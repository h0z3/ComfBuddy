#!/usr/bin/env python3
"""
ComfBuddy v0.2.0
Floating ComfyUI desktop companion — right-click for shortcuts
Listens to ComfyUI events via WebSocket for live reactions
"""

import sys
import os
import json
import socket
import subprocess
import threading
import winsound
from pathlib import Path

# ─── Singleton lock ───────────────────────────────────────────────────────────
# Bind a localhost TCP port to guarantee only one buddy runs at a time.
# This makes auto-launch from the ComfyUI custom node safe to call repeatedly.
SINGLETON_PORT = 51847   # arbitrary high port, change if it collides
_singleton_sock = None   # kept alive for the lifetime of the process

def _acquire_singleton_lock() -> bool:
    global _singleton_sock
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", SINGLETON_PORT))
        s.listen(1)
    except OSError:
        return False
    _singleton_sock = s
    return True

try:
    import requests
except ImportError:
    print("[ComfBuddy] Eksik paket: pip install requests")
    sys.exit(1)

try:
    import websocket
except ImportError:
    print("[ComfBuddy] Eksik paket: pip install websocket-client")
    sys.exit(1)

try:
    from PyQt6.QtWidgets import QApplication, QWidget, QMenu
    from PyQt6.QtCore    import Qt, QTimer, QPoint, pyqtSignal
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
BOB_IDLE = [0, 0, -1, -1, -2, -2, -2, -1, -1, 0, 0, 1, 1, 2, 2, 2, 1, 1]
BOB_WORK = [0, -1, -2, -1, 0, 1, 2, 1]            # faster bob while generating
BOB_JUMP = [0, -3, -6, -8, -9, -8, -6, -3, 0, 1, 0]  # celebratory jump

# ─── Buddy states ────────────────────────────────────────────────────────────
STATE_IDLE     = "idle"
STATE_WORKING  = "working"      # ComfyUI is generating
STATE_SUCCESS  = "success"      # generation just finished
STATE_ERROR    = "error"        # generation failed

# How many ticks the success / error animation lasts before returning to idle
REACTION_TICKS = 20  # ~2 seconds at 100ms/tick


# ─── WebSocket listener (runs in background thread) ──────────────────────────

class ComfyWSListener(threading.Thread):
    """Connect to ComfyUI's WebSocket and emit state changes via a callback."""

    daemon = True

    def __init__(self, url: str, on_state):
        super().__init__()
        self.ws_url = url.replace("http", "ws", 1) + "/ws?clientId=comfbuddy"
        self.on_state = on_state   # callable(state_str)

    def run(self):
        while True:
            try:
                ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_message=self._on_msg,
                    on_error=self._on_err,
                    on_close=self._on_close,
                )
                ws.run_forever(ping_interval=10, ping_timeout=5)
            except Exception as e:
                print(f"[ComfBuddy WS] Error: {e}")
            # Reconnect after 5 s
            import time
            time.sleep(5)

    def _on_msg(self, _ws, message):
        try:
            data = json.loads(message)
        except (json.JSONDecodeError, TypeError):
            return
        msg_type = data.get("type", "")
        if msg_type == "execution_start":
            self.on_state(STATE_WORKING)
        elif msg_type == "executed":
            pass  # individual node done, keep working
        elif msg_type in ("execution_success",):
            self.on_state(STATE_SUCCESS)
        elif msg_type in ("execution_error", "execution_interrupted"):
            self.on_state(STATE_ERROR)
        elif msg_type == "status":
            # If queue is empty, back to idle
            q = data.get("data", {}).get("status", {}).get("exec_info", {})
            if q.get("queue_remaining", 0) == 0:
                pass  # don't override success/error animation

    def _on_err(self, _ws, error):
        print(f"[ComfBuddy WS] {error}")

    def _on_close(self, _ws, code, msg):
        print(f"[ComfBuddy WS] Disconnected ({code}), reconnecting…")


# ─── Widget ───────────────────────────────────────────────────────────────────

