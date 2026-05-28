#!/usr/bin/env python3
"""
Generiert PNG-Icons für die Button-Bibliothek aus SF Symbols (macOS).

Workflow:
  1. SF Symbol via AppKit auf transparentem Canvas rendern
  2. Alpha-Kanal als Maske extrahieren → Symbol in Weiß umfärben
  3. Auf farbigen, abgerundeten Hintergrund (PIL) compositen
  4. Als PNG im angegebenen Verzeichnis speichern

Ausführen (manuell oder vor pyinstaller):
    python3 create_library_icons.py

Rechtlicher Hinweis:
  SF Symbols sind urheberrechtlich geschützt (Apple Inc.).
  Die generierten Icons dürfen nicht in öffentliche Git-Repositories
  eingecheckt werden. Sie werden lokal generiert und verbleiben auf
  dem jeweiligen Rechner (assets/icons/ ist in .gitignore).
"""

import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
ICONS_DIR = os.path.join(BASE_DIR, "assets", "icons")

ICON_SIZE = 76   # Canvas-Größe (Pixel) — passt zu ICON_DISP im UI
SYM_SIZE  = 42   # SF-Symbol-Rendergröße innerhalb des Canvas
CORNER_R  = 10   # Eckenradius des Hintergrunds

# ── Icon-Definitionen ──────────────────────────────────────────────────────────
# (dateiname, sf_symbol_name, hintergrund_rgb)

ICONS = [
    # ── App-Steuerung ──────────────────────────────────────────────────────────
    ("open_config.png",  "gearshape.fill",                       ( 40,  40,  55)),

    # ── Apps (nur emoji-basierte — app-pfad-basierte behalten ihr echtes Icon) ──
    ("app_terminal.png",  "terminal",                           ( 20,  30,  20)),
    ("app_finder.png",    "folder.badge.magnifyingglass",       ( 20,  60, 130)),
    ("app_vscode.png",    "chevron.left.forwardslash.chevron.right",
                                                                (  0,  70, 150)),
    ("app_spotify.png",   "music.note",                         ( 30, 120,  30)),
    ("app_slack.png",     "message.fill",                       ( 60,  20,  60)),
    ("app_zoom.png",      "video.fill",                         ( 20,  80, 180)),
    ("app_discord.png",   "gamecontroller.fill",                ( 50,  40, 120)),
    ("app_whatsapp.png",  "phone.fill",                         ( 20, 100,  30)),
    ("app_cubase.png",    "waveform",                           ( 80,  60,  20)),
    ("app_notes.png",     "note.text",                          (120, 100,  20)),

    # ── System ─────────────────────────────────────────────────────────────────
    ("vol_up.png",        "speaker.wave.3.fill",                ( 30,  30,  80)),
    ("vol_down.png",      "speaker.wave.1.fill",                ( 30,  30,  80)),
    ("mute.png",          "speaker.slash.fill",                 ( 80,  30,  30)),
    ("bright_up.png",     "sun.max.fill",                       (120,  80,  10)),
    ("bright_dn.png",     "sun.min",                            ( 80,  60,  10)),
    ("screenshot.png",    "camera.viewfinder",                  ( 60,  40,  80)),
    ("lock.png",          "lock.fill",                          ( 40,  40,  60)),
    ("mission.png",       "rectangle.3.group.fill",             ( 30,  60, 100)),
    ("spotlight.png",     "magnifyingglass",                    ( 50,  50,  50)),
    ("desktop.png",       "desktopcomputer",                    ( 30,  30,  60)),
    ("lock_screen.png",   "display.and.arrow.down",             ( 40,  40,  70)),
    ("logout.png",        "door.right.hand.open",               ( 70,  40,  20)),
    ("restart.png",       "arrow.clockwise.circle.fill",        ( 20,  60, 100)),
    ("shutdown.png",      "power",                              ( 80,  20,  20)),

    # ── Medien ─────────────────────────────────────────────────────────────────
    ("play_pause.png",    "playpause.fill",                     ( 20,  80,  40)),
    ("next_track.png",    "forward.end.fill",                   ( 20,  80,  40)),
    ("prev_track.png",    "backward.end.fill",                  ( 20,  80,  40)),
    ("stop_media.png",    "stop.fill",                          ( 80,  20,  20)),

    # ── Logic Pro spezifisch ──────────────────────────────────────────────────
    ("logic_record.png",  "record.circle.fill",                 (130,  15,  15)),
    ("logic_solo.png",    "headphones",                         (130,  90,  10)),
    ("logic_new.png",     "plus.rectangle.fill",                ( 20,  80,  40)),
    ("logic_open.png",    "folder.fill",                        ( 20,  60, 130)),
    ("logic_movie.png",   "film.fill",                          ( 70,  30, 110)),
    ("logic_import.png",  "waveform.badge.plus",                ( 20,  80,  80)),

    # ── Bearbeiten ─────────────────────────────────────────────────────────────
    ("undo.png",          "arrow.uturn.backward",               ( 60,  60,  60)),
    ("redo.png",          "arrow.uturn.forward",                ( 60,  60,  60)),
    ("copy.png",          "doc.on.doc.fill",                    ( 40,  60,  80)),
    ("paste.png",         "clipboard.fill",                     ( 40,  60,  80)),
    ("cut.png",           "scissors",                           ( 80,  40,  40)),
    ("save.png",          "square.and.arrow.down.fill",         ( 20,  80,  60)),
    ("find.png",          "magnifyingglass",                    ( 60,  40,  80)),
    ("new_tab.png",       "plus.rectangle.on.rectangle",        ( 30,  80,  30)),
    ("close_tab.png",     "xmark.rectangle.fill",               ( 80,  30,  30)),
]


