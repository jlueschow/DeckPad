"""
Icon generator for AKP03E LCD buttons (76×76 px JPEG).

load_app_icon(path) — lädt echtes App-Icon aus .app-Bundle oder Bilddatei (kein AppKit)
make_icon(label)    — Text/Emoji-Fallback
"""

import io
import os
import plistlib
import subprocess
import tempfile
from PIL import Image, ImageDraw, ImageFont

ICON_SIZE = 76
_BG_DARK  = (28, 28, 36)


def _find_icns(app_path: str) -> str | None:
    """
    Findet die Haupt-.icns-Datei eines .app-Bundles.
    Strategie 1: CFBundleIconFile / CFBundleIconName aus Info.plist
    Strategie 2: Erste .icns-Datei in Contents/Resources als Fallback
    Gibt None zurück wenn nichts gefunden (z. B. Asset-Katalog-only Apps).
    """
    resources_dir = os.path.join(app_path, "Contents", "Resources")

    # Strategie 1: via Info.plist
    plist_path = os.path.join(app_path, "Contents", "Info.plist")
    if os.path.exists(plist_path):
        try:
            with open(plist_path, "rb") as f:
                plist = plistlib.load(f)
            icon_name = (plist.get("CFBundleIconFile") or
                         plist.get("CFBundleIconName") or
                         "AppIcon")
            if not icon_name.endswith(".icns"):
                icon_name += ".icns"
            icns_path = os.path.join(resources_dir, icon_name)
            if os.path.exists(icns_path):
                return icns_path
        except Exception:
            pass  # plist nicht lesbar oder Schlüssel fehlt → Strategie 2

    # Strategie 2: erste .icns-Datei in Resources
    if os.path.isdir(resources_dir):
        for name in sorted(os.listdir(resources_dir)):
            if name.endswith(".icns"):
                return os.path.join(resources_dir, name)

    return None




def _load_via_sips(icns_path: str) -> "Image.Image | None":
    """
    Konvertiert .icns → PNG via sips (macOS-builtin).
    Fallback wenn Pillow die Datei nicht direkt öffnen kann
    (z. B. .icns mit JPEG-2000-Einträgen, die Pillow ohne openjpeg nicht liest).
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name
        result = subprocess.run(
            ["sips", "-s", "format", "png", icns_path, "--out", tmp_path],
            capture_output=True, timeout=10
        )
        if result.returncode == 0 and os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
            img = Image.open(tmp_path).convert("RGBA")
            img.load()   # in Speicher laden bevor Datei gelöscht wird
            return img
    except Exception:
        pass
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    return None


def load_app_icon(path: str, size: int = ICON_SIZE, bg: tuple = _BG_DARK,
                  for_device: bool = True) -> bytes:
    """
    Lädt ein Icon aus:
      - einem .app-Bundle  → sucht .icns via Info.plist, Fallback via sips
      - einer Bilddatei    → .icns, .png, .jpg direkt
    for_device=True  → dreht 90° CW für LCD-Display
    for_device=False → natürliche Orientierung (für UI-Vorschau)
    Compositet auf dunklen Hintergrund, gibt JPEG zurück.
    """
    if path.endswith(".app"):
        icns_path = _find_icns(path)
        if not icns_path:
            raise FileNotFoundError(f"Kein .icns-Icon in App-Bundle gefunden: {path}")
    else:
        icns_path = path

    # Versuch 1: Pillow direkt
    img = None
    try:
        img = Image.open(icns_path).convert("RGBA")
    except Exception:
        pass

    # Versuch 2: sips als Fallback (macOS-builtin, versteht alle .icns-Formate)
    if img is None and icns_path.endswith(".icns"):
        img = _load_via_sips(icns_path)

    if img is None:
        raise OSError(f"Icon konnte weder per Pillow noch per sips geladen werden: {icns_path}")

    img = img.resize((size, size), Image.LANCZOS)
    if for_device:
        img = img.rotate(-90, expand=False)   # 90° CW — LCD-Display sitzt seitlich

    background = Image.new("RGB", (size, size), bg)
    background.paste(img, mask=img.split()[3])

    buf = io.BytesIO()
    background.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def make_icon(label: str, symbol: str = "", bg: tuple = (30, 30, 40),
              for_device: bool = True) -> bytes:
    """
    Text/Emoji-Fallback wenn kein App-Pfad vorhanden.
    for_device=True  → dreht 90° CW (wie load_app_icon) — Standard für Gerät
    for_device=False → natürliche Orientierung — für UI-Vorschau
    """
    img  = Image.new("RGB", (ICON_SIZE, ICON_SIZE), bg)
    draw = ImageDraw.Draw(img)

    try:
        font_sym  = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 36)
        font_text = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except Exception:
        font_sym  = ImageFont.load_default()
        font_text = font_sym

    cx = ICON_SIZE // 2
    if symbol:
        draw.text((cx, 36), symbol, font=font_sym,  fill=(255, 255, 255), anchor="mm")
        draw.text((cx, ICON_SIZE - 8), label, font=font_text, fill=(200, 200, 200), anchor="mm")
    else:
        draw.text((cx, cx), label, font=font_text, fill=(255, 255, 255), anchor="mm")

    if for_device:
        img = img.rotate(-90, expand=False)   # 90° CW — LCD-Display sitzt seitlich

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()
