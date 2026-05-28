"""
SceneWidget — visuelle Darstellung einer Szene im Konfigurations-UI.
Layout entspricht dem physischen Gerät:
  Links oben:   6 LCD-Buttons (3×2)
  Links unten:  3 Nav-Buttons (◀ Zurück | Home | Weiter ▶)
  Rechts oben:  1 großer Knob (Knob 1)
  Rechts unten: 2 kleine Knobs nebeneinander (Knob 2, Knob 3)
"""

import sys, os, io
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                              QLabel, QFrame, QSizePolicy, QPushButton,
                              QApplication)
from PySide6.QtCore import Signal, Qt, QSize, QEvent, QMimeData
from PySide6.QtGui import QPixmap, QFont, QTransform, QPainter, QColor, QDrag

from icons import make_icon, load_app_icon

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLOT_W       = 88
SLOT_H       = 88
ICON_DISP    = 56    # Icon-Anzeigegröße in LCD-Buttons
NAV_BTN_W    = 88   # Gleiche Breite wie LCD-Buttons → bündige Ausrichtung
NAV_BTN_H    = 40   # Kompakthöhe (keine LCD-Anzeige)
KNOB_D_LARGE = 80   # Großer Regler (oben rechts)
KNOB_D_SMALL = 52   # Kleine Regler (unten rechts, nebeneinander)


# ── Icon-Rendering für UI-Vorschau ─────────────────────────────────────────────

def _icon_to_pixmap(btn: dict, size: int = ICON_DISP) -> QPixmap:
    """
    Rendert ein Button-Icon als QPixmap für die UI-Anzeige.
    Kein Gerätedrehung — natürliche Orientierung.
    """
    icon  = btn.get("icon") or {}
    itype = icon.get("type", "text")
    label = btn.get("label", "")

    try:
        if itype == "app":
            data = load_app_icon(icon["path"], for_device=False)
        elif itype == "file":
            path = icon.get("path", "")
            if path and not os.path.isabs(path):
                path = os.path.join(BASE_DIR, path)
            data = load_app_icon(path, for_device=False)
        elif itype == "emoji":
            data = make_icon(label, icon.get("emoji", ""),
                             tuple(icon.get("bg", [30, 30, 40])),
                             for_device=False)
        else:
            data = make_icon(label, bg=tuple(icon.get("bg", [30, 30, 40])),
                             for_device=False)
    except Exception:
        data = make_icon(label, for_device=False)

    pm = QPixmap()
    pm.loadFromData(data)
    return pm.scaled(size, size,
                     Qt.AspectRatioMode.KeepAspectRatio,
                     Qt.TransformationMode.SmoothTransformation)


# ── ButtonSlot ─────────────────────────────────────────────────────────────────

