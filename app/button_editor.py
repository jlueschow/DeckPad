"""
ButtonEditorDialog  — vollständiger Editor für einen Button-Slot.
KnobEditorDialog    — Editor für einen Knob-Regler.
"""

import sys, os, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QComboBox, QPushButton, QGroupBox,
    QDialogButtonBox, QFileDialog, QWidget, QFrame, QSizePolicy,
    QStackedWidget, QSpinBox, QColorDialog, QScrollArea, QSplitter
)
from PySide6.QtCore import Qt, Signal, QSize, QThread
from PySide6.QtGui import QPixmap, QFont, QColor

from app.scene_widget import _icon_to_pixmap
from config.config_manager import cfg


# ── Action-Typen ───────────────────────────────────────────────────────────────

ACTION_TYPES = [
    ("open_app",       "App öffnen"),
    ("open_url",       "URL öffnen"),
    ("shortcut",       "Tastenkürzel"),
    ("shell",          "Terminal-Befehl"),
    ("dante_route",    "Dante Routing"),
    ("open_config",    "Einstellungen öffnen"),
    ("none",           "Keine Aktion"),
]

ICON_TYPES = [
    ("text",   "Text-Label"),
    ("emoji",  "Emoji + Text"),
    ("app",    "App-Icon"),
    ("file",   "Bilddatei"),
]

KNOB_ACTION_TYPES = [
    ("volume",         "Lautstärke"),
    ("brightness",     "Bildschirmhelligkeit"),
    ("shortcut_turn",  "Tastenkürzel (CW/CCW)"),
    ("scroll",         "Scrollen"),
    ("none",           "Keine Aktion"),
]

# Aktionstypen für den Knob-Druck (identisch mit Button-Aktionen, ohne Icon)
KNOB_PRESS_ACTION_TYPES = [
    ("shortcut",    "Tastenkürzel"),
    ("open_config", "Einstellungen öffnen"),
    ("open_app",    "App öffnen"),
    ("open_url",    "URL öffnen"),
    ("shell",       "Terminal-Befehl"),
    ("none",        "Keine Aktion"),
]

NAV_ACTION_TYPES = [
    ("scene_prev",  "Vorherige Szene"),
    ("scene_home",  "Erste Szene (Home)"),
    ("scene_next",  "Nächste Szene"),
    ("open_app",    "App öffnen"),
    ("open_url",    "URL öffnen"),
    ("shortcut",    "Tastenkürzel"),
    ("shell",       "Terminal-Befehl"),
    ("none",        "Keine Aktion"),
]


# ── Hilfsfunktionen ────────────────────────────────────────────────────────────

def _type_index(items: list, key: str, default: int = 0) -> int:
    for i, (k, _) in enumerate(items):
        if k == key:
            return i
    return default


# ── _DanteDeviceLoader ────────────────────────────────────────────────────────

