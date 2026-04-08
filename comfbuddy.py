#!/usr/bin/env python3
"""
ComfBuddy v0.1.0
Floating ComfyUI desktop companion — right-click for shortcuts
"""

import sys
import os
import json
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ComfBuddy] Eksik paket: pip install requests")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QMenu
    from PyQt6.QtCore    import Qt, QTimer, QPoint
    from PyQt6.QtGui     import QPainter, QColor
except ImportError:
    print("[ComfBuddy] Eksik paket: pip install PyQt6")
    sys.exit(1)

# ─── Config ───────────────────────────────────────────────────────────────────

DEFAULTS = {
    "comfyui_url":   "http://127.0.0.1:8188",
    "output_folder": str(Path.home() / "AppData" / "Roaming" / "ComfyUI" / "output"),
    "position":      [200, 200],
    "scale":         4,
}

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                return {**DEFAULTS, **json.load(f)}
        except Exception:
            pass
    return DEFAULTS.copy()


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# ─── Palette ──────────────────────────────────────────────────────────────────

def c(r, g, b, a=255):
    return QColor(r, g, b, a)

PAL = [
    None,               # 0  transparent
    c( 30,  38,  18),   # 1  dark outline
    c(130, 200,  50),   # 2  lime green body
    c(195, 245, 120),   # 3  bright highlight (upper-left glow)
    c( 72, 140,  28),   # 4  shadow green (right / lower)
    c( 22,  25,  18),   # 5  eye black
]

# ─── Sprite (16 w × 16 h logical pixels) ─────────────────────────────────────
# Classic pac-man-style ghost: round dome, two eyes, three bottom bumps

SPRITE = [
    #   0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15
    [   0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0],  #  0  dome top
    [   0, 0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 0, 0, 0],  #  1
    [   0, 1, 2, 3, 3, 2, 2, 2, 2, 2, 2, 4, 4, 1, 0, 0],  #  2  HL left / shadow right
    [   0, 1, 2, 3, 5, 5, 2, 2, 2, 5, 5, 4, 4, 1, 0, 0],  #  3  EYES
    [   0, 1, 2, 3, 5, 5, 2, 2, 2, 5, 5, 4, 4, 1, 0, 0],  #  4
    [   0, 1, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 4, 1, 0, 0],  #  5
    [   0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 1, 0, 0],  #  6
    [   1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 4, 1, 0],  #  7  body widens
    [   1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 4, 1, 0],  #  8
    [   1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 4, 1, 0],  #  9
    [   0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 1, 0],  # 10  narrows slightly
    [   0, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 4, 1, 0],  # 11
    # Bottom: 3 bumps — [1,2,2,1] [gap] [1,2,2,1] [gap] [1,2,2,1]
    [   0, 1, 2, 2, 1, 0, 1, 2, 2, 1, 0, 1, 2, 2, 1, 0],  # 12
    [   0, 1, 2, 2, 1, 0, 1, 2, 2, 1, 0, 1, 2, 2, 1, 0],  # 13
    [   0, 1, 1, 1, 0, 0, 1, 2, 2, 1, 0, 1, 1, 1, 0, 0],  # 14  outer bumps round off
    [   0, 0, 0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0],  # 15  center bump tip
]

SPRITE_W = 16
SPRITE_H = 16

# Smooth float cycle (logical pixel offsets, up = negative)
BOB = [0, 0, -1, -1, -2, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 2, 1, 1]


# ─── Widget ───────────────────────────────────────────────────────────────────

