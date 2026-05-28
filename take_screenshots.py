#!/usr/bin/env python3
"""
Automatisches Screenshot-Skript für DeckPad README.
Öffnet ConfigWindow + ButtonEditorDialog, macht Screenshots mit QScreen.

Aufruf:
    python3 take_screenshots.py
Ergebnis: docs/screenshots/*.png
"""

import sys
import os
import copy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── QApplication zuerst ───────────────────────────────────────────────────────
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QScreen

app = QApplication(sys.argv)
app.setApplicationName("DeckPad")
app.setStyle("Fusion")

try:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    NSApplication.sharedApplication().setActivationPolicy_(
        NSApplicationActivationPolicyAccessory
    )
except Exception:
    pass

from app.styles import APP_STYLE
app.setStyleSheet(APP_STYLE)

from config.config_manager import cfg, _init_user_data
_init_user_data()

OUT_DIR = os.path.join(os.path.dirname(__file__), "docs", "screenshots")
os.makedirs(OUT_DIR, exist_ok=True)


def grab_widget(widget, filename: str):
    """Macht Screenshot eines Widgets und speichert als PNG."""
    widget.raise_()
    widget.activateWindow()
    app.processEvents()
    screen: QScreen = widget.screen() or app.primaryScreen()
    pm = screen.grabWindow(widget.winId())
    path = os.path.join(OUT_DIR, filename)
    pm.save(path, "PNG")
    print(f"  Gespeichert: {path}")


def run():
    from app.config_window import ConfigWindow
    from app.button_editor import ButtonEditorDialog, KnobEditorDialog

    shots_taken = []

    # ── 1. Konfigurationsfenster ─────────────────────────────────────────────
    config_win = ConfigWindow()
    config_win.show()
    config_win.raise_()

    def shot_config():
        grab_widget(config_win, "01_config_window.png")
        shots_taken.append("config_window")
        QTimer.singleShot(200, open_button_editor)

    def open_button_editor():
        config = cfg.get()
        scenes = config.get("scenes", [])
        if not scenes:
            QTimer.singleShot(100, open_knob_editor)
            return
        # Ersten belegten Button wählen (oder ersten leeren)
        btn = next(
            (b for b in scenes[0].get("buttons", []) if b.get("label") or b.get("action")),
            scenes[0].get("buttons", [{"index": 1, "label": "Test", "icon": None,
                                       "action": {"type": "shortcut", "keys": "cmd+c"}}])[0]
        )
        dlg = ButtonEditorDialog(btn, config_win)
        dlg.show()
        dlg.raise_()

        def shot_btn():
            grab_widget(dlg, "02_button_editor.png")
            shots_taken.append("button_editor")
            dlg.reject()
            QTimer.singleShot(200, open_knob_editor)

        QTimer.singleShot(300, shot_btn)

    def open_knob_editor():
        config = cfg.get()
        scenes = config.get("scenes", [])
        knob = (scenes[0].get("knobs", []) or [{"index": 1, "label": "Lautstärke",
                "action": {"type": "volume"}}])[0] if scenes else {
            "index": 1, "label": "Lautstärke", "action": {"type": "volume"}}
        dlg = KnobEditorDialog(knob, config_win)
        dlg.show()
        dlg.raise_()

        def shot_knob():
            grab_widget(dlg, "03_knob_editor.png")
            shots_taken.append("knob_editor")
            dlg.reject()
            QTimer.singleShot(200, finish)

        QTimer.singleShot(300, shot_knob)

    def finish():
        print(f"\nFertig — {len(shots_taken)} Screenshots in {OUT_DIR}/")
        for s in shots_taken:
            print(f"  - {s}")
        config_win.close()
        QTimer.singleShot(100, app.quit)

    QTimer.singleShot(600, shot_config)
    app.exec()


if __name__ == "__main__":
    run()