# ── SF-Symbol-Renderer ─────────────────────────────────────────────────────────

def _render_sf_symbol(symbol_name: str, size: int) -> "Image.Image | None":
    """
    Rendert ein SF Symbol via CGBitmapContext direkt in einen Rohpixelpuffer.

    Verwendet absichtlich KEIN ImageIO (kein TIFF, kein PNG-Codec) —
    auf macOS 26.x führt TIFFRepresentation() zu einem SIGBUS in
    SetupTIFFErrorHandler() (vergifteter Funktionszeiger in ImageIO).
    CGBitmapContextCreate + PIL.Image.frombuffer() umgeht ImageIO vollständig.

    Gibt ein PIL RGBA Image zurück, oder None bei Fehler.
    """
    try:
        import ctypes
        from AppKit import NSImage, NSGraphicsContext, NSMakeRect
        from Quartz import (
            CGBitmapContextCreate,
            CGColorSpaceCreateDeviceRGB,
            kCGImageAlphaPremultipliedLast,
        )

        sym = NSImage.imageWithSystemSymbolName_accessibilityDescription_(
            symbol_name, None
        )
        if sym is None:
            return None

        # Rohpuffer anlegen: width × height × 4 Byte (RGBA)
        bytes_per_row = size * 4
        buf = (ctypes.c_uint8 * (bytes_per_row * size))()

        cs     = CGColorSpaceCreateDeviceRGB()
        cg_ctx = CGBitmapContextCreate(
            buf, size, size, 8, bytes_per_row, cs,
            kCGImageAlphaPremultipliedLast,
        )
        if cg_ctx is None:
            return None

        # NSGraphicsContext auf den CG-Kontext zeigen lassen.
        # flipped=True: y=0 ist oben → Zeilenreihenfolge im Puffer
        # entspricht direkt PIL (kein nachträgliches Spiegeln nötig).
        ns_ctx = NSGraphicsContext.graphicsContextWithCGContext_flipped_(
            cg_ctx, True
        )
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.setCurrentContext_(ns_ctx)
        sym.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, size, size),
            NSMakeRect(0, 0, 0, 0),   # 0,0,0,0 = gesamtes Quellbild
            17,                        # NSCompositingOperationSourceOver
            1.0,
        )
        NSGraphicsContext.restoreGraphicsState()

        # Rohdaten direkt → PIL, kein ImageIO beteiligt
        img = Image.frombuffer(
            "RGBA", (size, size), bytes(buf), "raw", "RGBA", 0, 1
        )
        return img.convert("RGBA")

    except Exception as exc:
        print(f"    AppKit Fehler für '{symbol_name}': {exc}", file=sys.stderr)
        return None