class ButtonSlot(QWidget):
    """
    Klickbarer Button-Slot mit Icon-Vorschau und Label.
    Unterstützt Drag & Drop zum Tauschen von LCD-Buttons untereinander.
    """
    clicked_edit   = Signal(dict)
    swap_requested = Signal(int, int)   # (source_index, target_index)

    _DRAG_MIME = "application/x-deckpad-button"

    def __init__(self, btn_data: dict, parent=None):
        super().__init__(parent)
        self._data            = btn_data
        self._drag_start_pos  = None
        self._drag_initiated  = False
        self.setFixedSize(SLOT_W, SLOT_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ButtonSlot")
        self.setAcceptDrops(True)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(2)

        self._icon_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setFixedSize(ICON_DISP, ICON_DISP)
        self._icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._text_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._text_label.setFixedHeight(18)
        self._text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        font = QFont()
        font.setPointSize(11)
        self._text_label.setFont(font)
        self._text_label.setStyleSheet("color: #C7C7CC;")

        layout.addStretch()
        layout.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._text_label, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def update_data(self, btn_data: dict):
        self._data = btn_data
        self._refresh()

    def _refresh(self):
        label = self._data.get("label", "")
        pm = _icon_to_pixmap(self._data)
        self._icon_label.setPixmap(pm)
        display = label if len(label) <= 9 else label[:8] + "…"
        self._text_label.setText(display)
        idx = self._data.get("index", "?")
        action = self._data.get("action")
        action_str = action.get("type", "—") if action else "keine Aktion"
        self.setToolTip(f"<b>Slot {idx}: {label}</b><br>Aktion: {action_str}"
                        "<br><i>Klicken zum Bearbeiten | Ziehen zum Tauschen</i>")

    # ── Maus-Events: Klick vs. Drag unterscheiden ──────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_initiated = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        dist = (event.pos() - self._drag_start_pos).manhattanLength()
        if dist < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._drag_initiated = True
        self._start_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._drag_initiated:
            self.clicked_edit.emit(self._data)
        self._drag_start_pos = None
        self._drag_initiated = False
        super().mouseReleaseEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(self._DRAG_MIME, str(self._data["index"]).encode())
        drag.setMimeData(mime)
        # Widget-Screenshot als Drag-Bild
        pm = self.grab()
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        drag.exec(Qt.DropAction.MoveAction)

    # ── Drop-Ziel ──────────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self._DRAG_MIME):
            try:
                src_idx = int(bytes(event.mimeData().data(self._DRAG_MIME)).decode())
            except Exception:
                event.ignore()
                return
            if src_idx != self._data["index"]:
                self._set_drop_highlight(True)
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._set_drop_highlight(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._set_drop_highlight(False)
        if event.mimeData().hasFormat(self._DRAG_MIME):
            try:
                src_idx = int(bytes(event.mimeData().data(self._DRAG_MIME)).decode())
            except Exception:
                event.ignore()
                return
            tgt_idx = self._data["index"]
            if src_idx != tgt_idx:
                self.swap_requested.emit(src_idx, tgt_idx)
            event.acceptProposedAction()
        else:
            event.ignore()

    def _set_drop_highlight(self, on: bool):
        self.setProperty("dropTarget", on)
        self.style().unpolish(self)
        self.style().polish(self)

    # ── Hover ──────────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)


# ── NavButtonSlot ──────────────────────────────────────────────────────────────

# Symbole für die drei Nav-Buttons (keine Emoji — Geometric Shapes Block, sicher)
_NAV_SYMBOLS = {"prev": "◀", "home": "■", "next": "▶"}
_NAV_LABELS  = {"prev": "Zurück", "home": "Home", "next": "Weiter"}

class NavButtonSlot(QWidget):
    """Klickbarer Slot für einen der drei Navigations-Buttons (Prev / Home / Next)."""
    clicked_edit = Signal(dict)

    def __init__(self, nav_data: dict, parent=None):
        super().__init__(parent)
        self._data = nav_data
        self.setFixedSize(NAV_BTN_W, NAV_BTN_H)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("NavButtonSlot")
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(1)

        self._sym_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._sym_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        sym_font = QFont()
        sym_font.setPointSize(12)
        self._sym_label.setFont(sym_font)
        self._sym_label.setStyleSheet("color: #AEAEB2;")

        self._text_label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._text_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        txt_font = QFont()
        txt_font.setPointSize(9)
        self._text_label.setFont(txt_font)
        self._text_label.setStyleSheet("color: #8E8E93;")

        layout.addWidget(self._sym_label)
        layout.addWidget(self._text_label)

    def update_data(self, nav_data: dict):
        self._data = nav_data
        self._refresh()

    def _refresh(self):
        nav_id = self._data.get("id", "")
        label  = self._data.get("label", _NAV_LABELS.get(nav_id, nav_id))
        action = self._data.get("action")

        self._sym_label.setText(_NAV_SYMBOLS.get(nav_id, "?"))
        display = label if len(label) <= 9 else label[:8] + "…"
        self._text_label.setText(display)

        atype = action.get("type", "—") if action else "keine Aktion"
        self.setToolTip(f"<b>Nav: {nav_id}</b><br>Label: {label}"
                        f"<br>Aktion: {atype}"
                        "<br><i>Klicken zum Bearbeiten</i>")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked_edit.emit(self._data)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().leaveEvent(event)


# ── KnobSlot ───────────────────────────────────────────────────────────────────

class KnobSlot(QWidget):
    """
    Darstellung eines Knobs mit Aktion-Label. Unterstützt variable Kreisgrößen.
    Unterstützt Drag & Drop zum Tauschen von Knobs untereinander.
    """
    clicked_edit   = Signal(dict)
    swap_requested = Signal(int, int)   # (source_index, target_index)

    _DRAG_MIME = "application/x-deckpad-knob"

    def __init__(self, knob_data: dict, diameter: int = KNOB_D_SMALL, parent=None):
        super().__init__(parent)
        self._data            = knob_data
        self._d               = diameter
        self._drag_start_pos  = None
        self._drag_initiated  = False
        self.setFixedSize(diameter + 24, diameter + 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("KnobSlot")
        self.setAcceptDrops(True)
        self._setup_ui()
        self._refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._circle = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._circle.setFixedSize(self._d, self._d)
        self._circle.setObjectName("KnobCircle")
        self._circle.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        # Border-radius inline setzen (abhängig von Diameter)
        self._refresh_circle_style(highlight=False)

        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._label.setFixedHeight(16)
        self._label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        font = QFont()
        font.setPointSize(10)
        self._label.setFont(font)
        self._label.setStyleSheet("color: #C7C7CC;")

        layout.addWidget(self._circle, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label,  0, Qt.AlignmentFlag.AlignCenter)

    def _refresh_circle_style(self, highlight: bool = False):
        r  = self._d // 2
        fs = max(11, self._d // 5)
        border_color = "#0A84FF" if highlight else "#636366"   # mauve : surface2
        self._circle.setStyleSheet(
            f"border-radius: {r}px; font-size: {fs}px; border-color: {border_color};"
        )

    def _refresh(self):
        idx    = self._data.get("index", "?")
        label  = self._data.get("label", "—")
        action = self._data.get("action")

        self._circle.setText(str(idx))

        display = label if len(label) <= 10 else label[:9] + "…"
        self._label.setText(display)

        atype = action.get("type", "—") if action else "keine Aktion"
        self.setToolTip(f"<b>Knob {idx}: {label}</b><br>Aktion: {atype}"
                        "<br><i>Klicken zum Bearbeiten | Ziehen zum Tauschen</i>")

    def update_data(self, knob_data: dict):
        self._data = knob_data
        self._refresh()

    # ── Maus-Events: Klick vs. Drag unterscheiden ──────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
            self._drag_initiated = False
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return
        if self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        dist = (event.pos() - self._drag_start_pos).manhattanLength()
        if dist < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return
        self._drag_initiated = True
        self._start_drag()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._drag_initiated:
            self.clicked_edit.emit(self._data)
        self._drag_start_pos = None
        self._drag_initiated = False
        super().mouseReleaseEvent(event)

    def _start_drag(self):
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(self._DRAG_MIME, str(self._data["index"]).encode())
        drag.setMimeData(mime)
        pm = self.grab()
        drag.setPixmap(pm)
        drag.setHotSpot(pm.rect().center())
        drag.exec(Qt.DropAction.MoveAction)

    # ── Drop-Ziel ──────────────────────────────────────────────────────────────

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(self._DRAG_MIME):
            try:
                src_idx = int(bytes(event.mimeData().data(self._DRAG_MIME)).decode())
            except Exception:
                event.ignore()
                return
            if src_idx != self._data["index"]:
                self._refresh_circle_style(highlight=True)
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._refresh_circle_style(highlight=False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self._refresh_circle_style(highlight=False)
        if event.mimeData().hasFormat(self._DRAG_MIME):
            try:
                src_idx = int(bytes(event.mimeData().data(self._DRAG_MIME)).decode())
            except Exception:
                event.ignore()
                return
            tgt_idx = self._data["index"]
            if src_idx != tgt_idx:
                self.swap_requested.emit(src_idx, tgt_idx)
            event.acceptProposedAction()
        else:
            event.ignore()


# ── _DoubleClickLabel ──────────────────────────────────────────────────────────

class _DoubleClickLabel(QLabel):
    """QLabel das bei Doppelklick ein Signal aussendet."""
    double_clicked = Signal()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit()
        super().mouseDoubleClickEvent(event)


# ── SceneWidget ────────────────────────────────────────────────────────────────

class SceneWidget(QWidget):
    """
    Vollständige Szenen-Ansicht mit physisch korrektem Layout:
      Links:  6 LCD-Buttons (3×2) + 3 Nav-Buttons (◀ Home ▶)
      Rechts: 1 großer Knob oben + 2 kleine Knobs unten nebeneinander
    """
    button_edit_requested     = Signal(int, dict)   # (btn_index, btn_data)
    knob_edit_requested       = Signal(int, dict)   # (knob_index, knob_data)
    nav_button_edit_requested = Signal(str, dict)   # (nav_id, nav_data)
    buttons_swapped           = Signal(int, int)    # (src_btn_index, tgt_btn_index)
    knobs_swapped             = Signal(int, int)    # (src_knob_index, tgt_knob_index)
    delete_requested          = Signal()
    rename_requested          = Signal()
    save_to_library_requested = Signal()

    def __init__(self, scene_data: dict, parent=None, show_scene_actions: bool = True):
        super().__init__(parent)
        self._scene              = scene_data
        self._btn_slots          = {}
        self._knob_slots         = {}
        self._nav_slots          = {}
        self._name_label         = None
        self._show_scene_actions = show_scene_actions
        self._setup_ui()

    def _setup_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(20, 20, 20, 20)
        main.setSpacing(16)

        # ── Szenenname ────────────────────────────────────────────────────────
        name_row = QHBoxLayout()
        name_row.setContentsMargins(0, 0, 0, 0)
        name_row.setSpacing(8)

        self._name_label = _DoubleClickLabel(self._scene.get("name", "Szene"))
        self._name_label.double_clicked.connect(self.rename_requested)
        self._name_label.setCursor(Qt.CursorShape.IBeamCursor)
        self._name_label.setToolTip("Doppelklick zum Umbenennen")
        font = QFont()
        font.setPointSize(14)
        font.setWeight(QFont.Weight.Bold)
        self._name_label.setFont(font)
        self._name_label.setObjectName("SceneName")
        name_row.addWidget(self._name_label)

        pencil_btn = QPushButton("✎")
        pencil_btn.setFlat(True)
        pencil_btn.setFixedSize(22, 22)
        pencil_btn.setToolTip("Umbenennen")
        pencil_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #636366; border: none;"
            " font-size: 14px; padding: 0; }"
            "QPushButton:hover { color: #FFFFFF; }"
        )
        pencil_btn.clicked.connect(self.rename_requested)
        name_row.addWidget(pencil_btn)
        name_row.addStretch()
        main.addLayout(name_row)

        # ── Gerät-Rahmen (in eigene Zeile mit Trailing-Stretch → kein horizontales Dehnen) ──
        frame = QFrame()
        frame.setObjectName("DeviceFrame")
        frame_layout = QHBoxLayout(frame)
        frame_layout.setContentsMargins(14, 14, 14, 14)
        frame_layout.setSpacing(14)

        # ── Linke Spalte: LCD-Buttons + Nav-Buttons ───────────────────────────
        left_col = QVBoxLayout()
        left_col.setSpacing(8)
        left_col.setContentsMargins(0, 0, 0, 0)

        # LCD-Button-Grid (3 Spalten × 2 Zeilen)
        grid = QGridLayout()
        grid.setSpacing(8)
        grid.setContentsMargins(0, 0, 0, 0)

        buttons = {b["index"]: b for b in self._scene.get("buttons", [])}
        for row in range(2):
            for col in range(3):
                idx  = row * 3 + col + 1
                data = buttons.get(idx, {"index": idx, "label": "",
                                         "icon": None, "action": None})
                slot = ButtonSlot(data)
                slot.clicked_edit.connect(
                    lambda d, i=idx: self.button_edit_requested.emit(i, d)
                )
                slot.swap_requested.connect(self.buttons_swapped)
                self._btn_slots[idx] = slot
                grid.addWidget(slot, row, col)

        left_col.addLayout(grid)

        # Nav-Buttons-Zeile (◀ Home ▶)
        nav_row = QHBoxLayout()
        nav_row.setSpacing(8)
        nav_row.setContentsMargins(0, 0, 0, 0)

        nav_buttons = {b["id"]: b for b in self._scene.get("nav_buttons", [])}
        for nav_id in ("prev", "home", "next"):
            data = nav_buttons.get(nav_id, {
                "id": nav_id,
                "label": _NAV_LABELS.get(nav_id, nav_id),
                "action": {"type": f"scene_{nav_id}"},
            })
            slot = NavButtonSlot(data)
            slot.clicked_edit.connect(
                lambda d, nid=nav_id: self.nav_button_edit_requested.emit(nid, d)
            )
            self._nav_slots[nav_id] = slot
            nav_row.addWidget(slot)

        left_col.addLayout(nav_row)
        frame_layout.addLayout(left_col)

        # ── Rechte Spalte: 1 großer Knob oben + 2 kleine unten ───────────────
        # Kein Stretch außen — rechte Spalte sitzt direkt neben der linken.
        right_col = QVBoxLayout()
        right_col.setSpacing(0)
        right_col.setContentsMargins(0, 0, 0, 0)

        knobs = {k["index"]: k for k in self._scene.get("knobs", [])}

        # Knob 1 — groß, oben (bündig mit Button-Grid)
        data1 = knobs.get(1, {"index": 1, "label": "—", "action": None})
        large_knob = KnobSlot(data1, diameter=KNOB_D_LARGE)
        large_knob.clicked_edit.connect(
            lambda d: self.knob_edit_requested.emit(1, d)
        )
        large_knob.swap_requested.connect(self.knobs_swapped)
        self._knob_slots[1] = large_knob
        right_col.addWidget(large_knob, 0, Qt.AlignmentFlag.AlignCenter)

        # Flexibler Zwischenraum (analog Abstand Grid ↔ Nav in linker Spalte)
        right_col.addStretch(1)

        # Knobs 2 & 3 — klein, nebeneinander unten (bündig mit Nav-Buttons)
        small_row = QHBoxLayout()
        small_row.setSpacing(10)
        small_row.setContentsMargins(0, 0, 0, 0)

        for idx in (2, 3):
            data = knobs.get(idx, {"index": idx, "label": "—", "action": None})
            slot = KnobSlot(data, diameter=KNOB_D_SMALL)
            slot.clicked_edit.connect(
                lambda d, i=idx: self.knob_edit_requested.emit(i, d)
            )
            slot.swap_requested.connect(self.knobs_swapped)
            self._knob_slots[idx] = slot
            small_row.addWidget(slot, 0, Qt.AlignmentFlag.AlignCenter)

        right_col.addLayout(small_row)
        frame_layout.addLayout(right_col)

        # Frame in eigene Zeile — Trailing-Stretch verhindert Dehnung auf Fensterbreite
        frame_row = QHBoxLayout()
        frame_row.setContentsMargins(0, 0, 0, 0)
        frame_row.setSpacing(0)
        frame_row.addWidget(frame)
        frame_row.addStretch()
        main.addLayout(frame_row)
        main.addStretch()

        # ── Untere Aktionsleiste: nur in Szenen-Ansicht (nicht in Bibliothek) ──
        if self._show_scene_actions:
            del_row = QHBoxLayout()
            del_row.setContentsMargins(0, 0, 0, 0)

            lib_btn = QPushButton("In Bibliothek speichern")
            lib_btn.setObjectName("GhostButton")
            lib_btn.setFixedHeight(32)
            lib_btn.setToolTip("Aktuelle Seite als Vorlage in der Seiten-Bibliothek speichern")
            lib_btn.clicked.connect(self.save_to_library_requested)
            del_row.addWidget(lib_btn)

            del_row.addStretch()

            del_btn = QPushButton("Seite löschen")
            del_btn.setObjectName("DangerButton")
            del_btn.setFixedHeight(32)
            del_btn.clicked.connect(self.delete_requested)
            del_row.addWidget(del_btn)

            main.addLayout(del_row)

    def refresh_scene(self, scene_data: dict):
        """Aktualisiert alle Slots mit neuen Szenen-Daten."""
        self._scene = scene_data
        if self._name_label:
            self._name_label.setText(scene_data.get("name", "Szene"))

        buttons = {b["index"]: b for b in scene_data.get("buttons", [])}
        for idx, slot in self._btn_slots.items():
            slot.update_data(buttons.get(idx, {"index": idx, "label": "",
                                                "icon": None, "action": None}))

        knobs = {k["index"]: k for k in scene_data.get("knobs", [])}
        for idx, slot in self._knob_slots.items():
            slot.update_data(knobs.get(idx, {"index": idx, "label": "—",
                                              "action": None}))

        nav_buttons = {b["id"]: b for b in scene_data.get("nav_buttons", [])}
        for nav_id, slot in self._nav_slots.items():
            slot.update_data(nav_buttons.get(nav_id, {
                "id": nav_id,
                "label": _NAV_LABELS.get(nav_id, nav_id),
                "action": {"type": f"scene_{nav_id}"},
            }))
