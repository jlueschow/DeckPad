"""
LibraryPanel — zeigt Seiten-Bibliothek und Button-Bibliothek.
  PageLibraryPanel   — Dropdown-Auswahl + SceneWidget-Vorschau/Editor
                       + Speichern / Löschen / Hinzufügen
  ButtonLibraryPanel — kategorisierte Button-Bibliothek
"""

import sys, os, copy, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QFrame, QSizePolicy, QListWidget,
    QSplitter, QMessageBox, QComboBox, QInputDialog, QMenu
)
from PySide6.QtCore import Signal, Qt, QSize, QRect, QPoint
from PySide6.QtGui import QFont, QPixmap, QAction

from config.config_manager import cfg, PAGES_DIR
from app.scene_widget import SceneWidget, _icon_to_pixmap
from app.button_editor import ButtonEditorDialog, KnobEditorDialog, NavButtonEditorDialog
from app.styles import C


# ── ButtonGridWidget — wird von ButtonLibraryPanel verwendet ─────────────────

class ButtonGridWidget(QWidget):
    """
    Zeigt Buttons in einem responsiven Raster.
    Die Spaltenanzahl passt sich der verfügbaren Breite an (resizeEvent).
    Stabiler als manuelles Flow-Layout: verwendet QGridLayout, das Qt selbst
    verwaltet — kein manuelles move()/resize() nötig.
    """
    _CARD_W    = 90           # muss mit _ButtonCard.setFixedSize(90, …) übereinstimmen
    _SPACING   =  10          # Abstand zwischen Karten

    def __init__(self, parent=None):
        super().__init__(parent)
        self._widgets: list[QWidget] = []
        self._cols = 4         # Startwert; wird in resizeEvent angepasst
        self._grid = QGridLayout(self)
        self._grid.setContentsMargins(16, 16, 16, 16)
        self._grid.setSpacing(self._SPACING)

    def add_widget(self, w: QWidget):
        self._widgets.append(w)
        self._rebuild_grid()

    def clear_widgets(self):
        for w in self._widgets:
            self._grid.removeWidget(w)
            w.setParent(None)
            w.deleteLater()
        self._widgets.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        m = self._grid.contentsMargins()
        avail = self.width() - m.left() - m.right()
        cols  = max(1, (avail + self._SPACING) // (self._CARD_W + self._SPACING))
        if cols != self._cols:
            self._cols = cols
            self._rebuild_grid()

    def _rebuild_grid(self):
        # Alle Widgets aus dem Grid entfernen (ohne deleteLater)
        for w in self._widgets:
            self._grid.removeWidget(w)
        # Neu einfügen
        for i, w in enumerate(self._widgets):
            row, col = divmod(i, self._cols)
            self._grid.addWidget(w, row, col, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        # Leere Spalten mit Stretch füllen damit Buttons linksbündig bleiben
        for c in range(self._cols):
            self._grid.setColumnStretch(c, 0)
        self._grid.setColumnStretch(self._cols, 1)


# ── PageLibraryPanel ──────────────────────────────────────────────────────────

class PageLibraryPanel(QWidget):
    """
    Seiten-Bibliothek: Dropdown-Auswahl, SceneWidget-Editor, Aktionsleiste.
    Struktur:
      Oben  — Dropdown mit Vorlagen-Namen
      Mitte — SceneWidget (editierbar, ohne Szenen-Aktionsleiste)
      Unten — Speichern | Löschen | Hinzufügen
    """
    page_applied = Signal(str, int)   # (page_id, scene_index)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pages: list[dict] = []
        self._current_page: dict | None = None
        self._scene_widget: SceneWidget | None = None
        self._setup_ui()
        self.reload()

    # ── UI-Aufbau ──────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

        # Titel-Zeile
        title_row = QHBoxLayout()
        title_row.setSpacing(12)
        title = QLabel("Seiten-Bibliothek")
        f = QFont(); f.setPointSize(14); f.setBold(True)
        title.setFont(f)
        title_row.addWidget(title)
        title_row.addStretch()
        sub = QLabel("Vorlagen bearbeiten und auf Szenen anwenden")
        sub.setObjectName("Subtitle")
        title_row.addWidget(sub)
        root.addLayout(title_row)

        # Dropdown-Zeile
        combo_row = QHBoxLayout()
        combo_row.setSpacing(10)
        combo_lbl = QLabel("Vorlage:")
        combo_lbl.setStyleSheet(f"color: {C['subtext0']}; font-size: 13px;")
        self._combo = QComboBox()
        self._combo.setMinimumWidth(280)
        self._combo.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._combo.currentIndexChanged.connect(self._on_page_selected)
        combo_row.addWidget(combo_lbl)
        combo_row.addWidget(self._combo)
        combo_row.addStretch()
        root.addLayout(combo_row)

        # SceneWidget-Bereich (scrollbar)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._scene_container = QWidget()
        self._scene_layout = QVBoxLayout(self._scene_container)
        self._scene_layout.setContentsMargins(0, 0, 0, 0)
        self._scene_layout.setSpacing(0)
        self._scroll.setWidget(self._scene_container)
        root.addWidget(self._scroll, 1)

        # Trennlinie
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setObjectName("Separator")
        root.addWidget(sep)

        # Untere Aktionsleiste
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._del_btn = QPushButton("Vorlage löschen")
        self._del_btn.setObjectName("DangerButton")
        self._del_btn.setFixedHeight(32)
        self._del_btn.clicked.connect(self._delete_page)
        btn_row.addWidget(self._del_btn)

        btn_row.addStretch()

        self._save_btn = QPushButton("Speichern")
        self._save_btn.setObjectName("PrimaryButton")
        self._save_btn.setFixedHeight(32)
        self._save_btn.clicked.connect(self._save_page)
        btn_row.addWidget(self._save_btn)

        self._add_btn = QPushButton("+ Hinzufügen")
        self._add_btn.setObjectName("GhostButton")
        self._add_btn.setFixedHeight(32)
        self._add_btn.setToolTip("Vorlage auf eine Szene anwenden")
        self._add_btn.clicked.connect(self._apply_page)
        btn_row.addWidget(self._add_btn)

        root.addLayout(btn_row)

    # ── Laden ──────────────────────────────────────────────────────────────────

    def reload(self):
        """Lädt alle Vorlagen neu (Dateisystem → Combo-Box → SceneWidget)."""
        self._pages = cfg.load_all_pages()

        self._combo.blockSignals(True)
        prev_id = self._combo.currentData()   # aktuelle Auswahl merken
        self._combo.clear()
        for page in self._pages:
            self._combo.addItem(page.get("name", "?"), page.get("id", ""))

        # Vorherige Auswahl wiederherstellen; sonst erste Seite
        restored = False
        if prev_id:
            for i in range(self._combo.count()):
                if self._combo.itemData(i) == prev_id:
                    self._combo.setCurrentIndex(i)
                    restored = True
                    break
        if not restored and self._combo.count() > 0:
            self._combo.setCurrentIndex(0)
        self._combo.blockSignals(False)

        self._on_page_selected(self._combo.currentIndex())

    def _update_buttons_enabled(self):
        has = self._current_page is not None
        self._del_btn.setEnabled(has)
        self._save_btn.setEnabled(has)
        self._add_btn.setEnabled(has)

    # ── Vorlage auswählen ──────────────────────────────────────────────────────

    def _on_page_selected(self, idx: int):
        if 0 <= idx < len(self._pages):
            self._current_page = copy.deepcopy(self._pages[idx])
        else:
            self._current_page = None
        self._rebuild_scene_widget()
        self._update_buttons_enabled()

    def _rebuild_scene_widget(self):
        """Entfernt altes SceneWidget und baut es aus _current_page neu auf."""
        while self._scene_layout.count():
            item = self._scene_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._scene_widget = None

        if not self._current_page:
            lbl = QLabel(
                "Keine Vorlagen vorhanden.\n\n"
                "Nutze «In Bibliothek speichern» auf einer Szene, um eine Vorlage anzulegen."
            )
            lbl.setStyleSheet("color: #8E8E93; padding: 40px; font-size: 13px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setWordWrap(True)
            self._scene_layout.addWidget(lbl)
            self._scene_layout.addStretch()
            return

        # SceneWidget ohne die Szenen-Aktionsleiste (Speichern/Löschen)
        self._scene_widget = SceneWidget(self._current_page, show_scene_actions=False)
        self._scene_widget.button_edit_requested.connect(self._edit_button)
        self._scene_widget.knob_edit_requested.connect(self._edit_knob)
        self._scene_widget.nav_button_edit_requested.connect(self._edit_nav_button)
        self._scene_widget.rename_requested.connect(self._rename_page)
        self._scene_layout.addWidget(self._scene_widget)
        self._scene_layout.addStretch()

    # ── Button / Knob / Nav bearbeiten ─────────────────────────────────────────

    def _edit_button(self, btn_index: int, btn_data: dict):
        dlg = ButtonEditorDialog(btn_data, self)
        if dlg.exec() and dlg.result_data:
            for i, b in enumerate(self._current_page.get("buttons", [])):
                if b["index"] == btn_index:
                    self._current_page["buttons"][i] = dlg.result_data
                    break
            if self._scene_widget:
                self._scene_widget.refresh_scene(self._current_page)

    def _edit_knob(self, knob_index: int, knob_data: dict):
        dlg = KnobEditorDialog(knob_data, self)
        if dlg.exec() and dlg.result_data:
            for i, k in enumerate(self._current_page.get("knobs", [])):
                if k["index"] == knob_index:
                    self._current_page["knobs"][i] = dlg.result_data
                    break
            if self._scene_widget:
                self._scene_widget.refresh_scene(self._current_page)

    def _edit_nav_button(self, nav_id: str, nav_data: dict):
        dlg = NavButtonEditorDialog(nav_data, self)
        if dlg.exec() and dlg.result_data:
            for i, nb in enumerate(self._current_page.get("nav_buttons", [])):
                if nb["id"] == nav_id:
                    self._current_page["nav_buttons"][i] = dlg.result_data
                    break
            if self._scene_widget:
                self._scene_widget.refresh_scene(self._current_page)

    def _rename_page(self):
        """Umbenennen über den Bleistift-Button im SceneWidget."""
        if not self._current_page:
            return
        old_name = self._current_page.get("name", "")
        new_name, ok = QInputDialog.getText(
            self, "Vorlage umbenennen", "Neuer Name:", text=old_name
        )
        if ok and new_name.strip():
            self._current_page["name"] = new_name.strip()
            if self._scene_widget and self._scene_widget._name_label:
                self._scene_widget._name_label.setText(new_name.strip())
            idx = self._combo.currentIndex()
            if 0 <= idx < self._combo.count():
                self._combo.setItemText(idx, new_name.strip())

    # ── Aktionen ───────────────────────────────────────────────────────────────

    def _save_page(self):
        """Schreibt _current_page (inkl. nicht gespeicherter Änderungen) in die JSON-Datei."""
        if not self._current_page:
            return
        page_id = self._current_page.get("id", "")
        path    = os.path.join(PAGES_DIR, f"{page_id}.json")
        data    = copy.deepcopy(self._current_page)
        os.makedirs(PAGES_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # Cache aktualisieren
        cfg._pages_cache[page_id] = data
        # Lokale Liste synchronisieren
        for i, p in enumerate(self._pages):
            if p.get("id") == page_id:
                self._pages[i] = copy.deepcopy(self._current_page)
                break
        QMessageBox.information(
            self, "Gespeichert",
            f"Vorlage «{self._current_page.get('name', page_id)}» wurde gespeichert."
        )

    def _delete_page(self):
        """Löscht die aktuelle Vorlage nach Bestätigung."""
        if not self._current_page:
            return
        name    = self._current_page.get("name", "diese Vorlage")
        page_id = self._current_page.get("id", "")
        reply = QMessageBox.warning(
            self, "Vorlage löschen",
            f"Vorlage «{name}» wirklich löschen?\n\n"
            "Diese Aktion kann nicht rückgängig gemacht werden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        path = os.path.join(PAGES_DIR, f"{page_id}.json")
        try:
            os.remove(path)
        except Exception:
            pass
        cfg._pages_cache.pop(page_id, None)
        self.reload()

    def _apply_page(self):
        """Fügt die Vorlage als neue Szene am Ende hinzu (überschreibt nichts)."""
        if not self._current_page:
            return

        config      = cfg.get()
        scene_index = len(config.get("scenes", []))   # neuer Index = bisherige Anzahl

        # Neue Szene aus Vorlage aufbauen
        new_scene = copy.deepcopy(self._current_page)
        new_scene["id"]          = f"scene_{scene_index}"
        new_scene["source_page"] = self._current_page.get("id", "")
        config.setdefault("scenes", []).append(new_scene)
        cfg.save()

        self.page_applied.emit(self._current_page.get("id", ""), scene_index)


# ── ButtonLibraryPanel ────────────────────────────────────────────────────────

class ButtonLibraryPanel(QWidget):
    """
    Kategorisierte Button-Bibliothek.
    Links: Kategorie-Liste. Rechts: Button-Grid.
    """
    button_selected = Signal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categories: list[dict] = []
        self._setup_ui()
        self.reload()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(52)
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)
        hl.setSpacing(10)
        title = QLabel("Button-Bibliothek")
        f = QFont(); f.setPointSize(14); f.setBold(True)
        title.setFont(f)
        hl.addWidget(title)
        hl.addStretch()
        hint = QLabel("Klicken zum Zuweisen · Rechtsklick für Optionen")
        hint.setObjectName("Subtitle")
        hl.addWidget(hint)
        new_btn = QPushButton("+ Neuer Button")
        new_btn.setObjectName("GhostButton")
        new_btn.setFixedHeight(30)
        new_btn.clicked.connect(self._create_new_button)
        hl.addWidget(new_btn)
        root.addWidget(header)

        # Splitter: Kategorien | Buttons
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Kategorie-Liste
        self._cat_list = QListWidget()
        self._cat_list.setFixedWidth(160)
        self._cat_list.currentRowChanged.connect(self._on_category_changed)
        splitter.addWidget(self._cat_list)

        # Rechte Seite: Scroll + Flow
        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.setContentsMargins(0, 0, 0, 0)

        self._btn_scroll = QScrollArea()
        self._btn_scroll.setWidgetResizable(True)
        self._btn_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Wrapper: Grid oben, Stretch-Spacer unten.
        # setWidgetResizable(True) dehnt den Wrapper auf volle Viewport-Höhe;
        # der Stretch füllt den leeren Bereich — das Grid bleibt kompakt oben.
        scroll_container = QWidget()
        sc_layout = QVBoxLayout(scroll_container)
        sc_layout.setContentsMargins(0, 0, 0, 0)
        sc_layout.setSpacing(0)
        self._btn_grid = ButtonGridWidget()
        sc_layout.addWidget(self._btn_grid)
        sc_layout.addStretch(1)
        self._btn_scroll.setWidget(scroll_container)
        right_l.addWidget(self._btn_scroll)

        splitter.addWidget(right_w)
        splitter.setSizes([160, 700])
        root.addWidget(splitter, 1)

    def reload(self):
        data = cfg.load_buttons()
        self._categories = data.get("categories", [])
        self._cat_list.clear()
        for cat in self._categories:
            self._cat_list.addItem(cat.get("name", "?"))
        if self._categories:
            self._cat_list.setCurrentRow(0)

    def _on_category_changed(self, idx: int):
        if idx < 0 or idx >= len(self._categories):
            return
        cat = self._categories[idx]
        self._show_buttons(cat.get("buttons", []),
                           is_custom=cat.get("id") == "custom")

    def _show_buttons(self, buttons: list, is_custom: bool = False):
        self._btn_grid.clear_widgets()
        for btn in buttons:
            card = _ButtonCard(btn, is_custom=is_custom)
            card.clicked_assign.connect(self.button_selected)
            if is_custom:
                card.edit_requested.connect(self._edit_custom_button)
                card.delete_requested.connect(self._delete_custom_button)
            self._btn_grid.add_widget(card)

    # ── Eigene Buttons erstellen / bearbeiten / löschen ───────────────────────

    def _create_new_button(self):
        """Öffnet den Editor mit einer leeren Vorlage."""
        blank = {"index": 0, "label": "", "icon": None, "action": None}
        dlg = ButtonEditorDialog(blank, self)
        dlg.setWindowTitle("Neuer Button")
        if dlg.exec() and dlg.result_data:
            result = dlg.result_data
            lib_btn = {
                "label":  result.get("label", ""),
                "icon":   result.get("icon"),
                "action": result.get("action"),
            }
            cfg.add_custom_button(lib_btn)
            self._reload_and_select_custom()

    def _edit_custom_button(self, btn: dict):
        """Öffnet den Editor vorausgefüllt mit dem vorhandenen Button."""
        edit_data = {
            "index":  0,
            "label":  btn.get("label", ""),
            "icon":   btn.get("icon"),
            "action": btn.get("action"),
        }
        dlg = ButtonEditorDialog(edit_data, self)
        dlg.setWindowTitle(f"Button bearbeiten — {btn.get('label', '')}")
        if dlg.exec() and dlg.result_data:
            result = dlg.result_data
            updated = {
                "id":     btn["id"],
                "label":  result.get("label", ""),
                "icon":   result.get("icon"),
                "action": result.get("action"),
            }
            cfg.update_custom_button(updated)
            self._reload_and_select_custom()

    def _delete_custom_button(self, btn: dict):
        """Löscht einen eigenen Button nach Bestätigung."""
        name  = btn.get("label", "diesen Button")
        reply = QMessageBox.warning(
            self, "Button löschen",
            f"Button «{name}» aus der Bibliothek löschen?\n\n"
            "Diese Aktion kann nicht rückgängig gemacht werden.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        cfg.delete_custom_button(btn["id"])
        self._reload_and_select_custom()

    def _reload_and_select_custom(self):
        """Bibliothek neu laden und zur 'Eigene Buttons'-Kategorie springen."""
        self.reload()
        for i, cat in enumerate(self._categories):
            if cat.get("id") == "custom":
                self._cat_list.setCurrentRow(i)
                break


# ── _ButtonCard ───────────────────────────────────────────────────────────────

class _ButtonCard(QFrame):
    """Mini-Karte für einen Library-Button."""
    clicked_assign  = Signal(dict)
    edit_requested  = Signal(dict)   # nur für eigene Buttons
    delete_requested = Signal(dict)  # nur für eigene Buttons

    def __init__(self, btn: dict, is_custom: bool = False, parent=None):
        super().__init__(parent)
        self._btn       = btn
        self._is_custom = is_custom
        self.setObjectName("Card")
        self.setFixedSize(90, 112)   # etwas breiter für lange Labels
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if is_custom:
            self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            self.customContextMenuRequested.connect(self._show_context_menu)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 8, 6, 6)
        layout.setSpacing(4)

        icon_lbl = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        icon_lbl.setFixedSize(56, 56)
        pm = _icon_to_pixmap(self._btn, size=52)
        icon_lbl.setPixmap(pm)
        icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        text_lbl = QLabel(self._btn.get("label", ""),
                           alignment=Qt.AlignmentFlag.AlignCenter)
        text_lbl.setWordWrap(True)
        text_lbl.setFixedWidth(78)    # Kartenbreite minus 2× Margin
        text_lbl.setMinimumHeight(16)
        text_lbl.setMaximumHeight(30) # max 2 Zeilen
        text_lbl.setStyleSheet("color: #AEAEB2; font-size: 10px;")
        text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text_lbl, 0, Qt.AlignmentFlag.AlignCenter)

        action = self._btn.get("action") or {}
        tip_suffix = "<br><i>Rechtsklick: Bearbeiten / Löschen</i>" if self._is_custom else "<br><i>Klicken um zuzuweisen</i>"
        self.setToolTip(
            f"<b>{self._btn.get('label', '')}</b><br>"
            f"Aktion: {action.get('type', '—')}"
            f"{tip_suffix}"
        )

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        edit_act   = QAction("Bearbeiten", self)
        delete_act = QAction("Löschen",    self)
        edit_act.triggered.connect(lambda: self.edit_requested.emit(self._btn))
        delete_act.triggered.connect(lambda: self.delete_requested.emit(self._btn))
        menu.addAction(edit_act)
        menu.addSeparator()
        menu.addAction(delete_act)
        menu.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_assign.emit(self._btn)
        super().mousePressEvent(event)
