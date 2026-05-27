#!/usr/bin/env python3
"""
Erzeugt assets/DeckPad.icns für den macOS App-Bundle.

Darstellung: dunkler abgerundeter Hintergrund, 6 Button-Kacheln (2×3) + 3 Knobs.
Spiegelt das physische Layout des AKP03E.
"""

import os
import shutil
import subprocess
from PIL import Image, ImageDraw


def _draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # ── Hintergrund: dunkles Blau-Grau, abgerundet ───────────────────────────
    r_bg = int(size * 0.22)
    draw.rounded_rectangle([0, 0, size - 1, size - 1],
                            radius=r_bg, fill=(26, 26, 46))

    pad   = size * 0.11
    gap   = size * 0.04
    cols  = 3
    rows  = 2

    # ── 6 Button-Kacheln (2 Reihen × 3 Spalten) ──────────────────────────────
    btn_area_w = size - 2 * pad
    btn_area_h = size * 0.52
    btn_w = (btn_area_w - (cols - 1) * gap) / cols
    btn_h = (btn_area_h - (rows - 1) * gap) / rows
    btn_r = max(2, int(btn_w * 0.18))

    for row in range(rows):
        for col in range(cols):
            x0 = pad + col * (btn_w + gap)
            y0 = pad + row * (btn_h + gap)
            x1 = x0 + btn_w
            y1 = y0 + btn_h
            # Hintergrund der Kachel
            draw.rounded_rectangle([x0, y0, x1, y1],
                                    radius=btn_r, fill=(55, 55, 88))
            # Heller Punkt oben links — simuliert kleines Display-Highlight
            hl = max(2, int(size * 0.022))
            draw.ellipse([x0 + hl, y0 + hl,
                           x0 + hl * 2.5, y0 + hl * 2.5],
                          fill=(120, 120, 180, 160))

    # ── 3 Knobs (Kreise unten) ────────────────────────────────────────────────
    knob_y = size * 0.795
    r_outer = size * 0.088
    r_inner = size * 0.048
    r_dot   = size * 0.014

    for i in range(3):
        cx = pad + (i + 0.5) * btn_area_w / 3
        cy = knob_y
        # Äußerer Ring
        draw.ellipse([cx - r_outer, cy - r_outer,
                       cx + r_outer, cy + r_outer],
                      fill=(70, 70, 105))
        # Innerer Kreis
        draw.ellipse([cx - r_inner, cy - r_inner,
                       cx + r_inner, cy + r_inner],
                      fill=(130, 130, 175))
        # Markierungs-Punkt oben
        draw.ellipse([cx - r_dot, cy - r_inner + r_dot * 0.8,
                       cx + r_dot, cy - r_inner + r_dot * 0.8 + r_dot * 2],
                      fill=(200, 200, 230))

    return img


_ICONSET_SIZES = [
    (16,   "icon_16x16.png"),
    (32,   "icon_16x16@2x.png"),
    (32,   "icon_32x32.png"),
    (64,   "icon_32x32@2x.png"),
    (128,  "icon_128x128.png"),
    (256,  "icon_128x128@2x.png"),
    (256,  "icon_256x256.png"),
    (512,  "icon_256x256@2x.png"),
    (512,  "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
]


def create_icns(output_path: str):
    iconset_dir = output_path.replace(".icns", ".iconset")
    os.makedirs(iconset_dir, exist_ok=True)

    for px, name in _ICONSET_SIZES:
        img = _draw_icon(px)
        img.save(os.path.join(iconset_dir, name))
        print(f"  {px:4d}px  →  {name}")

    subprocess.run(
        ["iconutil", "-c", "icns", iconset_dir, "-o", output_path],
        check=True
    )
    shutil.rmtree(iconset_dir)
    print(f"\nIcon gespeichert: {output_path}")


if __name__ == "__main__":
    base = os.path.dirname(os.path.abspath(__file__))
    out  = os.path.join(base, "assets", "DeckPad.icns")
    print("Erzeuge DeckPad.icns …")
    create_icns(out)
