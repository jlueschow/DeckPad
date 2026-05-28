#!/usr/bin/env python3
"""
DeckPad — macOS Menu-Bar-App Einstiegspunkt.

Wichtig: app.menu_bar (und damit Quartz/AppKit via actions.py) wird
NACH QApplication-Erstellung importiert, damit PySide6 zuerst seinen
eigenen Cocoa-Stack initialisiert. Sonst: Bus Error.

Verwendung:
    python3 app_main.py
"""

import sys
import os
import faulthandler

# Gibt bei Bus Error / Segfault einen nativen Stack-Trace aus
faulthandler.enable()

# Sicherstellen, dass alle Module gefunden werden
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # ── Library-Icons ggf. generieren — VOR QApplication ─────────────────────
    # NSImage.lockFocus() (in create_library_icons.py) ist inkompatibel mit dem
    # Cocoa-Stack den PySide6 aufbaut. Lösung: Generation als Subprocess bevor
    # QApplication initialisiert wird. Zu diesem Zeitpunkt gibt es noch kein
    # aktives Fenster → kein Fokus-Raub möglich (Bug 8).
    import subprocess
    _base     = os.path.dirname(os.path.abspath(__file__))
    _icons    = os.path.join(_base, "assets", "icons")
    _script   = os.path.join(_base, "create_library_icons.py")
    _n_icons  = sum(1 for f in os.listdir(_icons) if f.endswith(".png")) if os.path.isdir(_icons) else 0
    if _n_icons < 10 and os.path.exists(_script):
        try:
            subprocess.run([sys.executable, _script], capture_output=True, timeout=60)
        except Exception:
            pass  # Icons fehlen → Bibliothek zeigt Fallback-Text

    # ── QApplication ZUERST erzeugen ─────────────────────────────────────────
    # ALLE weiteren Imports (Quartz, AppKit, HIDThread, ConfigWindow) kommen
    # erst danach — sonst initialisiert AppKit den Cocoa-Stack vor PySide6
    # und verursacht einen Bus Error.
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer

    app = QApplication(sys.argv)
    app.setApplicationName("DeckPad")
    app.setApplicationDisplayName("DeckPad")
    app.setOrganizationName("DeckPad")
    app.setOrganizationDomain("deckpad.app")
    app.setQuitOnLastWindowClosed(False)

    # ── Dock-Icon ausblenden (Menu-Bar-Only-App) ──────────────────────────────
    # NSApplicationActivationPolicyAccessory: App läuft im Hintergrund,
    # kein Dock-Icon, kein App-Switcher-Eintrag — genau richtig für Menu-Bar-Apps.
    # Import NACH QApplication, damit PySide6 seinen Cocoa-Stack zuerst aufbaut.
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyAccessory
        )
    except Exception:
        pass  # Kein macOS / kein pyobjc installiert — ignorieren

    # ── Fusion-Style: plattformunabhängiger Renderer, folgt 100% dem Stylesheet ─
    # Ohne dies ignoriert macOS (native Cocoa-Style) background: auf QTabBar,
    # QScrollBar, QGroupBox etc. und zeichnet alles nativ hell.
    app.setStyle("Fusion")

    # ── Globales Stylesheet — gilt für alle Fenster inkl. Dialoge ─────────────
    from app.styles import APP_STYLE
    app.setStyleSheet(APP_STYLE)

    # ── App-Module erst NACH QApplication importieren ─────────────────────────
    # (Quartz/AppKit via actions.py darf nicht vor QApplication initialisiert werden)
    from config.config_manager import _init_user_data
    _init_user_data()   # Nutzerdaten-Verzeichnis beim ersten Start anlegen (Bundle)

    from app.menu_bar import MenuBarApp

    # ── Menu-Bar-App starten ──────────────────────────────────────────────────
    # HID-Thread und ConfigWindow starten sich intern verzögert (400/800 ms)
    # damit der Qt-Event-Loop zuerst vollständig hochgefahren ist.
    menu_bar = MenuBarApp(app)   # noqa: F841  (Referenz muss gehalten werden)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