class BuddyWidget(QWidget):
    # Signal emitted from the WS thread to safely update state on the GUI thread
    state_changed = pyqtSignal(str)

    def __init__(self, cfg: dict):
        super().__init__()
        self.cfg = cfg
        self.s = cfg["scale"]           # pixels per logical pixel
        self._drag_pos = QPoint()
        self._bob_idx  = 0
        self._state    = STATE_IDLE
        self._reaction_remaining = 0    # countdown ticks for success/error anim
        self._flash_on = False          # toggle for error red flash

        # ── frameless transparent always-on-top window ──
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint      |
            Qt.WindowType.WindowStaysOnTopHint     |
            Qt.WindowType.Tool                      # no taskbar entry
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        w = SPRITE_W * self.s
        h = (SPRITE_H + 12) * self.s   # extra rows for shadow + jump headroom
        self.setFixedSize(w, h)

        x, y = cfg.get("position", [200, 200])
        self.move(x, y)

        # ── animation ──
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(100)          # 100 ms per frame → ~10 fps

        # ── state signal (thread-safe) ──
        self.state_changed.connect(self._on_state_changed)

        # ── WebSocket listener ──
        ws_listener = ComfyWSListener(cfg["comfyui_url"], self._emit_state)
        ws_listener.start()

    def _emit_state(self, state: str):
        """Called from WS thread — emit signal to cross into GUI thread."""
        self.state_changed.emit(state)

    def _on_state_changed(self, state: str):
        """Handle state transitions on the GUI thread."""
        prev = self._state

        if state == STATE_WORKING and prev != STATE_WORKING:
            self._state = STATE_WORKING
            self._bob_idx = 0
            print("[ComfBuddy] Generation started…")

        elif state == STATE_SUCCESS:
            self._state = STATE_SUCCESS
            self._bob_idx = 0
            self._reaction_remaining = REACTION_TICKS
            self._play_sound_success()
            print("[ComfBuddy] Generation complete!")

        elif state == STATE_ERROR:
            self._state = STATE_ERROR
            self._bob_idx = 0
            self._reaction_remaining = REACTION_TICKS
            self._play_sound_error()
            print("[ComfBuddy] Generation error!")

    # ── sounds ───────────────────────────────────────────────────────────────

    @staticmethod
    def _play_sound_success():
        """Play a happy 'ding' sound on success."""
        threading.Thread(
            target=lambda: (
                winsound.Beep(880, 150),  # A5
                winsound.Beep(1100, 150), # ~C#6
                winsound.Beep(1320, 250), # E6
            ),
            daemon=True,
        ).start()

    @staticmethod
    def _play_sound_error():
        """Play a descending 'buzz' sound on error."""
        threading.Thread(
            target=lambda: (
                winsound.Beep(400, 200),
                winsound.Beep(300, 300),
            ),
            daemon=True,
        ).start()

    # ── animation tick ───────────────────────────────────────────────────────

    def _tick(self):
        # Pick the right bob cycle for the current state
        if self._state == STATE_WORKING:
            cycle = BOB_WORK
        elif self._state == STATE_SUCCESS:
            cycle = BOB_JUMP
            self._reaction_remaining -= 1
            if self._reaction_remaining <= 0:
                self._state = STATE_IDLE
                self._bob_idx = 0
        elif self._state == STATE_ERROR:
            cycle = BOB_IDLE
            self._flash_on = not self._flash_on
            self._reaction_remaining -= 1
            if self._reaction_remaining <= 0:
                self._state = STATE_IDLE
                self._flash_on = False
                self._bob_idx = 0
        else:
            cycle = BOB_IDLE

        self._bob_idx = (self._bob_idx + 1) % len(cycle)
        self.update()

    # ── painting ─────────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        s = self.s

        # Pick bob cycle for current state
        if self._state == STATE_WORKING:
            cycle = BOB_WORK
        elif self._state == STATE_SUCCESS:
            cycle = BOB_JUMP
        else:
            cycle = BOB_IDLE

        bob = cycle[self._bob_idx % len(cycle)]

        # Extra vertical offset so jump doesn't clip at top
        y_base = 10 * s   # headroom for jump animation

        # --- shadow: ellipse below sprite, shrinks when higher ---
        shadow_y = y_base + SPRITE_H * s + s
        max_bob  = max(abs(min(cycle)), abs(max(cycle))) or 1
        bob_norm = (bob + max_bob) / (2 * max_bob)
        alpha    = int(60 + 80 * (1 - bob_norm))
        sw       = int((6 + 2 * (1 - bob_norm)) * s)
        sh       = max(1, s)
        sx       = (SPRITE_W * s - sw) // 2
        painter.setBrush(QColor(0, 0, 0, alpha))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(sx, shadow_y, sw, sh)

        # --- color tinting for states ---
        tint = None
        if self._state == STATE_ERROR and self._flash_on:
            tint = QColor(255, 60, 60, 100)  # red flash overlay
        elif self._state == STATE_SUCCESS:
            tint = QColor(255, 255, 100, 50)  # golden glow

        # --- sprite ---
        y_off = y_base + bob * s
        for row_i, row in enumerate(SPRITE):
            for col_i, ci in enumerate(row):
                if ci == 0:
                    continue
                color = PAL[ci]
                if color is None:
                    continue
                px = col_i * s
                py = row_i * s + y_off
                painter.fillRect(px, py, s, s, color)
                # overlay tint
                if tint and ci != 0:
                    painter.fillRect(px, py, s, s, tint)

        # --- sparkle particles on success ---
        if self._state == STATE_SUCCESS and self._reaction_remaining > 0:
            import math
            tick = REACTION_TICKS - self._reaction_remaining
            for i in range(6):
                angle = (tick * 0.3 + i * math.pi / 3)
                r = (tick * 1.5 + i * 2) * s * 0.3
                cx = SPRITE_W * s // 2 + int(math.cos(angle) * r)
                cy = y_off + SPRITE_H * s // 2 + int(math.sin(angle) * r)
                sparkle_alpha = max(0, 255 - tick * 20)
                sparkle_size = max(1, s // 2)
                painter.fillRect(
                    cx, cy, sparkle_size, sparkle_size,
                    QColor(255, 255, 120, sparkle_alpha),
                )

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
    # Singleton check: only one buddy instance at a time
    if not _acquire_singleton_lock():
        print("[ComfBuddy] Already running. Exiting.")
        return

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    cfg    = load_config()
    buddy  = BuddyWidget(cfg)
    buddy.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
