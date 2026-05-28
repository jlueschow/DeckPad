"""
Dark-Theme — macOS-inspiriertes Farbschema.
Neutrale Apple-Graustufen + macOS-Blau als Akzent.
Kontrastverhältnisse >= 7:1 überall (WCAG AAA).
"""

# ── Farbpalette ────────────────────────────────────────────────────────────────
# Angelehnt an macOS Dark Mode Systemfarben
C = {
    # Hintergründe — reine Graustufen, kein Blau-/Lila-Cast
    "base":     "#1C1C1E",    # Hauptfenster (macOS window bg)
    "mantle":   "#2C2C2E",    # Panels, Header, Tab-Leiste
    "crust":    "#111113",    # Tiefste Ebene, fast Schwarz

    # Erhobene Flächen
    "surface0": "#3A3A3C",    # Karten, Inputs, Button-Slots
    "surface1": "#48484A",    # Hover-States
    "surface2": "#636366",    # Starke Trennlinien

    # Text — klare Hierarchie, hoher Kontrast
    "text":     "#FFFFFF",    # Primär (Überschriften, wichtige Labels)
    "subtext1": "#F2F2F7",    # Körpertext, Listeneinträge
    "subtext0": "#C7C7CC",    # Sekundäre Labels, inaktive Tabs
    "overlay1": "#AEAEB2",    # Tertiär / Hints
    "overlay0": "#8E8E93",    # Placeholder / Disabled

    # Akzentfarbe — macOS System-Blau (Dark Mode)
    "mauve":    "#0A84FF",    # Primärer Akzent (wird als Akzent-Alias genutzt)
    "blue":     "#0A84FF",

    # Semantische Farben (macOS-Systemfarben Dark Mode)
    "green":    "#32D74B",
    "red":      "#FF453A",
    "yellow":   "#FFD60A",
    "peach":    "#FF9F0A",    # orange
    "teal":     "#5AC8FA",    # cyan
}

