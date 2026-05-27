# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller-Spec für DeckPad.app (macOS)

Bauen:
    pyinstaller DeckPad.spec

Ergebnis: dist/DeckPad.app
"""

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── PyObjC: alle Sub-Module sammeln ───────────────────────────────────────────
_pyobjc_hidden = (
    collect_submodules("objc") +
    collect_submodules("Foundation") +
    collect_submodules("AppKit") +
    collect_submodules("Quartz") +
    collect_submodules("CoreFoundation")
)

_pyobjc_datas = (
    collect_data_files("objc") +
    collect_data_files("Foundation") +
    collect_data_files("AppKit") +
    collect_data_files("Quartz") +
    collect_data_files("CoreFoundation")
)

# ── Analyse ───────────────────────────────────────────────────────────────────

a = Analysis(
    ["app_main.py"],
    pathex=["."],
    binaries=[],
    datas=[
        # Button-Bibliothek (read-only, wird beim ersten Start in User-Data kopiert)
        ("data/library/buttons.json", "data/library"),
        # SF-Symbol-Icons für Bibliotheks-Buttons
        ("assets/icons",              "assets/icons"),
        # App-Icon (für Tray-Icon-Fallback)
        ("assets/DeckPad.icns",       "assets"),
    ] + _pyobjc_datas,
    hiddenimports=[
        # Eigene Module (lazy imports via menu_bar._start_hid etc.)
        "app.menu_bar",
        "app.config_window",
        "app.hid_thread",
        "app.button_editor",
        "app.library_panel",
        "app.scene_widget",
        "app.styles",
        "app.log_window",
        "config.config_manager",
        "log_sink",
        "autostart",
        "actions",
        "icons",
        "akp03e",
        # PIL
        "PIL.Image",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        "PIL.ImageOps",
        "PIL.JpegImagePlugin",
        "PIL.PngImagePlugin",
        # PySide6
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        # PyObjC
        "objc",
        "Foundation",
        "AppKit",
        "Quartz",
        "Quartz.CoreGraphics",
        "CoreFoundation",
    ] + _pyobjc_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter", "unittest", "email", "html", "http",
        "xmlrpc", "pydoc", "doctest", "difflib",
        "matplotlib", "numpy", "scipy", "pandas",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DeckPad",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX kann PyObjC-Binaries beschädigen → aus
    console=False,      # Kein Terminal-Fenster
    icon="assets/DeckPad.icns",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="DeckPad",
)

app = BUNDLE(
    coll,
    name="DeckPad.app",
    icon="assets/DeckPad.icns",
    bundle_identifier="app.deckpad",
    version="1.0.0",
    info_plist={
        "CFBundleName":               "DeckPad",
        "CFBundleDisplayName":        "DeckPad",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion":            "1.0.0",
        "NSPrincipalClass":           "NSApplication",
        "NSHighResolutionCapable":    True,
        "LSUIElement":                True,   # Kein Dock-Icon (Menu-Bar-Only)
        "LSMinimumSystemVersion":     "13.0",
        "NSAppleEventsUsageDescription": "DeckPad benötigt Apple Events für Systemaktionen.",
    },
)
