"""
Autostart-Verwaltung für DeckPad.

macOS : launchd-Plist in ~/Library/LaunchAgents/app.deckpad.plist
Windows: Registry-Eintrag HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run

Verwendung:
    import autostart
    autostart.is_enabled()  → bool
    autostart.enable()      → bool  (True = Erfolg)
    autostart.disable()     → bool  (True = Erfolg)
"""

import sys
import os
import subprocess

# ── Konstanten ─────────────────────────────────────────────────────────────────

_LABEL       = "app.deckpad"
_PLIST_PATH  = os.path.expanduser(f"~/Library/LaunchAgents/{_LABEL}.plist")
_WIN_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_WIN_NAME    = "DeckPad"

# Python-Interpreter und Hauptskript (absolut, zur Laufzeit ermittelt)
_PYTHON = sys.executable
_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_main.py")


# ── Öffentliche API ────────────────────────────────────────────────────────────

def is_enabled() -> bool:
    """Gibt True zurück wenn Autostart aktiv ist."""
    if sys.platform == "darwin":
        return os.path.exists(_PLIST_PATH)
    if sys.platform == "win32":
        try:
            import winreg
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_REG_KEY)
            winreg.QueryValueEx(k, _WIN_NAME)
            winreg.CloseKey(k)
            return True
        except Exception:
            return False
    return False


def enable() -> bool:
    """Aktiviert Autostart beim Login. Gibt True bei Erfolg zurück."""
    if sys.platform == "darwin":
        return _enable_macos()
    if sys.platform == "win32":
        return _enable_windows()
    print("[autostart] Autostart wird nur auf macOS und Windows unterstützt.")
    return False


def disable() -> bool:
    """Deaktiviert Autostart. Gibt True bei Erfolg zurück."""
    if sys.platform == "darwin":
        return _disable_macos()
    if sys.platform == "win32":
        return _disable_windows()
    return False


# ── macOS ──────────────────────────────────────────────────────────────────────

_PLIST_TEMPLATE = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>{script}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/deckpad.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/deckpad.log</string>
</dict>
</plist>
"""


def _enable_macos() -> bool:
    try:
        plist_dir = os.path.dirname(_PLIST_PATH)
        os.makedirs(plist_dir, exist_ok=True)
        content = _PLIST_TEMPLATE.format(
            label=_LABEL, python=_PYTHON, script=_SCRIPT
        )
        with open(_PLIST_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        # Sofort laden — Fehler ignorieren (Plist ist bei nächstem Login aktiv)
        uid = os.getuid()
        subprocess.run(
            ["launchctl", "bootstrap", f"gui/{uid}", _PLIST_PATH],
            capture_output=True,
        )
        return True
    except Exception as e:
        print(f"[autostart] macOS enable Fehler: {e}")
        return False


def _disable_macos() -> bool:
    try:
        if os.path.exists(_PLIST_PATH):
            uid = os.getuid()
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}", _PLIST_PATH],
                capture_output=True,
            )
            os.remove(_PLIST_PATH)
        return True
    except Exception as e:
        print(f"[autostart] macOS disable Fehler: {e}")
        return False


# ── Windows ────────────────────────────────────────────────────────────────────

def _enable_windows() -> bool:
    try:
        import winreg
        cmd = f'"{_PYTHON}" "{_SCRIPT}"'
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(k, _WIN_NAME, 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(k)
        return True
    except Exception as e:
        print(f"[autostart] Windows enable Fehler: {e}")
        return False


def _disable_windows() -> bool:
    try:
        import winreg
        k = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _WIN_REG_KEY, 0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(k, _WIN_NAME)
        except FileNotFoundError:
            pass   # war bereits deaktiviert
        winreg.CloseKey(k)
        return True
    except Exception as e:
        print(f"[autostart] Windows disable Fehler: {e}")
        return False