class BuddyWidget(QWidget):
    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.s = cfg["scale"]           # pixels per logical pixel
        self._drag_pos = QPoint()
        self._bob_idx  = 0

        # ── frameless transparent always-on-top window ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint      |
            Qt.WindowType.WindowStaysOnTopHint     |
            Qt.WindowType.Tool                      # no taskbar entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        w = SPRITE_W * self.s
        h = (SPRITE_H + 5) * self.s    # extra rows for shadow + bob headroom
        self.setFixedSize(w, h)

        x, y = cfg.get("position", [200, 200])
        self.move(x, y)

        # ── animation ──
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)          # 100 ms per frame → ~10 fps

    # ── animation tick ───────────────────────────────────────────────────────

    def _tick(self):
        self._bob_idx = (self._bob_idx + 1) % len(BOB)
        self.update()

    # ── painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        s   = self.s
        bob = BOB[self._bob_idx]        # logical-pixel vertical offset

        # --- shadow: ellipse below sprite, shrinks when higher ---
        base_y   = SPRITE_H * s + s
        max_bob  = max(BOB)
        bob_norm = (bob + max_bob) / (2 * max_bob) if max_bob else 0.5  # 0..1
        alpha    = int(60 + 80 * (1 - bob_norm))       # darker when lower
        sw       = int((6 + 2 * (1 - bob_norm)) * s)   # wider when lower
        sh       = max(1, s)
        sx       = (SPRITE_W * s - sw) // 2
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(sx, base_y, sw, sh)

        # --- sprite ---
        y_off = bob * s
        for row_i, row in enumerate(SPRITE):
            for col_i, ci in enumerate(row):
                if ci == 0:
                    continue
                color = PAL[ci]
                if color is None:
                    continue
                painter.fillRect(col_i * s, row_i * s + y_off, s, s, color)

    # ── drag ─────────────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (event.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.pos()
            self.cfg["position"] = [p.x(), p.y()]
            save_config(self.cfg)

    # ── context menu ─────────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #111a11;
                color: #88dd88;
                border: 1px solid #2a5a2a;
                font-family: Consolas, monospace;
                font-size: 12px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px 6px 12px;
            }
            QMenu::item:selected {
                background-color: #1e3a1e;
                color: #aaffaa;
            }
            QMenu::separator {
                height: 1px;
                background: #2a5a2a;
                margin: 4px 8px;
            }
        """)

        a_vram    = menu.addAction("  VRAM Temizle")
        a_restart = menu.addAction("  Yeniden Basla")
        a_output  = menu.addAction("  Output Klasoru")
        menu.addSeparator()
        a_quit    = menu.addAction("  Kapat")

        a_vram.triggered.connect(self.action_clear_vram)
        a_restart.triggered.connect(self.action_restart)
        a_output.triggered.connect(self.action_open_output)
        a_quit.triggered.connect(QApplication.quit)

        menu.exec(event.globalPos())

    # ── actions ───────────────────────────────────────────────────────────────

    def action_clear_vram(self):
        url = self.cfg["comfyui_url"]
        try:
            r = requests.post(
                f"{url}/free",
                json={"unload_models": True, "free_memory": True},
                timeout=5,
            )
            print(f"[ComfBuddy] VRAM temizlendi — HTTP {r.status_code}")
        except requests.exceptions.ConnectionError:
            print("[ComfBuddy] ComfyUI'ye bagilanamadi (calistigindan emin ol)")
        except Exception as e:
            print(f"[ComfBuddy] VRAM hatasi: {e}")

    def action_restart(self):
        """Kill the ComfyUI Desktop process, then relaunch it."""
        PROC_NAMES = [
            "ComfyUI Desktop.exe",
            "ComfyUI.exe",
            "comfyui-electron.exe",
        ]
        killed = False
        for name in PROC_NAMES:
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True,
            )
            if name in result.stdout:
                subprocess.run(["taskkill", "/F", "/IM", name], capture_output=True)
                print(f"[ComfBuddy] Sonlandirildi: {name}")
                killed = True
                break

        if not killed:
            print("[ComfBuddy] ComfyUI prosesi bulunamadi")

        # Relaunch after 2 s
        QTimer.singleShot(2000, self._launch_comfyui)

    def _launch_comfyui(self):
        candidates = [
            Path.home() / "AppData" / "Local" / "Programs" / "comfyui-electron" / "ComfyUI Desktop.exe",
            Path.home() / "AppData" / "Local" / "Programs" / "ComfyUI Desktop"  / "ComfyUI Desktop.exe",
            Path("C:/Program Files/ComfyUI Desktop/ComfyUI Desktop.exe"),
            Path("C:/Program Files (x86)/ComfyUI Desktop/ComfyUI Desktop.exe"),
        ]
        for path in candidates:
            if path.exists():
                subprocess.Popen([str(path)])
                print(f"[ComfBuddy] Baslatildi: {path}")
                return
        # Last-resort: let Windows find it by name
        subprocess.Popen(["start", "", "ComfyUI Desktop"], shell=True)
        print("[ComfBuddy] Baslatma komutu gonderildi (shell)")

    def action_open_output(self):
        folder = self.cfg["output_folder"]
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            print(f"[ComfBuddy] Output klasoru yok: {folder}")
            print("  config.json icindeki 'output_folder' degerini guncelle")


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    cfg    = load_config()
    buddy  = BuddyWidget(cfg)
    buddy.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
