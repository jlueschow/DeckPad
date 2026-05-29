"""
ConfigWindow — Hauptfenster der AKP03E-Konfigurationsapp.
Tabs: Meine Szenen | Seiten-Bibliothek | Button-Bibliothek | Einstellungen
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QSlider, QFrame, QScrollArea, QSizePolicy,
    QStackedWidget, QInputDialog, QMessageBox, QSpacerItem, QGroupBox,
    QFormLayout, QTabBar, QCheckBox, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor

from config.config_manager import cfg
from app.scene_widget import SceneWidget
from app.button_editor import ButtonEditorDialog, KnobEditorDialog, NavButtonEditorDialog
from app.library_panel import PageLibraryPanel, ButtonLibraryPanel
from app.styles import C


# ── ConfigWindow ───────────────────────────────────────────────────────────────

class ConfigWindow(QMainWindow):
    """Haupt-Konfigurationsfenster."""
    scene_changed     = Signal(int)   # Szene muss auf Gerät hochgeladen werden
    brightness_changed = Signal(int)   # Helligkeit geändert

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AKP03E Konfiguration")
        self.setMinimumSize(880, 620)
        self.resize(980, 680)
        # Stylesheet wird global via app.setStyleSheet() in app_main.py gesetzt
        self._hid_thread = None   # wird von aussen gesetzt
        self._setup_ui()
        self._load_scenes()

    def set_hid_thread(self, thread):
        self._hid_thread = thread

    def set_connected(self, connected: bool):
        if connected:
            self._status_dot.setText("●")
            self._status_dot.setStyleSheet(f"color: {C['green']}; font-size: 14px;")
            self._status_lbl.setText("Verbunden")
            self._status_lbl.setObjectName("StatusLabel")
        else:
            self._status_dot.setText("●")
            self._status_dot.setStyleSheet(f"color: {C['red']}; font-size: 14px;")
            self._status_lbl.setText("Nicht verbunden")
            self._status_lbl.setObjectName("StatusLabelOff")
        self.style().unpolish(self._status_lbl)
        self.style().polish(self._status_lbl)

    # ── UI-Aufbau ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header-Leiste
        root.addWidget(self._make_header())

        # Tabs
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(True)
        self._tabs.setTabPosition(QTabWidget.TabPosition.North)
        root.addWidget(self._tabs, 1)

        # Tab 0: Meine Szenen
        self._scenes_tab = QWidget()
        self._tabs.addTab(self._scenes_tab, "Meine Szenen")
        self._setup_scenes_tab()

        # Tab 1: Seiten-Bibliothek
        self._page_lib = PageLibraryPanel()
        self._page_lib.page_applied.connect(self._on_page_applied)
        self._tabs.addTab(self._page_lib, "Seiten-Bibliothek")

        # Tab 2: Button-Bibliothek
        self._btn_lib = ButtonLibraryPanel()
        self._btn_lib.button_selected.connect(self._on_library_button_selected)
        self._tabs.addTab(self._btn_lib, "Button-Bibliothek")

        # Tab 3: Einstellungen
        self._settings_tab = QWidget()
        self._tabs.addTab(self._settings_tab, "Einstellungen")
        self._setup_settings_tab()

    def _make_header(self) -> QWidget:
        header = QFrame()
        header.setObjectName("HeaderBar")
        header.setFixedHeight(56)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(12)

        # App-Titel
        # Kein Emoji im QLabel: CoreText → CopyEmojiImage → ImageIO-Alignment-Fault auf macOS
        title = QLabel("AKP03E")
        f = QFont(); f.setPointSize(16); f.setBold(True)
        title.setFont(f)
        title.setObjectName("AppTitle")
        hl.addWidget(title)

        hl.addStretch()

        # Verbindungsstatus
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet(f"color: {C['red']}; font-size: 14px;")
        self._status_lbl = QLabel("Nicht verbunden")
        self._status_lbl.setObjectName("StatusLabelOff")
        hl.addWidget(self._status_dot)
        hl.addWidget(self._status_lbl)

        return header

    # ── Szenen-Tab ─────────────────────────────────────────────────────────────

    def _setup_scenes_tab(self):
        layout = QVBoxLayout(self._scenes_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Szenen-Auswahl-Leiste
        selector_bar = QWidget()
        selector_bar.setFixedHeight(44)
        selector_bar.setStyleSheet(f"background:{C['mantle']}; "
                                     f"border-bottom: 1px solid {C['surface0']};")
        sl = QHBoxLayout(selector_bar)
        sl.setContentsMargins(20, 0, 20, 0)
        sl.setSpacing(6)

        scene_label = QLabel("Szene:")
        scene_label.setStyleSheet(f"color:{C['subtext0']}; font-size:12px;")
        sl.addWidget(scene_label)

        self._scene_tabs = QTabBar()
        self._scene_tabs.setExpanding(False)
        self._scene_tabs.setStyleSheet(f"""
            QTabBar::tab {{
                background: transparent;
                color: {C['subtext1']};
                padding: 6px 16px;
                border-bottom: 2px solid transparent;
                border-radius: 0;
                font-size: 12px;
                font-weight: 500;
            }}
            QTabBar::tab:selected {{
                color: {C['mauve']};
                border-bottom: 2px solid {C['mauve']};
            }}
            QTabBar::tab:hover:!selected {{
                color: {C['text']};
            }}
        """)
        self._scene_tabs.currentChanged.connect(self._on_scene_tab_changed)
        sl.addWidget(self._scene_tabs)

        # Verschiebe-Buttons (direkt neben den Tabs)
        sl.addSpacing(6)
        self._move_left_btn = QPushButton("<<")
        self._move_left_btn.setObjectName("GhostButton")
        self._move_left_btn.setFixedSize(44, 28)
        _f = self._move_left_btn.font()
        _f.setBold(True)
        _f.setPointSize(11)
        self._move_left_btn.setFont(_f)
        self._move_left_btn.setToolTip("Szene nach links verschieben")
        self._move_left_btn.clicked.connect(self._move_scene_left)
        sl.addWidget(self._move_left_btn)

        self._move_right_btn = QPushButton(">>")
        self._move_right_btn.setObjectName("GhostButton")
        self._move_right_btn.setFixedSize(44, 28)
        _f2 = self._move_right_btn.font()
        _f2.setBold(True)
        _f2.setPointSize(11)
        self._move_right_btn.setFont(_f2)
        self._move_right_btn.setToolTip("Szene nach rechts verschieben")
        self._move_right_btn.clicked.connect(self._move_scene_right)
        sl.addWidget(self._move_right_btn)

        sl.addStretch()

        # Neue leere Szene hinzufügen
        add_btn = QPushButton("+ Szene")
        add_btn.setObjectName("GhostButton")
        add_btn.clicked.connect(self._add_scene)
        sl.addWidget(add_btn)

        # Auf Gerät hochladen
        upload_btn = QPushButton("↑ Auf Gerät laden")
        upload_btn.setObjectName("PrimaryButton")
        upload_btn.clicked.connect(self._upload_current_scene)
        sl.addWidget(upload_btn)

        layout.addWidget(selector_bar)

        # SceneWidget-Stack
        self._scene_stack = QStackedWidget()
        self._scene_widgets = []
        layout.addWidget(self._scene_stack, 1)

    def _load_scenes(self, select: int = -1):
        """
        Baut alle SceneWidgets neu auf.
        select: Index der danach aktiv gesetzten Szene.
                -1 → nimmt active_scene aus der Config.
        """
        config = cfg.get()
        scenes = config.get("scenes", [])

        # Bestehende Widgets löschen
        while self._scene_tabs.count() > 0:
            self._scene_tabs.removeTab(0)
        for sw in self._scene_widgets:
            sw.setParent(None)
            sw.deleteLater()
        self._scene_widgets = []

        for i, scene in enumerate(scenes):
            self._scene_tabs.addTab(scene.get("name", f"Szene {i+1}"))
            sw = SceneWidget(scene)
            sw.button_edit_requested.connect(
                lambda idx, d, si=i: self._edit_button(si, idx, d)
            )
            sw.knob_edit_requested.connect(
                lambda idx, d, si=i: self._edit_knob(si, idx, d)
            )
            sw.nav_button_edit_requested.connect(
                lambda nid, d, si=i: self._edit_nav_button(si, nid, d)
            )
            sw.save_to_library_requested.connect(
                lambda si=i: self._save_scene_to_library(si)
            )
            sw.delete_requested.connect(
                lambda si=i: self._delete_scene(si)
            )
            sw.rename_requested.connect(
                lambda si=i: self._rename_scene(si)
            )
            sw.buttons_swapped.connect(
                lambda src, tgt, si=i: self._swap_buttons(si, src, tgt)
            )
            sw.knobs_swapped.connect(
                lambda src, tgt, si=i: self._swap_knobs(si, src, tgt)
            )
            self._scene_stack.addWidget(sw)
            self._scene_widgets.append(sw)

        # Aktive Szene — ggf. durch expliziten select-Parameter überschreiben
        active = select if select >= 0 else config.get("active_scene", 0)
        active = min(active, max(len(scenes) - 1, 0))
        self._scene_tabs.setCurrentIndex(active)
        self._scene_stack.setCurrentIndex(active)

        self._update_move_buttons()

    def _update_move_buttons(self, idx: int = -1):
        """Aktiviert/deaktiviert ←/→ je nach Tab-Position."""
        if not hasattr(self, "_move_left_btn"):
            return
        if idx < 0:
            idx = self._scene_tabs.currentIndex()
        n = self._scene_tabs.count()
        self._move_left_btn.setEnabled(idx > 0)
        self._move_right_btn.setEnabled(n > 0 and idx < n - 1)

    def select_scene(self, index: int):
        """
        Wechselt den sichtbaren Tab auf index — ohne Widgets neu aufzubauen.
        Wird vom Gerät aus aufgerufen wenn prev/home/next gedrückt wird.
        """
        if 0 <= index < self._scene_stack.count():
            self._scene_tabs.setCurrentIndex(index)
            self._scene_stack.setCurrentIndex(index)

    def _on_scene_tab_changed(self, idx):
        if 0 <= idx < self._scene_stack.count():
            self._scene_stack.setCurrentIndex(idx)
        self._update_move_buttons(idx)

    # ── Szene verschieben ──────────────────────────────────────────────────────

    def _move_scene_left(self):
        idx = self._scene_tabs.currentIndex()
        if idx > 0:
            new_idx = idx - 1
            cfg.move_scene(idx, new_idx)
            self._load_scenes(select=new_idx)

    def _move_scene_right(self):
        idx = self._scene_tabs.currentIndex()
        if idx < self._scene_tabs.count() - 1:
            new_idx = idx + 1
            cfg.move_scene(idx, new_idx)
            self._load_scenes(select=new_idx)

    # ── Button/Knob bearbeiten ─────────────────────────────────────────────────

    def _edit_button(self, scene_index: int, btn_index: int, btn_data: dict):
        dlg = ButtonEditorDialog(btn_data, self)
        if dlg.exec() and dlg.result_data:
            new_data = dlg.result_data
            # In Config speichern
            config = cfg.get()
            buttons = config["scenes"][scene_index]["buttons"]
            for i, b in enumerate(buttons):
                if b["index"] == btn_index:
                    buttons[i] = new_data
                    break
            cfg.save()
            # SceneWidget aktualisieren
            self._scene_widgets[scene_index].refresh_scene(
                config["scenes"][scene_index]
            )
            # Auf Gerät hochladen wenn aktive Szene
            if scene_index == self._scene_tabs.currentIndex():
                self.scene_changed.emit(scene_index)

    def _edit_knob(self, scene_index: int, knob_index: int, knob_data: dict):
        dlg = KnobEditorDialog(knob_data, self)
        if dlg.exec() and dlg.result_data:
            new_data = dlg.result_data
            config = cfg.get()
            knobs = config["scenes"][scene_index]["knobs"]
            for i, k in enumerate(knobs):
                if k["index"] == knob_index:
                    knobs[i] = new_data
                    break
            cfg.save()
            self._scene_widgets[scene_index].refresh_scene(
                config["scenes"][scene_index]
            )

    def _edit_nav_button(self, scene_index: int, nav_id: str, nav_data: dict):
        dlg = NavButtonEditorDialog(nav_data, self)
        if dlg.exec() and dlg.result_data:
            new_data = dlg.result_data
            config = cfg.get()
            nav_buttons = config["scenes"][scene_index].get("nav_buttons", [])
            for i, nb in enumerate(nav_buttons):
                if nb["id"] == nav_id:
                    nav_buttons[i] = new_data
                    break
            cfg.save()
            self._scene_widgets[scene_index].refresh_scene(
                config["scenes"][scene_index]
            )

    # ── Drag & Drop: Tauschen ──────────────────────────────────────────────────

    def _swap_buttons(self, scene_index: int, idx_a: int, idx_b: int):
        """
        Tauscht Label, Icon und Aktion zweier LCD-Buttons (Index bleibt erhalten).
        Wird nach Drag & Drop in SceneWidget aufgerufen.
        """
        import copy
        config  = cfg.get()
        buttons = config["scenes"][scene_index]["buttons"]
        ba = next((b for b in buttons if b["index"] == idx_a), None)
        bb = next((b for b in buttons if b["index"] == idx_b), None)
        if ba is None or bb is None:
            return

        # Inhalte tauschen — Index bleibt
        for key in ("label", "icon", "action"):
            va = copy.deepcopy(ba.get(key))
            vb = copy.deepcopy(bb.get(key))
            ba[key] = vb
            bb[key] = va

        cfg.save()
        self._scene_widgets[scene_index].refresh_scene(config["scenes"][scene_index])
        if scene_index == self._scene_tabs.currentIndex():
            self.scene_changed.emit(scene_index)

    def _swap_knobs(self, scene_index: int, idx_a: int, idx_b: int):
        """
        Tauscht Label und Aktion zweier Knobs (Index bleibt erhalten).
        Wird nach Drag & Drop in SceneWidget aufgerufen.
        """
        import copy
        config = cfg.get()
        knobs  = config["scenes"][scene_index]["knobs"]
        ka = next((k for k in knobs if k["index"] == idx_a), None)
        kb = next((k for k in knobs if k["index"] == idx_b), None)
        if ka is None or kb is None:
            return

        for key in ("label", "action"):
            va = copy.deepcopy(ka.get(key))
            vb = copy.deepcopy(kb.get(key))
            ka[key] = vb
            kb[key] = va

        cfg.save()
        self._scene_widgets[scene_index].refresh_scene(config["scenes"][scene_index])

    # ── Bibliothek-Callbacks ───────────────────────────────────────────────────

    def _on_page_applied(self, page_id: str, scene_index: int):
        """Seite wurde auf Szene angewandt → Widgets neu laden."""
        self._load_scenes()
        if self._hid_thread:
            self._hid_thread.upload_scene_now(scene_index)

    def _on_library_button_selected(self, btn_data: dict):
        """Button aus Bibliothek → öffnet Editor, vorausgefüllt mit btn_data."""
        # Aktuell angezeigte Szene
        si = self._scene_tabs.currentIndex()
        config = cfg.get()
        scenes = config.get("scenes", [])
        if si >= len(scenes):
            return

        # Ersten freien (leeren) Slot in der Szene finden
        buttons = scenes[si].get("buttons", [])
        free_slot = None
        for b in buttons:
            if not b.get("label") and not b.get("action"):
                free_slot = b
                break

        if free_slot is None:
            # Kein freier Slot → Benutzer auswählen lassen (einfach Editor für Slot 1)
            free_slot = buttons[0] if buttons else {"index": 1, "label": "", "icon": None, "action": None}

        # btn_data aus Bibliothek in Slot kopieren (Index beibehalten)
        import copy
        merged = copy.deepcopy(btn_data)
        merged["index"] = free_slot["index"]

        dlg = ButtonEditorDialog(merged, self)
        if dlg.exec() and dlg.result_data:
            new_data = dlg.result_data
            for i, b in enumerate(buttons):
                if b["index"] == new_data["index"]:
                    buttons[i] = new_data
                    break
            cfg.save()
            self._scene_widgets[si].refresh_scene(config["scenes"][si])
            self.scene_changed.emit(si)

    # ── Szene umbenennen ───────────────────────────────────────────────────────

    def _rename_scene(self, scene_index: int = -1):
        si = scene_index if scene_index >= 0 else self._scene_tabs.currentIndex()
        config = cfg.get()
        scenes = config.get("scenes", [])
        if si >= len(scenes):
            return
        current_name = scenes[si].get("name", f"Szene {si+1}")
        new_name, ok = QInputDialog.getText(
            self, "Seite umbenennen", "Neuer Name:", text=current_name
        )
        if ok and new_name.strip():
            scenes[si]["name"] = new_name.strip()
            cfg.save()
            self._scene_tabs.setTabText(si, new_name.strip())
            if self._scene_widgets[si]._name_label:
                self._scene_widgets[si]._name_label.setText(new_name.strip())

    # ── In Bibliothek speichern ────────────────────────────────────────────────

    def _save_scene_to_library(self, scene_index: int):
        import copy
        config = cfg.get()
        scenes = config.get("scenes", [])
        if scene_index >= len(scenes):
            return

        scene       = scenes[scene_index]
        default_name = scene.get("name", f"Szene {scene_index + 1}")

        name, ok = QInputDialog.getText(
            self, "In Bibliothek speichern",
            "Name der Vorlage:", text=default_name
        )
        if not ok or not name.strip():
            return

        # Kopie der Szene als Library-Seite vorbereiten
        page = copy.deepcopy(scene)
        page["name"] = name.strip()
        page.pop("id",          None)   # wird in save_page neu vergeben
        page.pop("source_page", None)   # Bibliotheks-Referenz nicht übernehmen

        cfg.save_page(page)

        # Seiten-Bibliothek sofort aktualisieren
        self._page_lib.reload()

    # ── Szene hinzufügen ───────────────────────────────────────────────────────

    def _add_scene(self):
        """Neue leere Szene anlegen und direkt auswählen."""
        config = cfg.get()
        n = len(config.get("scenes", [])) + 1
        new_index = cfg.add_scene(f"Szene {n}")
        self._load_scenes()
        self._scene_tabs.setCurrentIndex(new_index)
        self._scene_stack.setCurrentIndex(new_index)

    # ── Szene löschen ──────────────────────────────────────────────────────────

    def _delete_scene(self, scene_index: int):
        """Löscht die Szene nach Bestätigung durch den Benutzer."""
        config = cfg.get()
        scenes = config.get("scenes", [])

        # Letzte Szene kann nicht gelöscht werden
        if len(scenes) <= 1:
            QMessageBox.information(
                self,
                "Hinweis",
                "Die letzte verbleibende Seite kann nicht gelöscht werden.",
            )
            return

        scene_name = scenes[scene_index].get("name", f"Szene {scene_index + 1}")
        reply = QMessageBox.warning(
            self,
            "Seite löschen",
            f"Seite \"{scene_name}\" wirklich löschen?\n\n"
            f"Alle Buttons und Knob-Einstellungen dieser Seite gehen unwiderruflich verloren.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cfg.delete_scene(scene_index)
            self._load_scenes()

    # ── Auf Gerät hochladen ────────────────────────────────────────────────────

    def _upload_current_scene(self):
        si = self._scene_tabs.currentIndex()
        self.scene_changed.emit(si)

    # ── Einstellungen-Tab ──────────────────────────────────────────────────────

    def _setup_settings_tab(self):
        # Äußeres Layout: nur die ScrollArea
        outer = QVBoxLayout(self._settings_tab)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        def _form(grp: QGroupBox) -> QFormLayout:
            """Erzeugt ein gut ausgerichtetes QFormLayout für eine GroupBox."""
            fl = QFormLayout(grp)
            fl.setContentsMargins(16, 16, 16, 16)
            fl.setSpacing(12)
            fl.setHorizontalSpacing(20)
            fl.setFieldGrowthPolicy(
                QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
            )
            return fl

        # ── Gerät ─────────────────────────────────────────────────────────────
        device_grp = QGroupBox("Gerät")
        device_l = _form(device_grp)
        self._dev_name_lbl = QLabel("AJAZZ AKP03E")
        self._dev_conn_lbl = QLabel("—")
        device_l.addRow("Modell:", self._dev_name_lbl)
        device_l.addRow("Status:", self._dev_conn_lbl)
        layout.addWidget(device_grp)

        # ── Display ────────────────────────────────────────────────────────────
        display_grp = QGroupBox("Display")
        display_l = _form(display_grp)
        config = cfg.get()
        brightness = config.get("brightness", 80)
        bright_row = QHBoxLayout()
        bright_row.setSpacing(10)
        self._bright_slider = QSlider(Qt.Orientation.Horizontal)
        self._bright_slider.setRange(0, 100)
        self._bright_slider.setValue(brightness)
        self._bright_slider.valueChanged.connect(self._on_brightness_changed)
        self._bright_value = QLabel(f"{brightness}%")
        self._bright_value.setFixedWidth(44)
        bright_row.addWidget(self._bright_slider, 1)
        bright_row.addWidget(self._bright_value)
        display_l.addRow("Helligkeit:", bright_row)
        layout.addWidget(display_grp)

        # ── Autostart ──────────────────────────────────────────────────────────
        autostart_grp = QGroupBox("Autostart")
        autostart_l = QVBoxLayout(autostart_grp)
        autostart_l.setContentsMargins(16, 16, 16, 16)
        autostart_l.setSpacing(8)
        self._autostart_cb = QCheckBox("DeckPad beim Login automatisch starten")
        try:
            import autostart as _as
            self._autostart_cb.setChecked(_as.is_enabled())
            self._autostart_cb.setEnabled(True)
        except Exception:
            self._autostart_cb.setEnabled(False)
        self._autostart_cb.toggled.connect(self._on_autostart_toggled)
        autostart_hint = QLabel(
            "macOS: launchd-Plist in ~/Library/LaunchAgents/\n"
            "Windows: Registrierungseintrag HKCU\\...\\Run"
        )
        autostart_hint.setStyleSheet("color: #636366; font-size: 11px;")
        autostart_l.addWidget(self._autostart_cb)
        autostart_l.addWidget(autostart_hint)
        layout.addWidget(autostart_grp)

        # ── Dante DDM ──────────────────────────────────────────────────────────
        dante_grp = QGroupBox("Dante DDM")
        dante_l = _form(dante_grp)
        dante_config = cfg.get().get("dante", {})

        self._dante_host_edit = QLineEdit()
        self._dante_host_edit.setPlaceholderText("http://172.17.113.10")
        self._dante_host_edit.setText(dante_config.get("host", ""))
        self._dante_host_edit.textChanged.connect(self._on_dante_host_changed)
        dante_l.addRow("DDM Host:", self._dante_host_edit)

        key_row = QHBoxLayout()
        key_row.setSpacing(6)
        self._dante_key_edit = QLineEdit()
        self._dante_key_edit.setPlaceholderText("API-Key")
        self._dante_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._dante_key_edit.setText(dante_config.get("api_key", ""))
        self._dante_key_edit.textChanged.connect(self._on_dante_key_changed)
        self._dante_key_toggle = QPushButton("Zeigen")
        self._dante_key_toggle.setObjectName("GhostButton")
        self._dante_key_toggle.setFixedWidth(80)
        self._dante_key_toggle.setCheckable(True)
        self._dante_key_toggle.clicked.connect(self._toggle_api_key_visibility)
        key_row.addWidget(self._dante_key_edit, 1)
        key_row.addWidget(self._dante_key_toggle)
        dante_l.addRow("API-Key:", key_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        dante_test_btn = QPushButton("Verbindung testen")
        dante_test_btn.setObjectName("GhostButton")
        dante_test_btn.clicked.connect(self._test_dante_connection)
        self._dante_status_lbl = QLabel("")
        self._dante_status_lbl.setStyleSheet("font-size: 12px;")
        btn_row.addWidget(dante_test_btn)
        btn_row.addWidget(self._dante_status_lbl, 1)
        dante_l.addRow("", btn_row)

        dante_hint = QLabel(
            "API-Key wird im Klartext in config.json gespeichert.\n"
            "Nur im lokalen Netzwerk (TH-OWL) erreichbar."
        )
        dante_hint.setStyleSheet("color: #636366; font-size: 11px;")
        dante_hint.setWordWrap(True)
        dante_l.addRow("", dante_hint)
        layout.addWidget(dante_grp)

        # ── Info ───────────────────────────────────────────────────────────────
        info_grp = QGroupBox("Info")
        info_l = _form(info_grp)
        info_l.addRow("App:", QLabel("DeckPad"))
        info_l.addRow("Version:", QLabel("1.0"))
        cfg_path_lbl = QLabel(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "data", "config.json")
        )
        cfg_path_lbl.setWordWrap(True)
        cfg_path_lbl.setStyleSheet("color: #8e8e93; font-size: 11px;")
        info_l.addRow("Config-Pfad:", cfg_path_lbl)
        layout.addWidget(info_grp)

        layout.addStretch()

    def _on_autostart_toggled(self, checked: bool):
        try:
            import autostart as _as
            ok = _as.enable() if checked else _as.disable()
            if not ok:
                # Änderung rückgängig: Checkbox zurücksetzen
                self._autostart_cb.blockSignals(True)
                self._autostart_cb.setChecked(not checked)
                self._autostart_cb.blockSignals(False)
                QMessageBox.warning(
                    self, "Autostart",
                    "Autostart konnte nicht geändert werden.\n"
                    "Bitte Berechtigungen prüfen."
                )
        except Exception as e:
            print(f"[autostart] Fehler: {e}")

    def _on_brightness_changed(self, value: int):
        self._bright_value.setText(f"{value}%")
        cfg.set_brightness(value)
        self.brightness_changed.emit(value)
        if self._hid_thread:
            self._hid_thread.set_brightness_now(value)

    def _on_dante_host_changed(self, text: str):
        cfg.get().setdefault("dante", {})["host"] = text.strip()
        cfg.save()
        self._dante_status_lbl.setText("")

    def _on_dante_key_changed(self, text: str):
        cfg.get().setdefault("dante", {})["api_key"] = text
        cfg.save()
        self._dante_status_lbl.setText("")

    def _toggle_api_key_visibility(self, checked: bool):
        if checked:
            self._dante_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self._dante_key_toggle.setText("Verbergen")
        else:
            self._dante_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self._dante_key_toggle.setText("Zeigen")

    def _test_dante_connection(self):
        import urllib.request
        import urllib.error
        import json as _json
        dante_cfg = cfg.get().get("dante", {})
        host    = dante_cfg.get("host", "").rstrip("/")
        api_key = dante_cfg.get("api_key", "")
        if not host:
            self._dante_status_lbl.setText("Kein Host eingetragen.")
            self._dante_status_lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")
            return
        self._dante_status_lbl.setText("Verbinde…")
        self._dante_status_lbl.setStyleSheet("color: #636366; font-size: 12px;")
        try:
            req = urllib.request.Request(
                f"{host}/graphql",
                data=b'{"query":"{ domains { name } }"}',
                headers={
                    "Content-Type": "application/json",
                    "Authorization": api_key,
                    "User-Agent": "PostmanRuntime/7.45.0",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            domains = [d["name"] for d in data.get("data", {}).get("domains", [])]
            self._dante_status_lbl.setText(
                f"✓ Verbunden  — Domains: {', '.join(domains)}"
            )
            self._dante_status_lbl.setStyleSheet("color: #a6e3a1; font-size: 12px;")
        except urllib.error.URLError as e:
            self._dante_status_lbl.setText(f"Nicht erreichbar: {e.reason}")
            self._dante_status_lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")
        except Exception as e:
            self._dante_status_lbl.setText(f"Fehler: {e}")
            self._dante_status_lbl.setStyleSheet("color: #ff6b6b; font-size: 12px;")

    def update_device_status(self, connected: bool, message: str = ""):
        self.set_connected(connected)
        if hasattr(self, "_dev_conn_lbl"):
            self._dev_conn_lbl.setText(
                "Verbunden ✓" if connected else f"Getrennt  {message}"
            )