# ── Icon-Komposition ───────────────────────────────────────────────────────────

def make_icon(filename: str, symbol_name: str, bg_rgb: tuple) -> bytes:
    """
    Baut ein 76×76 px PNG:
      1. Farbiger, abgerundeter Hintergrund (PIL)
      2. SF Symbol als weiße Silhouette zentriert darüber
    Fallback (kein AppKit / Symbol nicht vorhanden): Label-Text aus Dateiname.
    """
    S = ICON_SIZE

    # ── Hintergrund ────────────────────────────────────────────────────────────
    canvas = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        [(0, 0), (S - 1, S - 1)],
        radius=CORNER_R,
        fill=bg_rgb + (255,),
    )

    # ── SF Symbol in Weiß ──────────────────────────────────────────────────────
    sym_img = _render_sf_symbol(symbol_name, SYM_SIZE)
    if sym_img is not None:
        # Retina-Displays liefern 2× — auf SYM_SIZE normalisieren
        if sym_img.size != (SYM_SIZE, SYM_SIZE):
            sym_img = sym_img.resize((SYM_SIZE, SYM_SIZE), Image.LANCZOS)
        # Alpha-Kanal als Maske → alle Symbolflächen werden weiß
        *_, alpha = sym_img.split()
        white_sym = Image.new("RGBA", (SYM_SIZE, SYM_SIZE), (255, 255, 255, 0))
        white_sym.putalpha(alpha)

        ox = (S - SYM_SIZE) // 2
        oy = (S - SYM_SIZE) // 2
        canvas.paste(white_sym, (ox, oy), white_sym)
    else:
        # Fallback: Label-Text (Dateiname ohne .png, Unterstriche → Leerzeichen)
        label = os.path.splitext(filename)[0].replace("_", " ").title()
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 10)
        except Exception:
            font = ImageFont.load_default()
        draw.text((S // 2, S // 2), label, font=font,
                  fill=(255, 255, 255, 255), anchor="mm")

    # ── PNG-Bytes ──────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


# ── Öffentliche API ────────────────────────────────────────────────────────────

def generate_icons(icons_dir: str = None, silent: bool = False) -> bool:
    """
    Generiert alle Icons in icons_dir (Standard: assets/icons/ im Projektordner).
    Gibt True zurück wenn alle Icons erfolgreich generiert wurden.
    Kann aus app_main.py aufgerufen werden (nach QApplication, Hauptthread).
    """
    out_dir = icons_dir or ICONS_DIR
    os.makedirs(out_dir, exist_ok=True)
    total = len(ICONS)
    ok    = 0

    if not silent:
        print(f"Generiere {total} Icons in {out_dir}\n")

    for filename, symbol, bg in ICONS:
        path = os.path.join(out_dir, filename)
        try:
            data = make_icon(filename, symbol, bg)
            with open(path, "wb") as f:
                f.write(data)
            if not silent:
                print(f"  ✓  {filename:<30}  {len(data)/1024:4.1f} kB")
            ok += 1
        except Exception as exc:
            if not silent:
                print(f"  ✗  {filename}: {exc}")

    if not silent:
        print(f"\n{ok}/{total} erfolgreich.")
    return ok == total


def icons_exist(icons_dir: str = None) -> bool:
    """Gibt True zurück wenn mindestens die Hälfte der Icons bereits vorhanden ist."""
    out_dir = icons_dir or ICONS_DIR
    if not os.path.isdir(out_dir):
        return False
    existing = sum(1 for f, _, _ in ICONS if os.path.exists(os.path.join(out_dir, f)))
    return existing >= len(ICONS) // 2


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    generate_icons(silent=False)
