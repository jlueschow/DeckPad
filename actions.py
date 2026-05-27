"""
Plattformübergreifende Aktionen für DeckPad-Buttons und -Knöpfe.

macOS : Quartz/AppKit (native OSD, keine Drittanbieter-Deps nötig)
Windows: pyautogui für Shortcuts + Media-Keys; os.startfile für Apps/URLs

Imports von Quartz/AppKit erfolgen nur auf macOS — kein ImportError auf Windows.
"""

import sys
import subprocess
import time

from log_sink import log

# ── macOS-only Imports ─────────────────────────────────────────────────────────
if sys.platform == "darwin":
    import Quartz
    from AppKit import NSEvent


# ── App & URL ──────────────────────────────────────────────────────────────────

def open_app(name: str):
    """Öffnet eine App per Name. macOS: 'open -a'. Windows: Shell-Start."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-a", name])
    else:
        try:
            subprocess.Popen(name, shell=True)
        except Exception as e:
            print(f"[open_app] Fehler: {e}")


def open_url(url: str):
    """Öffnet eine URL im Standardbrowser."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", url])
    else:
        import webbrowser
        webbrowser.open(url)


def open_app_by_path(path: str):
    """Öffnet eine App oder Datei per Pfad."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        try:
            import os
            os.startfile(path)          # type: ignore[attr-defined]
        except Exception as e:
            print(f"[open_app_by_path] Fehler: {e}")


def open_app_fn(name: str):
    """Gibt eine Zero-Arg-Funktion zurück, die open_app(name) aufruft."""
    return lambda: open_app(name)


# ── Media-Keys ─────────────────────────────────────────────────────────────────

def _post_media_key_macos(key_type: int):
    """Sendet einen Media-Key-Event via CoreGraphics (macOS)."""
    for is_down in (True, False):
        flags = 0xa00 if is_down else 0xb00
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            14, (0, 0), 0, 0, 0, None, 8,
            (key_type << 16) | flags, -1,
        )
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev.CGEvent())
        if is_down:
            time.sleep(0.02)


def _press_win(key: str):
    """Sendet einen einzelnen Tastendruck via pyautogui (Windows/Linux)."""
    try:
        import pyautogui
        pyautogui.press(key)
    except Exception as e:
        print(f"[media_key_win] Fehler ({key}): {e}")


def volume_up():
    if sys.platform == "darwin":
        _post_media_key_macos(0)          # NX_KEYTYPE_SOUND_UP
    else:
        _press_win("volumeup")


def volume_down():
    if sys.platform == "darwin":
        _post_media_key_macos(1)          # NX_KEYTYPE_SOUND_DOWN
    else:
        _press_win("volumedown")


def brightness_up():
    if sys.platform == "darwin":
        _post_media_key_macos(2)          # NX_KEYTYPE_BRIGHTNESS_UP
    else:
        _press_win("brightnessup")        # nur auf manchen Laptops verfügbar


def brightness_down():
    if sys.platform == "darwin":
        _post_media_key_macos(3)          # NX_KEYTYPE_BRIGHTNESS_DOWN
    else:
        _press_win("brightnessdown")


class MediaVolumeKnob:
    def turn(self, direction: int):
        volume_up() if direction > 0 else volume_down()


class MediaBrightnessKnob:
    def turn(self, direction: int):
        brightness_up() if direction > 0 else brightness_down()


# ── Keyboard shortcuts ─────────────────────────────────────────────────────────

# macOS Virtual Keycodes (Carbon)
_KEYCODES_MACOS: dict[str, int] = {
    # Letters
    'a': 0,  's': 1,  'd': 2,  'f': 3,  'h': 4,  'g': 5,  'z': 6,  'x': 7,
    'c': 8,  'v': 9,  'b': 11, 'q': 12, 'w': 13, 'e': 14, 'r': 15, 'y': 16,
    't': 17, 'i': 34, 'o': 31, 'u': 32, 'p': 35, 'l': 37, 'j': 38, 'k': 40,
    'm': 46, 'n': 45,
    # Digits
    '0': 29, '1': 18, '2': 19, '3': 20, '4': 21, '5': 23, '6': 22, '7': 26,
    '8': 28, '9': 25,
    # Function keys
    'f1': 122, 'f2': 120, 'f3': 99,  'f4': 118, 'f5': 96,  'f6': 97,
    'f7': 98,  'f8': 100, 'f9': 101, 'f10': 109,'f11': 103,'f12': 111,
    # Special keys
    'space': 49, 'return': 36, 'enter': 76, 'tab': 48, 'escape': 53,
    'delete': 51, 'backspace': 51, 'forwarddelete': 117,
    # Navigation
    'left': 123, 'right': 124, 'down': 125, 'up': 126,
    'home': 115, 'end': 119, 'pageup': 116, 'pagedown': 121,
    # Punctuation / symbols
    'minus': 27,  '-': 27,  'equal': 24, '=': 24,
    'plus': 24,
    'bracketleft': 33, '[': 33, 'bracketright': 30, ']': 30,
    'semicolon': 41, ';': 41, 'quote': 39, "'": 39,
    'comma': 43,  ',': 43,  'period': 47, '.': 47,
    'slash': 44,  '/': 44,  'backslash': 42, '\\': 42,
    'grave': 50,  '`': 50,
}

# macOS: F7–F12 ohne Modifier → als echte Media-Keys senden (NX_KEYTYPE_*)
# CGEventCreateKeyboardEvent sendet einen rohen Keycode und wird von macOS
# NICHT als Media-Key interpretiert — deshalb brauchen wir _post_media_key_macos.
_MACOS_FKEY_MEDIA: dict[str, int] = {
    'f7':  18,   # NX_KEYTYPE_PREVIOUS  (Vorheriger Titel)
    'f8':  16,   # NX_KEYTYPE_PLAY      (Play/Pause)
    'f9':  17,   # NX_KEYTYPE_NEXT      (Nächster Titel)
    'f10':  7,   # NX_KEYTYPE_MUTE
    'f11':  1,   # NX_KEYTYPE_SOUND_DOWN
    'f12':  0,   # NX_KEYTYPE_SOUND_UP
}

# Auf Windows: macOS f-key-Media-Shortcuts → native Media-Key-Namen
# Hintergrund: buttons.json nutzt f7–f12 für Mediatasten (macOS-Konvention).
# Auf Windows haben diese Tasten keine Mediafunktion — wir mappen auf echte
# Media-Keys damit die Bibliotheks-Vorlagen auch auf Windows funktionieren.
_MACOS_FKEY_TO_WIN_MEDIA: dict[str, str] = {
    'f7': 'prevtrack', 'f8': 'playpause', 'f9': 'nexttrack',
    'f10': 'volumemute', 'f11': 'volumedown', 'f12': 'volumeup',
}

# Alias-Umbenennungen für pyautogui
_WIN_KEY_REMAP: dict[str, str] = {
    'cmd': 'ctrl', 'command': 'ctrl',        # macOS Cmd → Windows Ctrl
    'opt': 'alt', 'option': 'alt',
    'control': 'ctrl',
    'return': 'enter',
    'delete': 'backspace',
}


def _send_shortcut_macos(keys: str):
    """Sendet Shortcut via CoreGraphics (macOS)."""
    parts = [p.strip().lower() for p in keys.split('+')]

    # F7–F12 ohne Modifier → als echte NX_KEYTYPE Media-Keys senden.
    # CGEventCreateKeyboardEvent(keycode=109) für F10 würde NUR einen rohen
    # F10-Tastendruck erzeugen — kein Mute-Media-Event. Daher dieser Pfad.
    if len(parts) == 1 and parts[0] in _MACOS_FKEY_MEDIA:
        nx_type = _MACOS_FKEY_MEDIA[parts[0]]
        log(f"shortcut ▶ macOS media-key  key={parts[0]!r}  NX_type={nx_type}")
        _post_media_key_macos(nx_type)
        return

    flags = 0
    key_part = None
    for part in parts:
        if part in ('cmd', 'command'):
            flags |= Quartz.kCGEventFlagMaskCommand
        elif part == 'shift':
            flags |= Quartz.kCGEventFlagMaskShift
        elif part in ('alt', 'opt', 'option'):
            flags |= Quartz.kCGEventFlagMaskAlternate
        elif part in ('ctrl', 'control'):
            flags |= Quartz.kCGEventFlagMaskControl
        else:
            key_part = part

    if key_part is None:
        return
    keycode = _KEYCODES_MACOS.get(key_part)
    if keycode is None:
        log(f"shortcut ▶ Unbekannter Keycode: {key_part!r}")
        print(f"[send_shortcut] Unbekannter Keycode: '{key_part}'")
        return

    log(f"shortcut ▶ macOS CGEvent  keycode={keycode}  flags=0x{flags:08X}")
    down = Quartz.CGEventCreateKeyboardEvent(None, keycode, True)
    Quartz.CGEventSetFlags(down, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
    time.sleep(0.05)
    up = Quartz.CGEventCreateKeyboardEvent(None, keycode, False)
    Quartz.CGEventSetFlags(up, flags)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)


def _send_shortcut_windows(keys: str):
    """Sendet Shortcut via pyautogui (Windows/Linux)."""
    try:
        import pyautogui
        parts = [p.strip().lower() for p in keys.split('+')]

        # Einzelne f-key Media-Shortcuts mappen (nur wenn kein Modifier dabei)
        if len(parts) == 1 and parts[0] in _MACOS_FKEY_TO_WIN_MEDIA:
            pyautogui.press(_MACOS_FKEY_TO_WIN_MEDIA[parts[0]])
            return

        # Modifier + Key-Aliasse umschreiben
        parts = [_WIN_KEY_REMAP.get(p, p) for p in parts]
        pyautogui.hotkey(*parts)
    except Exception as e:
        print(f"[send_shortcut_windows] Fehler: {e}")


def send_shortcut(keys: str):
    """
    Sendet einen Tastaturkurzbefehl.
    Format: 'cmd+z', 'cmd+shift+4', 'f12', 'space', 'ctrl+up', usw.
    """
    if not keys:
        return
    log(f"shortcut ▶ keys={keys!r}  platform={sys.platform}")
    if sys.platform == "darwin":
        _send_shortcut_macos(keys)
    else:
        _send_shortcut_windows(keys)
