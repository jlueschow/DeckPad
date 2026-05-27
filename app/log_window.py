"""
Schwebendes Ereignis-Log-Fenster für DeckPad.
Zeigt HID-Ereignisse, Aktionsaufrufe und Shortcut-Details in Echtzeit.
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, QLabel
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor

from log_sink import emitter

_window: "LogWindow | None" = None


def show_log_window(parent=None) -> "LogWindow":
    """Erstellt das Singleton-Fenster oder hebt es in den Vordergrund."""
    global _window
    if _window is None:
        _window = LogWindow(parent)
    _window.show()
    _window.raise_()
    _window.activateWindow()
    return _window


class LogWindow(QDialog):
    """Schwebendes, nicht-modales Fenster mit farbig codiertem Ereignis-Log."""

    # Farben nach Kategorie (erkannt anhand von Schlüsselwörtern in der Zeile)
    _COLORS = [
        ("HID ▶",      "#64D2FF"),   # blau   — rohe HID-Ereignisse
        ("shortcut ▶", "#30D158"),   # grün   — Shortcut-Ausführung
        ("ACTION ▶",   "#30D158"),   # grün   — allgemeine Aktionen
        ("KNOB_ACTION","#30D158"),   # grün
        ("press ▶",    "#FFD60A"),   # gelb   — Knob-Druck-Pipeline
        ("knob ▶",     "#FFD60A"),   # gelb
        ("Fehler",     "#FF453A"),   # rot    — Fehler
        ("Error",      "#FF453A"),
        ("fehler",     "#FF453A"),
    ]
    _DEFAULT_COLOR = "#AEAEB2"       # grau   — sonstiges

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DeckPad — Ereignis-Log")
        self.setMinimumSize(620, 400)
        self.resize(740, 520)
        # Unabhängiges Fenster — nicht modal, schließbar, minimierbar
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )
        self._setup_ui()
        emitter.message.connect(self._append)

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        hint = QLabel(
            "HID-Ereignisse, Aktionsaufrufe und Shortcut-Details in Echtzeit  —  "
            "<span style='color:#64D2FF'>blau</span> HID  "
            "<span style='color:#FFD60A'>gelb</span> Knob-Druck  "
            "<span style='color:#30D158'>grün</span> Aktion"
        )
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        hint.setTextFormat(Qt.TextFormat.RichText)
        lay.addWidget(hint)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        f = QFont("Menlo")
        f.setPointSize(11)
        f.setStyleHint(QFont.StyleHint.Monospace)
        self._text.setFont(f)
        self._text.setStyleSheet(
            "QTextEdit { background: #1C1C1E; color: #E5E5E7; "
            "border: 1px solid #3A3A3C; border-radius: 6px; }"
        )
        lay.addWidget(self._text, 1)

        btn_row = QHBoxLayout()
        clear_btn = QPushButton("Leeren")
        clear_btn.setObjectName("GhostButton")
        clear_btn.clicked.connect(self._text.clear)
        close_btn = QPushButton("Schließen")
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(clear_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

    def _append(self, msg: str):
        color = self._DEFAULT_COLOR
        for keyword, c in self._COLORS:
            if keyword in msg:
                color = c
                break

        # HTML-Sonderzeichen escapen, dann farbig ausgeben
        safe = (msg.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;"))
        self._text.append(f'<span style="color:{color};">{safe}</span>')
        self._text.moveCursor(QTextCursor.MoveOperation.End)

    def closeEvent(self, event):
        """Schließen-Knopf versteckt nur — Singleton bleibt erhalten."""
        self.hide()
        event.ignore()