class _DanteDeviceLoader(QThread):
    """
    Lädt die Dante-Geräteliste (TX- + RX-Kanäle) im Hintergrund-Thread.
    Kein Qt-Blocking auf dem Main-Thread.
    """
    devices_loaded = Signal(list)   # [{"name": str, "tx": [...], "rx": [...]}]
    load_failed    = Signal(str)    # Fehlermeldung

    def __init__(self, host: str, api_key: str, parent=None):
        super().__init__(parent)
        self._host    = host
        self._api_key = api_key

    def run(self):
        import urllib.request
        import urllib.error
        import json as _json

        if not self._host:
            self.load_failed.emit(
                "DDM-Host nicht konfiguriert — Einstellungen → Dante DDM."
            )
            return
        try:
            payload = _json.dumps({"query": (
                "{ domains { name devices { name "
                "txChannels { index name } "
                "rxChannels { index name subscribedDevice } } } }"
            )}).encode("utf-8")
            req = urllib.request.Request(
                f"{self._host.rstrip('/')}/graphql",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": self._api_key,
                    "User-Agent": "PostmanRuntime/7.45.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            if "errors" in data:
                self.load_failed.emit(data["errors"][0]["message"])
                return
            devices: list = []
            for domain in data.get("data", {}).get("domains", []):
                for dev in domain["devices"]:
                    devices.append({
                        "name": dev["name"],
                        "tx":   dev.get("txChannels", []),
                        "rx":   dev.get("rxChannels", []),
                    })
            self.devices_loaded.emit(devices)
        except urllib.error.URLError as e:
            self.load_failed.emit(f"DDM nicht erreichbar: {e.reason}")
        except Exception as e:
            self.load_failed.emit(str(e))


# ── _LibraryButtonCard ─────────────────────────────────────────────────────────

class _LibraryButtonCard(QFrame):
    """Kompaktes, klickbares Karten-Widget für die Button-Bibliothek im Editor."""

    clicked_assign = Signal(dict)

    _STYLE = (
        "QFrame { background: #2C2C2E; border: 1px solid #3A3A3C; border-radius: 8px; }"
        "QFrame:hover { background: #3A3A3C; border-color: #636366; }"
    )

    def __init__(self, btn: dict, parent=None):
        super().__init__(parent)
        self._btn = btn
        self.setFixedSize(76, 92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet(self._STYLE)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 6, 4, 4)
        lay.setSpacing(3)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Icon-Vorschau
        icon_lbl = QLabel()
        icon_lbl.setFixedSize(48, 48)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pm = _icon_to_pixmap(btn, size=44)
        icon_lbl.setPixmap(pm)
        lay.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        # Label
        text_lbl = QLabel(btn.get("label", ""))
        text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text_lbl.setWordWrap(True)
        text_lbl.setMaximumWidth(68)
        f = text_lbl.font()
        f.setPointSize(9)
        text_lbl.setFont(f)
        lay.addWidget(text_lbl, 0, Qt.AlignmentFlag.AlignCenter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_assign.emit(self._btn)
        super().mousePressEvent(event)


# ── ButtonEditorDialog ─────────────────────────────────────────────────────────

class ButtonEditorDialog(QDialog):
    """
    Vollständiger Dialog zum Bearbeiten eines Button-Slots.
    Gibt geänderte btn_data über .result_data zurück (wenn Accepted).
    """

    def __init__(self, btn_data: dict, parent=None):
        super().__init__(parent)
        self._original = btn_data
        self._data = copy.deepcopy(btn_data)
        self.result_data = None

        self.setWindowTitle(f"Button {btn_data.get('index', '?')} bearbeiten")
        self.setMinimumSize(840, 480)
        self.setModal(True)
        self._loading = False   # Verhindert Auto-Browser beim Laden bestehender Daten
        self._setup_ui()
        self._load_data()
        self._fit_to_content()

    def _setup_ui(self):
        # Äußeres Layout: Scroll-Bereich + feste Button-Leiste unten
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Scrollbarer Content-Bereich ──────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._scroll_content = QWidget()
        content_w = self._scroll_content
        content = QVBoxLayout(content_w)
        content.setSpacing(20)
        content.setContentsMargins(24, 24, 24, 16)

        # ── Vorschau ──
        preview_row = QHBoxLayout()
        self._preview_lbl = QLabel()
        self._preview_lbl.setFixedSize(76, 76)
        self._preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_lbl.setStyleSheet(
            "background: #3A3A3C; border: 1px solid #636366; border-radius: 8px;"
        )
        preview_row.addWidget(self._preview_lbl)
        preview_row.addSpacing(16)

        title_col = QVBoxLayout()
        title_lbl = QLabel("Button bearbeiten")
        f = QFont(); f.setPointSize(15); f.setBold(True)
        title_lbl.setFont(f)
        slot_lbl = QLabel(f"Slot {self._data.get('index', '?')}")
        slot_lbl.setStyleSheet("color: #AEAEB2; font-size: 12px;")
        title_col.addWidget(title_lbl)
        title_col.addWidget(slot_lbl)
        title_col.addStretch()
        preview_row.addLayout(title_col)
        preview_row.addStretch()
        content.addLayout(preview_row)

        # ── Label ──
        grp_label = QGroupBox("Beschriftung")
        gl = QFormLayout(grp_label)
        gl.setSpacing(10)
        self._label_edit = QLineEdit()
        # NoFontMerging: gleiche Absicherung wie _emoji_edit — verhindert Crash via
        # CoreText → Apple Color Emoji → PNGReadPlugin (EXC_ARM_DA_ALIGN, macOS 26.3.1).
        _lf = self._label_edit.font()
        _lf.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        self._label_edit.setFont(_lf)
        self._label_edit.setPlaceholderText("z. B. Chrome, Aufnahme, ...")
        self._label_edit.textChanged.connect(self._on_label_changed)
        gl.addRow("Label:", self._label_edit)
        content.addWidget(grp_label)

        # ── Aktion ── (vor dem Icon-Bereich)
        grp_action = QGroupBox("Aktion")
        ga = QVBoxLayout(grp_action)
        ga.setSpacing(12)

        action_type_row = QHBoxLayout()
        action_type_row.addWidget(QLabel("Typ:"))
        self._action_combo = QComboBox()
        for key, name in ACTION_TYPES:
            self._action_combo.addItem(name, key)
        self._action_combo.currentIndexChanged.connect(self._on_action_type_changed)
        action_type_row.addWidget(self._action_combo)
        action_type_row.addStretch()
        ga.addLayout(action_type_row)

        self._action_stack = QStackedWidget()

        # 0: open_app — Durchsuchen-Button öffnet App-Dialog und setzt Icon automatisch
        app_act_w = QWidget()
        app_act_l = QFormLayout(app_act_w)
        app_act_l.setSpacing(10)
        app_act_l.setContentsMargins(0, 4, 0, 4)
        self._act_app_name = QLineEdit()
        self._act_app_name.setPlaceholderText("Google Chrome")
        act_path_row = QHBoxLayout()
        self._act_app_path = QLineEdit()
        self._act_app_path.setPlaceholderText("/Applications/…")
        act_browse_btn = QPushButton("Durchsuchen…")
        act_browse_btn.setObjectName("GhostButton")
        act_browse_btn.clicked.connect(self._browse_for_open_app)
        act_path_row.addWidget(self._act_app_path)
        act_path_row.addWidget(act_browse_btn)
        app_act_l.addRow("App-Name:", self._act_app_name)
        app_act_l.addRow("App-Pfad:", act_path_row)
        self._action_stack.addWidget(app_act_w)

        # 1: open_url
        url_w = QWidget()
        url_l = QFormLayout(url_w)
        url_l.setSpacing(10)
        url_l.setContentsMargins(0, 4, 0, 4)
        self._act_url = QLineEdit()
        self._act_url.setPlaceholderText("https://…")
        url_l.addRow("URL:", self._act_url)
        self._action_stack.addWidget(url_w)

        # 2: shortcut
        sc_w = QWidget()
        sc_l = QFormLayout(sc_w)
        sc_l.setSpacing(10)
        sc_l.setContentsMargins(0, 4, 0, 4)
        self._act_keys = QLineEdit()
        self._act_keys.setPlaceholderText("cmd+shift+4")
        hint = QLabel("Modifier: cmd, shift, alt, ctrl — z. B. cmd+z, f12, space")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        sc_l.addRow("Tasten:", self._act_keys)
        sc_l.addRow("", hint)
        self._action_stack.addWidget(sc_w)

        # 3: shell
        sh_w = QWidget()
        sh_l = QFormLayout(sh_w)
        sh_l.setSpacing(10)
        sh_l.setContentsMargins(0, 4, 0, 4)
        self._act_cmd = QLineEdit()
        self._act_cmd.setPlaceholderText("echo 'Hallo'")
        sh_l.addRow("Befehl:", self._act_cmd)
        self._action_stack.addWidget(sh_w)

        # 4: dante_route — Mehrfach-Routen-Tabelle
        dante_w = QWidget()
        dante_outer = QVBoxLayout(dante_w)
        dante_outer.setContentsMargins(0, 4, 0, 4)
        dante_outer.setSpacing(6)

        # Status + Refresh
        dante_top = QHBoxLayout()
        self._dante_status_lbl = QLabel("Geräte werden geladen…")
        self._dante_status_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        _dante_refresh_btn = QPushButton("Aktualisieren")
        _dante_refresh_btn.setObjectName("GhostButton")
        _dante_refresh_btn.setFixedWidth(110)
        _dante_refresh_btn.clicked.connect(self._dante_load_devices)
        dante_top.addWidget(self._dante_status_lbl)
        dante_top.addStretch()
        dante_top.addWidget(_dante_refresh_btn)
        dante_outer.addLayout(dante_top)

        # Spalten-Header — gleiche Stretch-Gewichte wie die Zeilen (3-2-3-2 + 26 del)
        _hdr = QWidget()
        _hdr_l = QHBoxLayout(_hdr)
        _hdr_l.setContentsMargins(2, 0, 30, 0)
        _hdr_l.setSpacing(4)
        for _title, _stretch in [
            ("Empfänger-Gerät", 3), ("RX-Kanal", 2),
            ("Sender-Gerät",    3), ("TX-Kanal",  2),
        ]:
            _lbl = QLabel(_title)
            _lbl.setStyleSheet("color: #636366; font-size: 11px;")
            _hdr_l.addWidget(_lbl, _stretch)
        dante_outer.addWidget(_hdr)

        # Scrollbarer Zeilen-Container
        self._dante_routes_scroll = QScrollArea()
        self._dante_routes_scroll.setWidgetResizable(True)
        self._dante_routes_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._dante_routes_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._dante_routes_scroll.setFixedHeight(148)

        self._dante_rows_widget = QWidget()
        self._dante_rows_layout = QVBoxLayout(self._dante_rows_widget)
        self._dante_rows_layout.setContentsMargins(0, 0, 0, 0)
        self._dante_rows_layout.setSpacing(4)
        self._dante_rows_layout.addStretch()
        self._dante_routes_scroll.setWidget(self._dante_rows_widget)
        dante_outer.addWidget(self._dante_routes_scroll)

        # Hinzufügen-Button
        _add_btn = QPushButton("+ Route hinzufügen")
        _add_btn.setObjectName("GhostButton")
        _add_btn.clicked.connect(lambda: self._dante_add_route_row())
        dante_outer.addWidget(_add_btn)

        self._action_stack.addWidget(dante_w)

        # Laufzeit-State
        self._dante_devices:    list = []
        self._dante_pending:    dict = {}
        self._dante_loader:     _DanteDeviceLoader | None = None
        self._dante_route_rows: list = []   # [{"rx_dev":CB,"rx_ch":CB,"tx_dev":CB,"tx_ch":CB,"widget":QWidget}]

        # 5: open_config
        cfg_w = QWidget()
        cfg_l = QVBoxLayout(cfg_w)
        cfg_l.setContentsMargins(0, 4, 0, 4)
        cfg_l.addWidget(QLabel("Öffnet das Konfigurationsfenster der App."))
        self._action_stack.addWidget(cfg_w)

        # 6: none
        none_w = QWidget()
        none_l = QVBoxLayout(none_w)
        none_l.setContentsMargins(0, 4, 0, 4)
        none_l.addWidget(QLabel("Dieser Button hat keine Aktion."))
        self._action_stack.addWidget(none_w)

        ga.addWidget(self._action_stack)
        content.addWidget(grp_action)

        # ── Icon ── (nach dem Aktion-Bereich)
        grp_icon = QGroupBox("Icon")
        gi = QVBoxLayout(grp_icon)
        gi.setSpacing(12)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Typ:"))
        self._icon_type_combo = QComboBox()
        for key, name in ICON_TYPES:
            self._icon_type_combo.addItem(name, key)
        self._icon_type_combo.currentIndexChanged.connect(self._on_icon_type_changed)
        type_row.addWidget(self._icon_type_combo)
        type_row.addStretch()
        gi.addLayout(type_row)

        # Gestapelte Eingaben je nach Icon-Typ
        self._icon_stack = QStackedWidget()

        # Page 0: text — kein extra Feld
        text_page = QWidget()
        tl = QVBoxLayout(text_page)
        tl.setContentsMargins(0, 4, 0, 4)
        tl.addWidget(QLabel("Label wird als Text-Icon gerendert."))
        self._icon_stack.addWidget(text_page)

        # Page 1: emoji
        emoji_page = QWidget()
        el = QFormLayout(emoji_page)
        el.setSpacing(10)
        el.setContentsMargins(0, 4, 0, 4)
        self._emoji_edit = QLineEdit()
        # NoFontMerging: verhindert, dass Qt auf Apple Color Emoji (PNG-Glyphen) ausweicht.
        # Ohne dieses Flag crasht QLineEdit::paintEvent auf macOS 26.3.1 via
        # CoreText → CopyEmojiImage → PNGReadPlugin::InitializePluginData (EXC_ARM_DA_ALIGN).
        _ef = self._emoji_edit.font()
        _ef.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        self._emoji_edit.setFont(_ef)
        # Kein Emoji im Placeholder — ASCII bleibt sicher.
        self._emoji_edit.setPlaceholderText("Emoji einfuegen, z. B. aus Zeichentabelle")
        self._emoji_edit.textChanged.connect(self._update_preview)
        self._emoji_bg_btn = QPushButton()
        self._emoji_bg_btn.setFixedSize(32, 24)
        self._emoji_bg_btn.clicked.connect(self._pick_emoji_bg)
        self._emoji_bg_color = (30, 30, 40)
        self._update_bg_btn()
        bg_row = QHBoxLayout()
        bg_row.addWidget(self._emoji_bg_btn)
        bg_row.addWidget(QLabel("Hintergrundfarbe"))
        bg_row.addStretch()
        emoji_hint = QLabel("Emoji hier einfügen — Vorschau oben links.")
        emoji_hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        el.addRow("Emoji:", self._emoji_edit)
        el.addRow("", emoji_hint)
        el.addRow("Hintergrund:", bg_row)
        self._icon_stack.addWidget(emoji_page)

        # Page 2: app — für manuelle Icon-Auswahl / Auto-Übernahme aus Aktion
        app_icon_page = QWidget()
        al = QFormLayout(app_icon_page)
        al.setSpacing(10)
        al.setContentsMargins(0, 4, 0, 4)
        app_icon_row = QHBoxLayout()
        self._app_path_edit = QLineEdit()
        self._app_path_edit.setPlaceholderText("/Applications/MyApp.app")
        self._app_path_edit.textChanged.connect(self._update_preview)
        icon_browse_btn = QPushButton("Durchsuchen…")
        icon_browse_btn.setObjectName("GhostButton")
        icon_browse_btn.clicked.connect(self._browse_app_icon)
        app_icon_row.addWidget(self._app_path_edit)
        app_icon_row.addWidget(icon_browse_btn)
        al.addRow("App-Pfad:", app_icon_row)
        app_icon_hint = QLabel(
            "Funktioniert auch für System-Apps (Kalender, Notizen, …) — "
            "Icon wird beim ersten Auswählen automatisch extrahiert."
        )
        app_icon_hint.setWordWrap(True)
        app_icon_hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        al.addRow("", app_icon_hint)
        self._icon_stack.addWidget(app_icon_page)

        # Page 3: file
        file_page = QWidget()
        fl2 = QFormLayout(file_page)
        fl2.setSpacing(10)
        fl2.setContentsMargins(0, 4, 0, 4)
        file_row = QHBoxLayout()
        self._file_path_edit = QLineEdit()
        self._file_path_edit.setPlaceholderText("Pfad zur Bilddatei (PNG/ICNS/JPG)")
        self._file_path_edit.textChanged.connect(self._update_preview)
        browse_file_btn = QPushButton("Durchsuchen…")
        browse_file_btn.setObjectName("GhostButton")
        browse_file_btn.clicked.connect(self._browse_file)
        file_row.addWidget(self._file_path_edit)
        file_row.addWidget(browse_file_btn)
        fl2.addRow("Datei-Pfad:", file_row)
        self._icon_stack.addWidget(file_page)

        gi.addWidget(self._icon_stack)
        content.addWidget(grp_icon)
        content.addStretch()

        scroll.setWidget(content_w)

        # ── Splitter: Editor links | Button-Bibliothek rechts ─────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(scroll)
        self._splitter.addWidget(self._build_library_panel())
        self._splitter.setSizes([520, 300])
        root.addWidget(self._splitter, 1)

        # ── Feste Button-Leiste (immer sichtbar) ──────────────────────────────
        self._btn_area = QWidget()
        btn_area = self._btn_area
        btn_area_l = QVBoxLayout(btn_area)
        btn_area_l.setContentsMargins(24, 12, 24, 20)
        btn_area_l.setSpacing(12)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("Separator")
        btn_area_l.addWidget(sep)

        btn_box = QHBoxLayout()
        clear_btn = QPushButton("Slot leeren")
        clear_btn.setObjectName("DangerButton")
        clear_btn.clicked.connect(self._clear_slot)
        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(clear_btn)
        btn_box.addStretch()
        btn_box.addWidget(cancel_btn)
        btn_box.addWidget(save_btn)
        btn_area_l.addLayout(btn_box)

        root.addWidget(btn_area)

    # ── Größe anpassen ──

    def _fit_to_content(self):
        """
        Dialog so groß machen, dass kein Scrollen nötig ist.
        Maximale Höhe: 90 % des verfügbaren Bildschirms (Fallback für kleine Displays).
        """
        # Vollständige Inhaltshöhe: scroll-Content + feste Button-Leiste
        content_h = self._scroll_content.sizeHint().height()
        btn_h = self._btn_area.sizeHint().height()
        total_h = content_h + btn_h

        # Bildschirmhöhe ermitteln
        screen = self.screen()
        max_h = int(screen.availableGeometry().height() * 0.9) if screen else 900

        self.resize(self.width(), min(total_h, max_h))

    # ── Daten laden ──

    def _load_data(self):
        # _loading=True: verhindert dass _on_action_type_changed den App-Browser öffnet
        self._loading = True
        try:
            label = self._data.get("label", "")
            self._label_edit.setText(label)

            icon = self._data.get("icon") or {}
            itype = icon.get("type", "text")
            self._icon_type_combo.setCurrentIndex(_type_index(ICON_TYPES, itype))

            if itype == "emoji":
                self._emoji_edit.setText(icon.get("emoji", ""))
                bg = icon.get("bg", [30, 30, 40])
                self._emoji_bg_color = tuple(bg)
                self._update_bg_btn()
            elif itype == "app":
                self._app_path_edit.setText(icon.get("path", ""))
            elif itype == "file":
                self._file_path_edit.setText(icon.get("path", ""))

            action = self._data.get("action") or {}
            atype = action.get("type", "none") if action else "none"

            # dante_route: pending VOR setCurrentIndex setzen — das Signal
            # _on_action_type_changed startet den Loader sofort, er muss die
            # Werte schon vorfinden, bevor er _dante_restore_pending() aufruft.
            if atype == "dante_route":
                # Backward-Compat: altes Single-Route-Format → routes-Liste
                if "routes" in action:
                    routes = action["routes"]
                elif action.get("rx_device") or action.get("tx_device"):
                    routes = [{
                        "rx_device": action.get("rx_device", ""),
                        "rx_channel": action.get("rx_channel", 1),
                        "tx_device":  action.get("tx_device", ""),
                        "tx_channel": action.get("tx_channel", ""),
                    }]
                else:
                    routes = []
                self._dante_pending = {"routes": routes}

            self._action_combo.setCurrentIndex(_type_index(ACTION_TYPES, atype))
            # ↑ feuert _on_action_type_changed → startet Loader falls dante_route

            self._act_app_name.setText(action.get("name", ""))
            self._act_app_path.setText(action.get("path", "") or "")
            self._act_url.setText(action.get("url", ""))
            self._act_keys.setText(action.get("keys", ""))
            self._act_cmd.setText(action.get("command", ""))

            self._update_preview()
        finally:
            self._loading = False

    # ── Slots ──

    def _on_label_changed(self, text):
        self._data["label"] = text
        self._update_preview()

    def _on_icon_type_changed(self, idx):
        self._icon_stack.setCurrentIndex(idx)
        self._update_preview()

    def _on_action_type_changed(self, idx):
        prev_akey = ACTION_TYPES[self._action_stack.currentIndex()][0] \
            if 0 <= self._action_stack.currentIndex() < len(ACTION_TYPES) else ""
        self._action_stack.setCurrentIndex(idx)
        akey = ACTION_TYPES[idx][0]

        # Bei "App öffnen": automatisch App-Browser öffnen — aber nicht beim Laden
        if not self._loading and akey == "open_app":
            self._browse_for_open_app()
        # Bei "Dante Routing": Geräteliste laden (falls noch nicht geschehen)
        elif akey == "dante_route" and not self._dante_devices:
            self._dante_load_devices()

        # Dialog-Breite anpassen
        if akey == "dante_route" and prev_akey != "dante_route":
            self._set_wide_layout(True)
        elif prev_akey == "dante_route" and akey != "dante_route":
            self._set_wide_layout(False)

    def _set_wide_layout(self, wide: bool):
        """
        Wechselt zwischen Normal- (840 px) und Dante-Breite (1100 px).
        Passt auch die Splitter-Aufteilung an, damit der Editor-Bereich
        genug Platz für die 4-Spalten-Tabelle hat.
        """
        screen = self.screen()
        screen_w = screen.availableGeometry().width() if screen else 1440

        if wide:
            target_w = min(1100, int(screen_w * 0.88))
            self.setMinimumWidth(target_w)
            self.resize(target_w, self.height())
            lib_w = 220
            self._splitter.setSizes([target_w - lib_w - 6, lib_w])
        else:
            self.setMinimumWidth(840)
            self.resize(840, self.height())
            self._splitter.setSizes([520, 300])

    # ── Dante DDM — Laden ────────────────────────────────────────────────────

    def _dante_load_devices(self):
        """Startet den DDM-Geräte-Loader (Hintergrund-Thread, non-blocking)."""
        dante_cfg = cfg.get().get("dante", {})
        self._dante_status_lbl.setText("Geräte werden geladen…")
        self._dante_status_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        if self._dante_loader and self._dante_loader.isRunning():
            self._dante_loader.quit()
            self._dante_loader.wait(500)
        self._dante_loader = _DanteDeviceLoader(
            dante_cfg.get("host", ""), dante_cfg.get("api_key", ""), self
        )
        self._dante_loader.devices_loaded.connect(self._dante_on_devices_loaded)
        self._dante_loader.load_failed.connect(self._dante_on_load_failed)
        self._dante_loader.start()

    def _dante_on_devices_loaded(self, devices: list):
        self._dante_devices = devices
        rx_devs = [d for d in devices if d["rx"]]
        tx_devs = [d for d in devices if d["tx"]]

        # Bestehende Zeilen aktualisieren (falls schon vorhanden)
        for row in self._dante_route_rows:
            self._dante_repopulate_row(row)

        # Gespeicherte Routen restaurieren oder erste leere Zeile anlegen
        if self._dante_pending:
            self._dante_restore_pending()
        elif not self._dante_route_rows:
            self._dante_add_route_row()

        self._dante_status_lbl.setText(
            f"{len(rx_devs)} Empfänger, {len(tx_devs)} Sender geladen."
        )
        self._dante_status_lbl.setStyleSheet("color: #30D158; font-size: 11px;")

    def _dante_on_load_failed(self, msg: str):
        self._dante_status_lbl.setText(f"Fehler: {msg}")
        self._dante_status_lbl.setStyleSheet("color: #FF453A; font-size: 11px;")

    # ── Dante DDM — Zeilen-Verwaltung ────────────────────────────────────────

    def _dante_add_route_row(self, rx_dev_name="", rx_ch_val=None,
                              tx_dev_name="", tx_ch_name=""):
        """
        Fügt eine neue Route-Zeile hinzu.
        Ohne Argumente: Auto-Fill aus der letzten Zeile (nächsthöherer Kanal).
        """
        # Auto-Fill: letzte Zeile als Vorlage, nächsten Kanal wählen
        if not rx_dev_name and self._dante_route_rows:
            last = self._dante_route_rows[-1]
            rx_dev_name = last["rx_dev"].currentData() or ""
            tx_dev_name = last["tx_dev"].currentData() or ""
            last_rx_ch  = last["rx_ch"].currentData()
            last_tx_ch  = last["tx_ch"].currentData()
            rx_ch_val   = self._dante_next_rx_ch(rx_dev_name, last_rx_ch)
            tx_ch_name  = self._dante_next_tx_ch(tx_dev_name, last_tx_ch)

        # Widget für diese Zeile
        row_w = QWidget()
        row_l = QHBoxLayout(row_w)
        row_l.setContentsMargins(0, 0, 0, 0)
        row_l.setSpacing(4)

        rx_dev = QComboBox(); rx_dev.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        rx_ch  = QComboBox(); rx_ch.setSizePolicy(QSizePolicy.Policy.Expanding,  QSizePolicy.Policy.Fixed)
        tx_dev = QComboBox(); tx_dev.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        tx_ch  = QComboBox(); tx_ch.setSizePolicy(QSizePolicy.Policy.Expanding,  QSizePolicy.Policy.Fixed)

        del_btn = QPushButton("×")
        del_btn.setFixedSize(26, 26)
        del_btn.setStyleSheet(
            "QPushButton { color: #FF453A; background: transparent; "
            "border: 1px solid #3A3A3C; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background: #3A3A3C; }"
        )

        row_l.addWidget(rx_dev, 3)
        row_l.addWidget(rx_ch,  2)
        row_l.addWidget(tx_dev, 3)
        row_l.addWidget(tx_ch,  2)
        row_l.addWidget(del_btn)

        row = {
            "rx_dev": rx_dev, "rx_ch": rx_ch,
            "tx_dev": tx_dev, "tx_ch": tx_ch,
            "widget": row_w,
        }
        self._dante_route_rows.append(row)

        # Signals
        rx_dev.currentIndexChanged.connect(
            lambda idx, r=row: self._dante_on_row_rx_dev_changed(r, idx)
        )
        tx_dev.currentIndexChanged.connect(
            lambda idx, r=row: self._dante_on_row_tx_dev_changed(r, idx)
        )
        del_btn.clicked.connect(lambda _checked=False, r=row: self._dante_remove_row(r))

        # Vor dem Stretch einfügen
        stretch_pos = self._dante_rows_layout.count() - 1
        self._dante_rows_layout.insertWidget(stretch_pos, row_w)

        # Geräte eintragen (falls schon geladen)
        if self._dante_devices:
            for d in [d for d in self._dante_devices if d["rx"]]:
                rx_dev.addItem(d["name"], d["name"])
            for d in [d for d in self._dante_devices if d["tx"]]:
                tx_dev.addItem(d["name"], d["name"])

        # Gewünschte Werte setzen
        if rx_dev_name:
            i = rx_dev.findData(rx_dev_name)
            if i >= 0:
                rx_dev.setCurrentIndex(i)
        self._dante_on_row_rx_dev_changed(row, rx_dev.currentIndex())
        if rx_ch_val is not None:
            i = rx_ch.findData(rx_ch_val)
            if i >= 0:
                rx_ch.setCurrentIndex(i)

        if tx_dev_name:
            i = tx_dev.findData(tx_dev_name)
            if i >= 0:
                tx_dev.setCurrentIndex(i)
        self._dante_on_row_tx_dev_changed(row, tx_dev.currentIndex())
        if tx_ch_name:
            i = tx_ch.findData(tx_ch_name)
            if i >= 0:
                tx_ch.setCurrentIndex(i)

    def _dante_remove_row(self, row: dict):
        """Entfernt eine Route-Zeile."""
        if row in self._dante_route_rows:
            self._dante_route_rows.remove(row)
        row["widget"].deleteLater()

    def _dante_repopulate_row(self, row: dict):
        """Aktualisiert die Geräte-Combos einer Zeile nach dem Laden der Geräteliste."""
        cur = {
            "rx_dev": row["rx_dev"].currentData(),
            "rx_ch":  row["rx_ch"].currentData(),
            "tx_dev": row["tx_dev"].currentData(),
            "tx_ch":  row["tx_ch"].currentData(),
        }
        row["rx_dev"].blockSignals(True)
        row["rx_dev"].clear()
        for d in [d for d in self._dante_devices if d["rx"]]:
            row["rx_dev"].addItem(d["name"], d["name"])
        row["rx_dev"].blockSignals(False)

        row["tx_dev"].blockSignals(True)
        row["tx_dev"].clear()
        for d in [d for d in self._dante_devices if d["tx"]]:
            row["tx_dev"].addItem(d["name"], d["name"])
        row["tx_dev"].blockSignals(False)

        # Alte Auswahl wiederherstellen
        i = row["rx_dev"].findData(cur["rx_dev"])
        if i >= 0:
            row["rx_dev"].setCurrentIndex(i)
        self._dante_on_row_rx_dev_changed(row, row["rx_dev"].currentIndex())
        i = row["rx_ch"].findData(cur["rx_ch"])
        if i >= 0:
            row["rx_ch"].setCurrentIndex(i)

        i = row["tx_dev"].findData(cur["tx_dev"])
        if i >= 0:
            row["tx_dev"].setCurrentIndex(i)
        self._dante_on_row_tx_dev_changed(row, row["tx_dev"].currentIndex())
        i = row["tx_ch"].findData(cur["tx_ch"])
        if i >= 0:
            row["tx_ch"].setCurrentIndex(i)

    def _dante_on_row_rx_dev_changed(self, row: dict, idx: int):
        dev_name = row["rx_dev"].itemData(idx)
        dev = next((d for d in self._dante_devices if d["name"] == dev_name), None)
        row["rx_ch"].blockSignals(True)
        row["rx_ch"].clear()
        if dev:
            for ch in sorted(dev["rx"], key=lambda c: c["index"]):
                busy  = "  [belegt]" if ch.get("subscribedDevice") else ""
                row["rx_ch"].addItem(f"{ch['index']} — {ch['name']}{busy}", ch["index"])
        row["rx_ch"].blockSignals(False)

    def _dante_on_row_tx_dev_changed(self, row: dict, idx: int):
        dev_name = row["tx_dev"].itemData(idx)
        dev = next((d for d in self._dante_devices if d["name"] == dev_name), None)
        row["tx_ch"].blockSignals(True)
        row["tx_ch"].clear()
        if dev:
            for ch in sorted(dev["tx"], key=lambda c: c["index"]):
                row["tx_ch"].addItem(ch["name"], ch["name"])
        row["tx_ch"].blockSignals(False)

    def _dante_next_rx_ch(self, dev_name: str, last_idx) -> int:
        """Gibt den nächsthöheren RX-Kanalindex zurück (gleiche Sortierreihenfolge)."""
        dev = next((d for d in self._dante_devices if d["name"] == dev_name), None)
        if not dev or last_idx is None:
            return 1
        indices = sorted(ch["index"] for ch in dev["rx"])
        for i in indices:
            if i > last_idx:
                return i
        return last_idx  # kein höherer → letzten beibehalten

    def _dante_next_tx_ch(self, dev_name: str, last_name: str) -> str:
        """Gibt den nächsten TX-Kanal zurück (nach Position in der sortierten Liste)."""
        dev = next((d for d in self._dante_devices if d["name"] == dev_name), None)
        if not dev:
            return last_name
        names = [ch["name"] for ch in sorted(dev["tx"], key=lambda c: c["index"])]
        if last_name in names:
            pos = names.index(last_name)
            if pos + 1 < len(names):
                return names[pos + 1]
        return last_name

    def _dante_restore_pending(self):
        """Stellt alle Routen aus _dante_pending wieder her."""
        p = self._dante_pending
        if not p:
            return
        routes = p.get("routes", [])

        # Alle alten Zeilen entfernen
        for row in list(self._dante_route_rows):
            self._dante_route_rows.remove(row)
            row["widget"].deleteLater()

        # Neue Zeilen aus gespeicherten Routen
        for route in routes:
            self._dante_add_route_row(
                rx_dev_name=route.get("rx_device", ""),
                rx_ch_val=route.get("rx_channel", 1),
                tx_dev_name=route.get("tx_device", ""),
                tx_ch_name=route.get("tx_channel", ""),
            )

        if not routes:
            self._dante_add_route_row()  # mind. eine leere Zeile

        self._dante_pending = {}

    def _browse_for_open_app(self):
        """
        App-Dialog aus dem Aktion-Bereich.
        Setzt Aktion-Felder UND übernimmt das App-Icon automatisch in den Icon-Bereich.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "App auswählen", "/Applications",
            "Apps (*.app);;Alle Dateien (*)"
        )
        if not path:
            return

        # Bundle-Root sicherstellen
        if ".app/" in path or (not path.endswith(".app") and ".app" in path):
            path = path.split(".app")[0] + ".app"

        app_name = os.path.basename(path).replace(".app", "")

        # Aktion-Felder befüllen
        self._act_app_path.setText(path)
        if not self._act_app_name.text():
            self._act_app_name.setText(app_name)

        # Label auto-befüllen wenn noch leer
        if not self._label_edit.text():
            self._label_edit.setText(app_name)

        # Icon automatisch auf App-Icon setzen
        self._auto_set_app_icon(path)

    def _auto_set_app_icon(self, app_path: str):
        """
        Setzt Icon-Typ auf 'App-Icon' und den Pfad.
        Kann vom Benutzer danach im Icon-Bereich manuell überschrieben werden.
        """
        app_icon_idx = _type_index(ICON_TYPES, "app")
        # Signals kurz blockieren damit nicht _update_preview doppelt feuert
        self._icon_type_combo.blockSignals(True)
        self._icon_type_combo.setCurrentIndex(app_icon_idx)
        self._icon_stack.setCurrentIndex(app_icon_idx)
        self._icon_type_combo.blockSignals(False)
        # Pfad setzen — triggert textChanged → _update_preview
        self._app_path_edit.setText(app_path)

    def _browse_app_icon(self):
        """
        Manueller Icon-Override aus dem Icon-Bereich.
        Öffnet App-Browser nur für den Icon-Pfad — ändert die Aktion NICHT.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, "App für Icon auswählen", "/Applications",
            "Apps (*.app);;Alle Dateien (*)"
        )
        if not path:
            return
        if ".app/" in path or (not path.endswith(".app") and ".app" in path):
            path = path.split(".app")[0] + ".app"
        self._app_path_edit.setText(path)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Bild auswählen", os.path.expanduser("~"),
            "Bilder (*.png *.jpg *.jpeg *.icns);;Alle Dateien (*)"
        )
        if path:
            self._file_path_edit.setText(path)

    def _pick_emoji_bg(self):
        r, g, b = self._emoji_bg_color
        initial = QColor(r, g, b)
        color = QColorDialog.getColor(initial, self, "Hintergrundfarbe wählen")
        if color.isValid():
            self._emoji_bg_color = (color.red(), color.green(), color.blue())
            self._update_bg_btn()
            self._update_preview()

    def _update_bg_btn(self):
        r, g, b = self._emoji_bg_color
        self._emoji_bg_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); "
            f"border: 1px solid #636366; border-radius: 4px;"
        )

    def _update_preview(self):
        """Baut temporäre btn_data für Vorschau."""
        tmp = self._build_data()
        pm = _icon_to_pixmap(tmp, size=70)
        self._preview_lbl.setPixmap(pm)

    def _build_data(self) -> dict:
        """Sammelt aktuelle Formular-Werte in btn_data dict."""
        data = copy.deepcopy(self._data)
        data["label"] = self._label_edit.text()

        itype_key = self._icon_type_combo.currentData()
        if itype_key == "emoji":
            data["icon"] = {
                "type": "emoji",
                "emoji": self._emoji_edit.text(),
                "bg": list(self._emoji_bg_color),
            }
        elif itype_key == "app":
            data["icon"] = {"type": "app", "path": self._app_path_edit.text()}
        elif itype_key == "file":
            data["icon"] = {"type": "file", "path": self._file_path_edit.text()}
        else:
            data["icon"] = {"type": "text"}

        atype_key = self._action_combo.currentData()
        if atype_key == "open_app":
            data["action"] = {
                "type": "open_app",
                "name": self._act_app_name.text(),
                "path": self._act_app_path.text() or None,
            }
        elif atype_key == "open_url":
            data["action"] = {"type": "open_url", "url": self._act_url.text()}
        elif atype_key == "shortcut":
            data["action"] = {"type": "shortcut", "keys": self._act_keys.text()}
        elif atype_key == "shell":
            data["action"] = {"type": "shell", "command": self._act_cmd.text()}
        elif atype_key == "dante_route":
            data["action"] = {
                "type": "dante_route",
                "routes": [
                    {
                        "rx_device": r["rx_dev"].currentData() or "",
                        "rx_channel": r["rx_ch"].currentData() or 1,
                        "tx_device":  r["tx_dev"].currentData() or "",
                        "tx_channel": r["tx_ch"].currentData() or "",
                    }
                    for r in self._dante_route_rows
                ],
            }
        elif atype_key == "open_config":
            data["action"] = {"type": "open_config"}
        else:
            data["action"] = None

        return data

    def _save(self):
        self.result_data = self._build_data()
        self.accept()

    def _clear_slot(self):
        idx = self._data.get("index", 1)
        self.result_data = {"index": idx, "label": "", "icon": None, "action": None}
        self.accept()

    # ── Button-Bibliothek (rechte Seite) ─────────────────────────────────────

    def _build_library_panel(self) -> QWidget:
        """Erstellt das rechte Panel mit der Button-Bibliothek."""
        panel = QWidget()
        panel.setMinimumWidth(240)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(10)

        title = QLabel("Button-Bibliothek")
        f = QFont(); f.setPointSize(12); f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)

        hint = QLabel("Klicken zum Übernehmen")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        lay.addWidget(hint)

        # Kategorie-Auswahl
        self._lib_cat_combo = QComboBox()
        lib_data = cfg.load_buttons()
        self._lib_categories = lib_data.get("categories", [])
        for cat in self._lib_categories:
            self._lib_cat_combo.addItem(cat.get("name", ""), cat.get("id", ""))
        self._lib_cat_combo.currentIndexChanged.connect(self._on_lib_category_changed)
        lay.addWidget(self._lib_cat_combo)

        # Scroll-Bereich für Button-Karten
        self._lib_scroll = QScrollArea()
        self._lib_scroll.setWidgetResizable(True)
        self._lib_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._lib_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._lib_grid_w = QWidget()
        self._lib_grid = QGridLayout(self._lib_grid_w)
        self._lib_grid.setSpacing(8)
        self._lib_grid.setContentsMargins(4, 4, 4, 4)
        self._lib_grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._lib_scroll.setWidget(self._lib_grid_w)
        lay.addWidget(self._lib_scroll, 1)

        # Erste Kategorie sofort laden
        if self._lib_categories:
            self._on_lib_category_changed(0)

        return panel

    def _on_lib_category_changed(self, idx: int):
        """Leert das Grid und befüllt es mit den Buttons der gewählten Kategorie."""
        while self._lib_grid.count():
            item = self._lib_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if idx < 0 or idx >= len(self._lib_categories):
            return

        buttons = self._lib_categories[idx].get("buttons", [])
        cols = 3
        for i, btn in enumerate(buttons):
            card = _LibraryButtonCard(btn, self._lib_grid_w)
            card.clicked_assign.connect(self._apply_library_button)
            self._lib_grid.addWidget(card, i // cols, i % cols)

    def _apply_library_button(self, btn: dict):
        """Übernimmt einen Bibliotheks-Button in den Editor (Label, Aktion, Icon)."""
        self._loading = True
        try:
            # Label
            self._label_edit.setText(btn.get("label", ""))

            # Aktion
            action = btn.get("action") or {}
            atype = action.get("type", "none")
            self._action_combo.setCurrentIndex(_type_index(ACTION_TYPES, atype))
            if atype == "open_app":
                self._act_app_name.setText(action.get("name", ""))
                self._act_app_path.setText(action.get("path", "") or "")
            elif atype == "open_url":
                self._act_url.setText(action.get("url", ""))
            elif atype == "shortcut":
                self._act_keys.setText(action.get("keys", ""))
            elif atype == "shell":
                self._act_cmd.setText(action.get("command", ""))
            elif atype == "dante_route":
                if "routes" in action:
                    routes = action["routes"]
                elif action.get("rx_device"):
                    routes = [{
                        "rx_device": action.get("rx_device", ""),
                        "rx_channel": action.get("rx_channel", 1),
                        "tx_device":  action.get("tx_device", ""),
                        "tx_channel": action.get("tx_channel", ""),
                    }]
                else:
                    routes = []
                self._dante_pending = {"routes": routes}
                if self._dante_devices:
                    self._dante_restore_pending()
                # Andernfalls restauriert _dante_on_devices_loaded nach dem Laden

            # Icon
            icon = btn.get("icon") or {}
            itype = icon.get("type", "text")
            self._icon_type_combo.setCurrentIndex(_type_index(ICON_TYPES, itype))
            if itype == "emoji":
                self._emoji_edit.setText(icon.get("emoji", ""))
                bg = icon.get("bg", [30, 30, 40])
                self._emoji_bg_color = tuple(bg)
                self._update_bg_btn()
            elif itype == "app":
                self._app_path_edit.setText(icon.get("path", ""))
            elif itype == "file":
                self._file_path_edit.setText(icon.get("path", ""))
        finally:
            self._loading = False

        self._update_preview()


# ── KnobEditorDialog ───────────────────────────────────────────────────────────

class KnobEditorDialog(QDialog):
    """Dialog zum Bearbeiten eines Knob-Reglers."""

    def __init__(self, knob_data: dict, parent=None):
        super().__init__(parent)
        self._data = copy.deepcopy(knob_data)
        self.result_data = None

        self.setWindowTitle(f"Knob {knob_data.get('index', '?')} bearbeiten")
        self.setMinimumSize(700, 380)
        self.setModal(True)
        self._setup_ui()
        self._load_data()
        self._fit_to_content()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Splitter: Editor links | Bibliothek rechts ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Linke Seite: Editor-Inhalt in ScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._scroll_content = QWidget()
        content_w = self._scroll_content
        content = QVBoxLayout(content_w)
        content.setSpacing(12)
        content.setContentsMargins(20, 20, 20, 12)

        # Titel
        title = QLabel(f"Knob {self._data.get('index', '?')} bearbeiten")
        f = QFont(); f.setPointSize(14); f.setBold(True)
        title.setFont(f)
        content.addWidget(title)

        # Label
        grp = QGroupBox("Beschriftung")
        gl = QFormLayout(grp)
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("z. B. Lautstärke, Helligkeit, …")
        gl.addRow("Label:", self._label_edit)
        content.addWidget(grp)

        # ── Dreh-Aktion ──────────────────────────────────────────────────────
        grp_action = QGroupBox("Aktion (Drehen)")
        ga = QVBoxLayout(grp_action)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Typ:"))
        self._action_combo = QComboBox()
        for key, name in KNOB_ACTION_TYPES:
            self._action_combo.addItem(name, key)
        self._action_combo.currentIndexChanged.connect(self._on_action_type_changed)
        type_row.addWidget(self._action_combo)
        type_row.addStretch()
        ga.addLayout(type_row)

        self._action_stack = QStackedWidget()

        # 0: volume
        vol_w = QWidget()
        vol_l = QVBoxLayout(vol_w)
        vol_l.addWidget(QLabel("Drehen: Systemlautstärke erhöhen / verringern\n"
                                "(mit nativer macOS-OSD-Anzeige)"))
        self._action_stack.addWidget(vol_w)

        # 1: brightness
        br_w = QWidget()
        br_l = QVBoxLayout(br_w)
        br_l.addWidget(QLabel("Drehen: Bildschirmhelligkeit erhöhen / verringern\n"
                               "(mit nativer macOS-OSD-Anzeige)"))
        self._action_stack.addWidget(br_w)

        # 2: shortcut_turn
        sc_w = QWidget()
        sc_l = QFormLayout(sc_w)
        self._key_cw  = QLineEdit(); self._key_cw.setPlaceholderText("right / equal / …")
        self._key_ccw = QLineEdit(); self._key_ccw.setPlaceholderText("left / minus / …")
        hint = QLabel("Modifier: cmd, shift, alt, ctrl")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        sc_l.addRow("CW  (→):", self._key_cw)
        sc_l.addRow("CCW (←):", self._key_ccw)
        sc_l.addRow("", hint)
        self._action_stack.addWidget(sc_w)

        # 3: scroll
        scr_w = QWidget()
        scr_l = QFormLayout(scr_w)
        self._scroll_axis = QComboBox()
        self._scroll_axis.addItem("Vertikal",    "vertical")
        self._scroll_axis.addItem("Horizontal",  "horizontal")
        scr_l.addRow("Richtung:", self._scroll_axis)
        self._scroll_speed = QSpinBox()
        self._scroll_speed.setRange(1, 10)
        self._scroll_speed.setValue(3)
        self._scroll_speed.setSuffix("  (1 = langsam, 10 = schnell)")
        scr_l.addRow("Geschwindigkeit:", self._scroll_speed)
        self._action_stack.addWidget(scr_w)

        # 4: none
        none_w = QWidget()
        none_l = QVBoxLayout(none_w)
        none_l.addWidget(QLabel("Dieser Knob hat keine Aktion."))
        self._action_stack.addWidget(none_w)

        ga.addWidget(self._action_stack)
        content.addWidget(grp_action)

        # ── Drücken-Aktion ────────────────────────────────────────────────────
        grp_press = QGroupBox("Drücken (Knob-Klick)")
        gp = QVBoxLayout(grp_press)

        press_hint = QLabel("Aus der Bibliothek wählen oder manuell konfigurieren:")
        press_hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        gp.addWidget(press_hint)

        press_type_row = QHBoxLayout()
        press_type_row.addWidget(QLabel("Typ:"))
        self._press_combo = QComboBox()
        for key, name in KNOB_PRESS_ACTION_TYPES:
            self._press_combo.addItem(name, key)
        self._press_combo.currentIndexChanged.connect(self._on_press_type_changed)
        press_type_row.addWidget(self._press_combo)
        press_type_row.addStretch()
        gp.addLayout(press_type_row)

        self._press_stack = QStackedWidget()

        # 0: shortcut
        ps_sc = QWidget()
        ps_sc_l = QFormLayout(ps_sc)
        self._press_keys = QLineEdit()
        self._press_keys.setPlaceholderText("z. B. cmd+m, space, f5 …")
        ps_sc_l.addRow("Kürzel:", self._press_keys)
        self._press_stack.addWidget(ps_sc)

        # 1: open_config
        ps_cfg = QWidget()
        ps_cfg_l = QVBoxLayout(ps_cfg)
        ps_cfg_l.addWidget(QLabel("Öffnet das DeckPad-Konfigurationsfenster."))
        self._press_stack.addWidget(ps_cfg)

        # 2: open_app
        ps_app = QWidget()
        ps_app_l = QFormLayout(ps_app)
        self._press_app = QLineEdit()
        self._press_app.setPlaceholderText("App-Name oder Pfad zur .app …")
        ps_app_l.addRow("App:", self._press_app)
        self._press_stack.addWidget(ps_app)

        # 3: open_url
        ps_url = QWidget()
        ps_url_l = QFormLayout(ps_url)
        self._press_url = QLineEdit()
        self._press_url.setPlaceholderText("https://…")
        ps_url_l.addRow("URL:", self._press_url)
        self._press_stack.addWidget(ps_url)

        # 4: shell
        ps_sh = QWidget()
        ps_sh_l = QFormLayout(ps_sh)
        self._press_shell = QLineEdit()
        self._press_shell.setPlaceholderText("z. B. open ~/Downloads")
        ps_sh_l.addRow("Befehl:", self._press_shell)
        self._press_stack.addWidget(ps_sh)

        # 5: none
        ps_none = QWidget()
        ps_none_l = QVBoxLayout(ps_none)
        ps_none_l.addWidget(QLabel("Kein Druck-Ereignis konfiguriert."))
        self._press_stack.addWidget(ps_none)

        gp.addWidget(self._press_stack)
        content.addWidget(grp_press)
        content.addStretch()

        scroll.setWidget(content_w)
        splitter.addWidget(scroll)
        splitter.addWidget(self._build_library_panel())
        splitter.setSizes([420, 280])
        root.addWidget(splitter, 1)

        # ── Feste Button-Leiste ───────────────────────────────────────────────
        self._btn_area = QWidget()
        btn_area = self._btn_area
        btn_area_l = QVBoxLayout(btn_area)
        btn_area_l.setContentsMargins(20, 12, 20, 16)
        btn_area_l.setSpacing(12)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("Separator")
        btn_area_l.addWidget(sep)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        btn_area_l.addLayout(btn_row)

        root.addWidget(btn_area)

    # ── Größe anpassen ────────────────────────────────────────────────────────

    def _fit_to_content(self):
        """
        Dialog so groß machen, dass der Editor-Inhalt ohne Scrollen sichtbar ist.
        Maximale Höhe: 90 % des verfügbaren Bildschirms — Fallback für kleine Displays.
        """
        content_h = self._scroll_content.sizeHint().height()
        btn_h     = self._btn_area.sizeHint().height()
        total_h   = content_h + btn_h

        screen = self.screen()
        max_h = int(screen.availableGeometry().height() * 0.9) if screen else 900
        self.resize(self.width(), min(total_h, max_h))

    # ── Button-Bibliothek (rechte Seite) ──────────────────────────────────────

    def _build_library_panel(self) -> QWidget:
        """Rechtes Panel mit der Button-Bibliothek — Klick übernimmt Druck-Aktion."""
        panel = QWidget()
        panel.setMinimumWidth(220)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 16, 12, 12)
        lay.setSpacing(10)

        title = QLabel("Button-Bibliothek")
        f = QFont(); f.setPointSize(12); f.setBold(True)
        title.setFont(f)
        lay.addWidget(title)

        hint = QLabel("Klicken → Druck-Aktion übernehmen")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        lay.addWidget(hint)

        self._lib_cat_combo = QComboBox()
        lib_data = cfg.load_buttons()
        self._lib_categories = lib_data.get("categories", [])
        for cat in self._lib_categories:
            self._lib_cat_combo.addItem(cat.get("name", ""), cat.get("id", ""))
        self._lib_cat_combo.currentIndexChanged.connect(self._on_lib_category_changed)
        lay.addWidget(self._lib_cat_combo)

        self._lib_scroll = QScrollArea()
        self._lib_scroll.setWidgetResizable(True)
        self._lib_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._lib_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._lib_grid_w = QWidget()
        self._lib_grid = QGridLayout(self._lib_grid_w)
        self._lib_grid.setSpacing(8)
        self._lib_grid.setContentsMargins(4, 4, 4, 4)
        self._lib_grid.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )
        self._lib_scroll.setWidget(self._lib_grid_w)
        lay.addWidget(self._lib_scroll, 1)

        if self._lib_categories:
            self._on_lib_category_changed(0)

        return panel

    def _on_lib_category_changed(self, idx: int):
        """Leert das Grid und befüllt es mit den Buttons der gewählten Kategorie."""
        while self._lib_grid.count():
            item = self._lib_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if idx < 0 or idx >= len(self._lib_categories):
            return

        buttons = self._lib_categories[idx].get("buttons", [])
        cols = 3
        for i, btn in enumerate(buttons):
            card = _LibraryButtonCard(btn, self._lib_grid_w)
            card.clicked_assign.connect(self._apply_library_press_action)
            self._lib_grid.addWidget(card, i // cols, i % cols)

    def _apply_library_press_action(self, btn: dict):
        """Übernimmt die Aktion eines Bibliotheks-Buttons als Druck-Aktion des Knobs."""
        action = btn.get("action") or {}
        atype = action.get("type", "none")
        self._press_combo.setCurrentIndex(_type_index(KNOB_PRESS_ACTION_TYPES, atype))
        if atype == "shortcut":
            self._press_keys.setText(action.get("keys", ""))
        elif atype == "open_app":
            app_display = action.get("path") or action.get("name", "")
            self._press_app.setText(app_display or "")
        elif atype == "open_url":
            self._press_url.setText(action.get("url", ""))
        elif atype == "shell":
            self._press_shell.setText(action.get("command", ""))

    def _load_data(self):
        self._label_edit.setText(self._data.get("label", ""))
        action = self._data.get("action") or {}
        atype = action.get("type", "none") if action else "none"
        self._action_combo.setCurrentIndex(_type_index(KNOB_ACTION_TYPES, atype))
        self._key_cw.setText(action.get("key_cw", ""))
        self._key_ccw.setText(action.get("key_ccw", ""))
        # Scroll-Felder
        axis = action.get("axis", "vertical")
        self._scroll_axis.setCurrentIndex(0 if axis == "vertical" else 1)
        self._scroll_speed.setValue(int(action.get("speed", 3)))

        # Druck-Aktion laden
        press_action = self._data.get("press_action") or {}
        pa_type = press_action.get("type", "none") if press_action else "none"
        self._press_combo.setCurrentIndex(_type_index(KNOB_PRESS_ACTION_TYPES, pa_type))
        self._press_keys.setText(press_action.get("keys", ""))
        # open_app: Pfad bevorzugen, sonst Name anzeigen
        app_display = press_action.get("path") or press_action.get("name", "")
        self._press_app.setText(app_display or "")
        self._press_url.setText(press_action.get("url", ""))
        self._press_shell.setText(press_action.get("command", ""))

    def _on_action_type_changed(self, idx):
        self._action_stack.setCurrentIndex(idx)

    def _on_press_type_changed(self, idx):
        self._press_stack.setCurrentIndex(idx)

    def _save(self):
        atype_key = self._action_combo.currentData()
        if atype_key == "volume":
            action = {"type": "volume"}
        elif atype_key == "brightness":
            action = {"type": "brightness"}
        elif atype_key == "shortcut_turn":
            action = {
                "type": "shortcut_turn",
                "key_cw":  self._key_cw.text(),
                "key_ccw": self._key_ccw.text(),
            }
        elif atype_key == "scroll":
            action = {
                "type":  "scroll",
                "axis":  self._scroll_axis.currentData(),
                "speed": self._scroll_speed.value(),
            }
        else:
            action = None

        # Druck-Aktion
        ptype_key = self._press_combo.currentData()
        if ptype_key == "shortcut":
            press_action = {"type": "shortcut", "keys": self._press_keys.text()}
        elif ptype_key == "open_config":
            press_action = {"type": "open_config"}
        elif ptype_key == "open_app":
            app_val = self._press_app.text().strip()
            if app_val.startswith("/") or app_val.endswith(".app"):
                press_action = {
                    "type": "open_app",
                    "name": os.path.basename(app_val).replace(".app", ""),
                    "path": app_val,
                }
            else:
                press_action = {"type": "open_app", "name": app_val, "path": None}
        elif ptype_key == "open_url":
            press_action = {"type": "open_url", "url": self._press_url.text()}
        elif ptype_key == "shell":
            press_action = {"type": "shell", "command": self._press_shell.text()}
        else:
            press_action = None

        self.result_data = {
            "index":        self._data.get("index", 1),
            "label":        self._label_edit.text(),
            "action":       action,
            "press_action": press_action,
        }
        self.accept()


# ── NavButtonEditorDialog ──────────────────────────────────────────────────────

class NavButtonEditorDialog(QDialog):
    """
    Dialog zum Bearbeiten eines Nav-Buttons (◀ Zurück | Home | ▶ Weiter).
    Kein Icon-Bereich — nur Label + Aktion.
    Standard-Aktionen sind scene_prev / scene_home / scene_next.
    """

    _NAV_TITLES = {
        "prev": "◀ Zurück",
        "home": "■ Home",
        "next": "▶ Weiter",
    }

    def __init__(self, nav_data: dict, parent=None):
        super().__init__(parent)
        self._data = copy.deepcopy(nav_data)
        self.result_data = None

        nav_id = nav_data.get("id", "")
        title = self._NAV_TITLES.get(nav_id, "Nav-Button") + " bearbeiten"
        self.setWindowTitle(title)
        self.setMinimumWidth(440)
        self.setModal(True)

        self._setup_ui(nav_id)
        self._load_data()

    def _setup_ui(self, nav_id: str):
        root = QVBoxLayout(self)
        root.setSpacing(16)
        root.setContentsMargins(24, 24, 24, 20)

        # Titel
        title_lbl = QLabel(self._NAV_TITLES.get(nav_id, "Nav-Button") + " bearbeiten")
        f = QFont(); f.setPointSize(14); f.setBold(True)
        title_lbl.setFont(f)
        root.addWidget(title_lbl)

        hint_lbl = QLabel(
            "Standardmäßig wechseln diese Buttons zwischen Szenen.\n"
            "Du kannst die Aktion auch auf etwas anderes legen."
        )
        hint_lbl.setStyleSheet("color: #8E8E93; font-size: 11px;")
        hint_lbl.setWordWrap(True)
        root.addWidget(hint_lbl)

        # Label
        grp_label = QGroupBox("Beschriftung")
        gl = QFormLayout(grp_label)
        gl.setSpacing(10)
        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("z. B. Zurück, Home, …")
        gl.addRow("Label:", self._label_edit)
        root.addWidget(grp_label)

        # Aktion
        grp_action = QGroupBox("Aktion")
        ga = QVBoxLayout(grp_action)
        ga.setSpacing(12)

        type_row = QHBoxLayout()
        type_row.addWidget(QLabel("Typ:"))
        self._action_combo = QComboBox()
        for key, name in NAV_ACTION_TYPES:
            self._action_combo.addItem(name, key)
        self._action_combo.currentIndexChanged.connect(self._on_action_type_changed)
        type_row.addWidget(self._action_combo)
        type_row.addStretch()
        ga.addLayout(type_row)

        self._action_stack = QStackedWidget()

        # 0: scene_prev — kein extra Feld
        prev_w = QWidget()
        prev_l = QVBoxLayout(prev_w)
        prev_l.setContentsMargins(0, 4, 0, 4)
        prev_l.addWidget(QLabel("Wechselt zur vorherigen Szene (zyklisch)."))
        self._action_stack.addWidget(prev_w)

        # 1: scene_home — kein extra Feld
        home_w = QWidget()
        home_l = QVBoxLayout(home_w)
        home_l.setContentsMargins(0, 4, 0, 4)
        home_l.addWidget(QLabel("Springt direkt zur ersten Szene."))
        self._action_stack.addWidget(home_w)

        # 2: scene_next — kein extra Feld
        next_w = QWidget()
        next_l = QVBoxLayout(next_w)
        next_l.setContentsMargins(0, 4, 0, 4)
        next_l.addWidget(QLabel("Wechselt zur nächsten Szene (zyklisch)."))
        self._action_stack.addWidget(next_w)

        # 3: open_app
        app_w = QWidget()
        app_l = QFormLayout(app_w)
        app_l.setSpacing(10)
        app_l.setContentsMargins(0, 4, 0, 4)
        self._act_app_name = QLineEdit()
        self._act_app_name.setPlaceholderText("Google Chrome")
        act_path_row = QHBoxLayout()
        self._act_app_path = QLineEdit()
        self._act_app_path.setPlaceholderText("/Applications/…")
        browse_app_btn = QPushButton("Durchsuchen…")
        browse_app_btn.setObjectName("GhostButton")
        browse_app_btn.clicked.connect(self._browse_app)
        act_path_row.addWidget(self._act_app_path)
        act_path_row.addWidget(browse_app_btn)
        app_l.addRow("App-Name:", self._act_app_name)
        app_l.addRow("App-Pfad:", act_path_row)
        self._action_stack.addWidget(app_w)

        # 4: open_url
        url_w = QWidget()
        url_l = QFormLayout(url_w)
        url_l.setSpacing(10)
        url_l.setContentsMargins(0, 4, 0, 4)
        self._act_url = QLineEdit()
        self._act_url.setPlaceholderText("https://…")
        url_l.addRow("URL:", self._act_url)
        self._action_stack.addWidget(url_w)

        # 5: shortcut
        sc_w = QWidget()
        sc_l = QFormLayout(sc_w)
        sc_l.setSpacing(10)
        sc_l.setContentsMargins(0, 4, 0, 4)
        self._act_keys = QLineEdit()
        self._act_keys.setPlaceholderText("cmd+shift+4")
        hint = QLabel("Modifier: cmd, shift, alt, ctrl — z. B. cmd+z, f12, space")
        hint.setStyleSheet("color: #8E8E93; font-size: 11px;")
        sc_l.addRow("Tasten:", self._act_keys)
        sc_l.addRow("", hint)
        self._action_stack.addWidget(sc_w)

        # 6: shell
        sh_w = QWidget()
        sh_l = QFormLayout(sh_w)
        sh_l.setSpacing(10)
        sh_l.setContentsMargins(0, 4, 0, 4)
        self._act_cmd = QLineEdit()
        self._act_cmd.setPlaceholderText("echo 'Hallo'")
        sh_l.addRow("Befehl:", self._act_cmd)
        self._action_stack.addWidget(sh_w)

        # 7: none
        none_w = QWidget()
        none_l = QVBoxLayout(none_w)
        none_l.setContentsMargins(0, 4, 0, 4)
        none_l.addWidget(QLabel("Dieser Button hat keine Aktion."))
        self._action_stack.addWidget(none_w)

        ga.addWidget(self._action_stack)
        root.addWidget(grp_action)

        # Reset-Button
        reset_btn = QPushButton("Standard-Aktion wiederherstellen")
        reset_btn.setObjectName("GhostButton")
        reset_btn.clicked.connect(self._reset_to_default)
        root.addWidget(reset_btn)

        # Trennlinie + Buttons
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("Separator")
        root.addWidget(sep)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Speichern")
        save_btn.setObjectName("PrimaryButton")
        save_btn.clicked.connect(self._save)
        cancel_btn = QPushButton("Abbrechen")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)

    def _load_data(self):
        self._label_edit.setText(self._data.get("label", ""))
        action = self._data.get("action") or {}
        atype = action.get("type", "none") if action else "none"
        self._action_combo.setCurrentIndex(_type_index(NAV_ACTION_TYPES, atype))
        # Felder vorbelegen
        if hasattr(self, "_act_app_name"):
            self._act_app_name.setText(action.get("name", ""))
            self._act_app_path.setText(action.get("path", "") or "")
        if hasattr(self, "_act_url"):
            self._act_url.setText(action.get("url", ""))
        if hasattr(self, "_act_keys"):
            self._act_keys.setText(action.get("keys", ""))
        if hasattr(self, "_act_cmd"):
            self._act_cmd.setText(action.get("command", ""))

    def _on_action_type_changed(self, idx):
        self._action_stack.setCurrentIndex(idx)

    def _browse_app(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "App auswählen", "/Applications",
            "Apps (*.app);;Alle Dateien (*)"
        )
        if not path:
            return
        if ".app/" in path or (not path.endswith(".app") and ".app" in path):
            path = path.split(".app")[0] + ".app"
        app_name = os.path.basename(path).replace(".app", "")
        self._act_app_path.setText(path)
        if not self._act_app_name.text():
            self._act_app_name.setText(app_name)
        if not self._label_edit.text():
            self._label_edit.setText(app_name)

    def _reset_to_default(self):
        """Stellt die Standard-Szenen-Navigation wieder her."""
        nav_id = self._data.get("id", "home")
        default_type = f"scene_{nav_id}"
        idx = _type_index(NAV_ACTION_TYPES, default_type)
        self._action_combo.setCurrentIndex(idx)

    def _build_data(self) -> dict:
        atype_key = self._action_combo.currentData()
        if atype_key == "open_app":
            action = {
                "type": "open_app",
                "name": self._act_app_name.text(),
                "path": self._act_app_path.text() or None,
            }
        elif atype_key == "open_url":
            action = {"type": "open_url", "url": self._act_url.text()}
        elif atype_key == "shortcut":
            action = {"type": "shortcut", "keys": self._act_keys.text()}
        elif atype_key == "shell":
            action = {"type": "shell", "command": self._act_cmd.text()}
        elif atype_key in ("scene_prev", "scene_home", "scene_next"):
            action = {"type": atype_key}
        else:
            action = None

        return {
            "id":     self._data.get("id", ""),
            "label":  self._label_edit.text(),
            "action": action,
        }

    def _save(self):
        self.result_data = self._build_data()
        self.accept()
