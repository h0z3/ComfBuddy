#!/usr/bin/env python3
"""Render ComfBuddy sprites as PNG images for the README / GitHub page."""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QPainter, QColor
from PyQt6.QtCore import Qt

# Re-use palette and sprite from main module
from comfbuddy import PAL, SPRITE, SPRITE_W, SPRITE_H


def render_sprite(scale: int, bg_color=None) -> QImage:
    """Render the sprite at the given scale to a QImage with transparency."""
    w = SPRITE_W * scale
    h = SPRITE_H * scale
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))  # transparent

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    if bg_color:
        painter.fillRect(0, 0, w, h, bg_color)

    for row_i, row in enumerate(SPRITE):
        for col_i, ci in enumerate(row):
            if ci == 0:
                continue
            color = PAL[ci]
            if color is None:
                continue
            painter.fillRect(col_i * scale, row_i * scale, scale, scale, color)

    painter.end()
    return img


def render_banner(scale: int = 10) -> QImage:
    """Render a banner with the buddy centered on a dark background."""
    sprite_w = SPRITE_W * scale
    sprite_h = SPRITE_H * scale
    pad_x, pad_y = scale * 6, scale * 4
    banner_w = sprite_w + pad_x * 2
    banner_h = sprite_h + pad_y * 2

    img = QImage(banner_w, banner_h, QImage.Format.Format_ARGB32)
    img.fill(QColor(22, 27, 22))  # dark green-ish bg

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    # Shadow
    shadow_w = 8 * scale
    shadow_h = max(2, scale // 2)
    sx = pad_x + (sprite_w - shadow_w) // 2
    sy = pad_y + sprite_h + scale
    painter.setBrush(QColor(0, 0, 0, 80))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(sx, sy, shadow_w, shadow_h)

    # Sprite
    for row_i, row in enumerate(SPRITE):
        for col_i, ci in enumerate(row):
            if ci == 0:
                continue
            color = PAL[ci]
            if color is None:
                continue
            painter.fillRect(
                pad_x + col_i * scale,
                pad_y + row_i * scale,
                scale, scale, color,
            )

    # Title text
    from PyQt6.QtGui import QFont
    font = QFont("Consolas", scale * 2)
    font.setBold(True)
    painter.setFont(font)
    painter.setPen(QColor(130, 200, 50))
    text_y = pad_y + sprite_h + scale * 4
    painter.drawText(0, 0, banner_w, text_y + scale * 3,
                     Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
                     "ComfBuddy")

    painter.end()
    return img


def main():
    app = QApplication(sys.argv)

    # 1. Sprite only (transparent background) — for inline use
    sprite_img = render_sprite(scale=8)
    sprite_img.save("assets/buddy.png")
    print("[OK] assets/buddy.png")

    # 2. Banner with dark bg — for README header
    banner_img = render_banner(scale=8)
    banner_img.save("assets/banner.png")
    print("[OK] assets/banner.png")

    # 3. Small icon (for repo social preview etc.)
    icon_img = render_sprite(scale=16)
    icon_img.save("assets/icon.png")
    print("[OK] assets/icon.png")

    app.quit()


if __name__ == "__main__":
    main()