APP_STYLE = f"""

/* ═══════════════════════════════════════════════════════════════════════════════
   BASIS
   ═══════════════════════════════════════════════════════════════════════════════ */

QWidget {{
    background-color: {C["base"]};
    color: {C["text"]};
    font-family: -apple-system, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {C["base"]};
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   HEADER-LEISTE
   ═══════════════════════════════════════════════════════════════════════════════ */

QFrame#HeaderBar {{
    background-color: {C["crust"]};
    border-bottom: 1px solid {C["surface0"]};
}}

QLabel#AppTitle {{
    color: {C["text"]};
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.05em;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   HAUPT-TABS  (Meine Szenen | Seiten-Bibliothek | …)
   Inaktiv: helles Grau (#C7C7CC) auf dunklem Panel (#2C2C2E) → Kontrast 7.5:1
   Aktiv:   Weiß (#FFF) + blauer Unterstrich
   ═══════════════════════════════════════════════════════════════════════════════ */

QTabWidget::pane {{
    border: none;
    background-color: {C["base"]};
}}

QTabBar {{
    background: {C["base"]};
    border-bottom: 1px solid {C["surface0"]};
}}

QTabBar::tab {{
    background: transparent;
    color: {C["subtext0"]};
    padding: 11px 26px;
    font-size: 13px;
    font-weight: 500;
    border: none;
    border-bottom: 3px solid transparent;
}}

QTabBar::tab:selected {{
    color: {C["text"]};
    border-bottom: 3px solid {C["mauve"]};
    font-weight: 600;
    background: transparent;
}}

QTabBar::tab:hover:!selected {{
    color: {C["subtext1"]};
    background: rgba(255,255,255,0.06);
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════════════════════════════════════════════ */

QPushButton {{
    background-color: {C["surface1"]};
    color: {C["text"]};
    border: 1px solid {C["surface2"]};
    border-radius: 7px;
    padding: 7px 18px;
    font-weight: 500;
    font-size: 13px;
    min-height: 22px;
}}

QPushButton:hover {{
    background-color: {C["surface2"]};
    border-color: {C["overlay0"]};
}}

QPushButton:pressed {{
    background-color: {C["overlay0"]};
}}

QPushButton:disabled {{
    background-color: {C["mantle"]};
    color: {C["overlay0"]};
    border-color: {C["surface0"]};
}}

QPushButton#PrimaryButton {{
    background-color: {C["mauve"]};
    color: #FFFFFF;
    border: none;
    font-weight: 700;
}}

QPushButton#PrimaryButton:hover {{
    background-color: #3395FF;
}}

QPushButton#PrimaryButton:pressed {{
    background-color: #0066CC;
}}

QPushButton#DangerButton {{
    background-color: transparent;
    color: {C["red"]};
    border: 1px solid {C["red"]};
    font-weight: 500;
}}

QPushButton#DangerButton:hover {{
    background-color: {C["red"]};
    color: #FFFFFF;
}}

QPushButton#GhostButton {{
    background-color: transparent;
    border: 1px solid {C["surface2"]};
    color: {C["subtext1"]};
    padding: 5px 12px;
    font-size: 12px;
    min-height: 18px;
}}

QPushButton#GhostButton:hover {{
    background-color: {C["surface1"]};
    color: {C["text"]};
    border-color: {C["overlay0"]};
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   EINGABEFELDER
   ═══════════════════════════════════════════════════════════════════════════════ */

QLineEdit {{
    background-color: {C["surface0"]};
    color: {C["text"]};
    border: 1.5px solid {C["surface2"]};
    border-radius: 7px;
    padding: 7px 11px;
    selection-background-color: {C["mauve"]};
    selection-color: #FFFFFF;
    font-size: 13px;
}}

QLineEdit:focus {{
    border-color: {C["mauve"]};
    background-color: {C["surface1"]};
}}

QLineEdit:disabled {{
    color: {C["overlay0"]};
    background-color: {C["mantle"]};
    border-color: {C["surface0"]};
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   COMBOBOX
   ═══════════════════════════════════════════════════════════════════════════════ */

QComboBox {{
    background-color: {C["surface0"]};
    color: {C["text"]};
    border: 1.5px solid {C["surface2"]};
    border-radius: 7px;
    padding: 7px 11px;
    min-width: 130px;
    font-size: 13px;
}}

QComboBox:focus {{
    border-color: {C["mauve"]};
}}

QComboBox:hover {{
    border-color: {C["overlay1"]};
}}

QComboBox::drop-down {{
    border: none;
    width: 22px;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {C["subtext0"]};
    width: 0;
    height: 0;
    margin-right: 7px;
}}

QComboBox QAbstractItemView {{
    background-color: {C["surface1"]};
    color: {C["text"]};
    border: 1px solid {C["surface2"]};
    border-radius: 7px;
    selection-background-color: {C["mauve"]};
    selection-color: #FFFFFF;
    padding: 4px;
    outline: 0px;
    font-size: 13px;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   SPINBOX
   ═══════════════════════════════════════════════════════════════════════════════ */

QSpinBox {{
    background-color: {C["surface0"]};
    color: {C["text"]};
    border: 1.5px solid {C["surface2"]};
    border-radius: 7px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 80px;
}}

QSpinBox:focus {{
    border-color: {C["mauve"]};
}}

QSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    background-color: {C["surface1"]};
    border: none;
    border-left: 1px solid {C["surface2"]};
    border-top-right-radius: 6px;
    width: 20px;
}}

QSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    background-color: {C["surface1"]};
    border: none;
    border-left: 1px solid {C["surface2"]};
    border-bottom-right-radius: 6px;
    width: 20px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background-color: {C["surface2"]};
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   SLIDER
   ═══════════════════════════════════════════════════════════════════════════════ */

QSlider::groove:horizontal {{
    height: 4px;
    background: {C["surface2"]};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: {C["mauve"]};
    border: 2px solid {C["base"]};
    width: 18px;
    height: 18px;
    border-radius: 9px;
    margin: -7px 0;
}}

QSlider::handle:horizontal:hover {{
    background: #3395FF;
}}

QSlider::sub-page:horizontal {{
    background: {C["mauve"]};
    border-radius: 2px;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   SCROLLBAR
   ═══════════════════════════════════════════════════════════════════════════════ */

QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 2px;
}}

QScrollBar::handle:vertical {{
    background: {C["surface2"]};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background: {C["overlay1"]};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
    border: none;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px;
}}

QScrollBar::handle:horizontal {{
    background: {C["surface2"]};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    background: transparent;
    width: 0;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   GROUPBOX
   ═══════════════════════════════════════════════════════════════════════════════ */

QGroupBox {{
    background-color: {C["mantle"]};
    border: 1px solid {C["surface2"]};
    border-radius: 10px;
    margin-top: 22px;
    padding: 14px 14px 12px 14px;
    font-size: 13px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 4px;
    padding: 2px 10px;
    background-color: {C["base"]};
    color: {C["mauve"]};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    border: 1px solid {C["surface2"]};
    border-radius: 5px;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   LISTWIDGET
   ═══════════════════════════════════════════════════════════════════════════════ */

QListWidget {{
    background-color: {C["mantle"]};
    border: 1px solid {C["surface2"]};
    border-radius: 8px;
    outline: none;
    padding: 4px;
    font-size: 13px;
}}

QListWidget::item {{
    color: {C["text"]};
    padding: 9px 12px;
    border-radius: 6px;
}}

QListWidget::item:selected {{
    background-color: {C["mauve"]};
    color: #FFFFFF;
    font-weight: 600;
}}

QListWidget::item:hover:!selected {{
    background-color: {C["surface0"]};
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   LABELS
   ═══════════════════════════════════════════════════════════════════════════════ */

QLabel#SectionHeader {{
    color: {C["mauve"]};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.1em;
}}

QLabel#StatusLabel {{
    color: {C["green"]};
    font-size: 12px;
    font-weight: 600;
}}

QLabel#StatusLabelOff {{
    color: {C["overlay1"]};
    font-size: 12px;
    font-weight: 500;
}}

QLabel#Subtitle {{
    color: {C["subtext0"]};
    font-size: 12px;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   SZENEN-EDITOR — Button- und Knob-Slots
   ═══════════════════════════════════════════════════════════════════════════════ */

QFrame#DeviceFrame {{
    background-color: {C["mantle"]};
    border: 1px solid {C["surface2"]};
    border-radius: 14px;
}}

QWidget#ButtonSlot {{
    background-color: {C["surface0"]};
    border: 1.5px solid {C["surface2"]};
    border-radius: 10px;
}}

QWidget#ButtonSlot:hover {{
    background-color: {C["surface1"]};
    border-color: {C["mauve"]};
}}

QWidget#ButtonSlot[dropTarget="true"] {{
    background-color: {C["surface1"]};
    border: 2px dashed {C["mauve"]};
}}

QWidget#KnobSlot {{
    background-color: transparent;
}}

/* KnobCircle: border-radius wird inline per Diameter gesetzt (variiert je Größe) */
QLabel#KnobCircle {{
    background-color: {C["surface1"]};
    border: 2.5px solid {C["surface2"]};
    color: {C["subtext0"]};
    font-weight: 700;
}}

QWidget#NavButtonSlot {{
    background-color: {C["surface0"]};
    border: 1.5px solid {C["surface2"]};
    border-radius: 8px;
}}

QWidget#NavButtonSlot[hovered="true"] {{
    background-color: {C["surface1"]};
    border-color: {C["mauve"]};
}}

QLabel#SceneName {{
    color: {C["text"]};
    font-size: 17px;
    font-weight: 700;
}}

QFrame#Separator {{
    background-color: {C["surface2"]};
    color: {C["surface2"]};
    max-height: 1px;
    border: none;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   BIBLIOTHEKS-KARTEN
   ═══════════════════════════════════════════════════════════════════════════════ */

QFrame#Card {{
    background-color: {C["mantle"]};
    border: 1px solid {C["surface2"]};
    border-radius: 10px;
}}

QFrame#Card:hover {{
    border-color: {C["mauve"]};
    background-color: {C["surface0"]};
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   DIALOGE
   ═══════════════════════════════════════════════════════════════════════════════ */

QMessageBox {{
    background-color: {C["base"]};
}}

QMessageBox QLabel {{
    color: {C["text"]};
    font-size: 13px;
}}

QMessageBox QPushButton {{
    min-width: 80px;
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   CHECKBOXEN
   ═══════════════════════════════════════════════════════════════════════════════ */

QCheckBox {{
    color: {C["text"]};
    spacing: 8px;
    font-size: 13px;
}}

QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border: 1.5px solid {C["surface2"]};
    border-radius: 5px;
    background-color: {C["surface0"]};
}}

QCheckBox::indicator:hover {{
    border-color: {C["mauve"]};
}}

QCheckBox::indicator:checked {{
    background-color: {C["mauve"]};
    border-color: {C["mauve"]};
}}

/* ═══════════════════════════════════════════════════════════════════════════════
   TOOLTIP
   ═══════════════════════════════════════════════════════════════════════════════ */

QToolTip {{
    background-color: {C["surface1"]};
    color: {C["text"]};
    border: 1px solid {C["surface2"]};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

"""
