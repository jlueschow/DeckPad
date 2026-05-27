"""
Lädt und speichert config.json, stellt Standard-Config bereit.

Pfad-Strategie:
  Entwicklung  → data/ relativ zum Projektverzeichnis
  PyInstaller  → ~/Library/Application Support/DeckPad/  (schreibbar)
                 Beim ersten Start wird buttons.json aus dem Bundle kopiert.
"""

import json
import os
import sys
import copy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Pfade je nach Laufzeitumgebung ────────────────────────────────────────────

if getattr(sys, "frozen", False):
    # PyInstaller-Bundle: Nutzerdaten in ~/Library/Application Support/DeckPad/
    _DATA_DIR      = os.path.expanduser("~/Library/Application Support/DeckPad")
    _BUNDLE_ASSETS = getattr(sys, "_MEIPASS", BASE_DIR)  # Bundle-Ressourcen (read-only)
else:
    _DATA_DIR      = os.path.join(BASE_DIR, "data")
    _BUNDLE_ASSETS = None

CONFIG_PATH  = os.path.join(_DATA_DIR, "config.json")
PAGES_DIR    = os.path.join(_DATA_DIR, "library", "pages")
BUTTONS_PATH = os.path.join(_DATA_DIR, "library", "buttons.json")


def _init_user_data():
    """
    Initialisiert ~/Library/Application Support/DeckPad/ beim ersten Start.
    Kopiert buttons.json aus dem Bundle-Ressourcen-Verzeichnis.
    Muss vor dem ersten ConfigManager.load() aufgerufen werden.
    """
    if not getattr(sys, "frozen", False):
        return   # Nur im Bundle nötig

    lib_dir = os.path.join(_DATA_DIR, "library")
    pages_dir = os.path.join(lib_dir, "pages")
    os.makedirs(pages_dir, exist_ok=True)

    # buttons.json aus Bundle kopieren falls noch nicht vorhanden
    if not os.path.exists(BUTTONS_PATH) and _BUNDLE_ASSETS:
        src = os.path.join(_BUNDLE_ASSETS, "data", "library", "buttons.json")
        if os.path.exists(src):
            import shutil
            shutil.copy2(src, BUTTONS_PATH)


class ConfigManager:
    def __init__(self):
        self._config = None
        self._pages_cache = {}
        self._buttons_cache = None

    # ── Config ────────────────────────────────────────────────────────────────

    def load(self) -> dict:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                self._config = json.load(f)
        else:
            self._config = self._default_config()
        # Migration: nav_buttons in bestehende Szenen einfügen falls fehlend
        for scene in self._config.get("scenes", []):
            if "nav_buttons" not in scene:
                scene["nav_buttons"] = self._default_nav_buttons()
            # Migration: press_action in bestehende Knobs einfügen falls fehlend
            for knob in scene.get("knobs", []):
                if "press_action" not in knob:
                    knob["press_action"] = None
        return self._config

    def save(self, config: dict = None):
        if config:
            self._config = config
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2, ensure_ascii=False)

    def get(self) -> dict:
        if self._config is None:
            self.load()
        return self._config

    def set_brightness(self, value: int):
        self.get()["brightness"] = max(0, min(100, value))
        self.save()

    def set_active_scene(self, index: int):
        self.get()["active_scene"] = index
        self.save()

    def get_scene(self, index: int) -> dict:
        return self.get()["scenes"][index]

    def update_scene(self, index: int, scene: dict):
        self.get()["scenes"][index] = scene
        self.save()

    def update_button(self, scene_index: int, button_index: int, button_data: dict):
        self.get()["scenes"][scene_index]["buttons"][button_index] = button_data
        self.save()

    def add_scene(self, name: str = None) -> int:
        """Fügt eine neue leere Szene am Ende hinzu. Gibt den neuen Index zurück."""
        scenes = self.get()["scenes"]
        new_index = len(scenes)
        if name is None:
            name = f"Szene {new_index + 1}"
        scenes.append(self._empty_scene(new_index, name))
        self.save()
        return new_index

    def move_scene(self, from_idx: int, to_idx: int):
        """
        Verschiebt eine Szene von from_idx nach to_idx.
        Aktualisiert active_scene entsprechend.
        """
        scenes = self.get()["scenes"]
        n = len(scenes)
        if not (0 <= from_idx < n and 0 <= to_idx < n) or from_idx == to_idx:
            return
        scenes.insert(to_idx, scenes.pop(from_idx))
        for i, s in enumerate(scenes):
            s["id"] = f"scene_{i}"
        # active_scene Index nachführen
        active = self.get().get("active_scene", 0)
        if active == from_idx:
            self.get()["active_scene"] = to_idx
        elif from_idx < to_idx and from_idx < active <= to_idx:
            self.get()["active_scene"] = active - 1
        elif from_idx > to_idx and to_idx <= active < from_idx:
            self.get()["active_scene"] = active + 1
        self.save()

    def delete_scene(self, index: int):
        """Löscht Szene an Position index. Mindestens eine Szene bleibt erhalten."""
        scenes = self.get()["scenes"]
        if len(scenes) <= 1:
            return
        scenes.pop(index)
        # IDs neu durchnummerieren
        for i, scene in enumerate(scenes):
            scene["id"] = f"scene_{i}"
        # active_scene ggf. korrigieren
        active = self.get().get("active_scene", 0)
        if active >= len(scenes):
            self.get()["active_scene"] = len(scenes) - 1
        self.save()

    def save_page(self, page: dict) -> str:
        """
        Speichert eine Seite in der Bibliothek.
        Erzeugt eine eindeutige page_id aus dem Namen (z. B. "Voice Control" → "voice_control").
        Falls die Datei bereits existiert wird _2, _3, … angehängt.
        Gibt die verwendete page_id zurück.
        """
        import re
        name    = page.get("name", "Seite")
        base_id = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "seite"
        os.makedirs(PAGES_DIR, exist_ok=True)
        page_id = base_id
        counter = 2
        while os.path.exists(os.path.join(PAGES_DIR, f"{page_id}.json")):
            page_id = f"{base_id}_{counter}"
            counter += 1
        page["id"] = page_id
        path = os.path.join(PAGES_DIR, f"{page_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(page, f, indent=2, ensure_ascii=False)
        self._pages_cache[page_id] = page
        return page_id

    def apply_page_to_scene(self, scene_index: int, page_id: str):
        """Übernimmt eine Bibliotheks-Seite als Szene."""
        page = self.load_page(page_id)
        if page:
            scene = copy.deepcopy(page)
            scene["id"] = f"scene_{scene_index}"
            scene["source_page"] = page_id
            self.get()["scenes"][scene_index] = scene
            self.save()

    # ── Seiten-Bibliothek ─────────────────────────────────────────────────────

    def load_all_pages(self) -> list[dict]:
        pages = []
        if not os.path.isdir(PAGES_DIR):
            return pages
        for fname in sorted(os.listdir(PAGES_DIR)):
            if fname.endswith(".json"):
                page = self.load_page(fname[:-5])
                if page:
                    pages.append(page)
        return pages

    def load_page(self, page_id: str) -> dict | None:
        if page_id in self._pages_cache:
            return self._pages_cache[page_id]
        path = os.path.join(PAGES_DIR, f"{page_id}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            page = json.load(f)
        self._pages_cache[page_id] = page
        return page

    # ── Button-Bibliothek ─────────────────────────────────────────────────────

    def load_buttons(self) -> dict:
        if self._buttons_cache:
            return self._buttons_cache
        if not os.path.exists(BUTTONS_PATH):
            return {"categories": []}
        with open(BUTTONS_PATH, "r", encoding="utf-8") as f:
            self._buttons_cache = json.load(f)
        return self._buttons_cache

    def _save_buttons(self, data: dict):
        """Schreibt buttons.json und leert den Cache."""
        self._buttons_cache = data
        os.makedirs(os.path.dirname(BUTTONS_PATH), exist_ok=True)
        with open(BUTTONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _custom_category(self, data: dict) -> dict:
        """Gibt die 'Eigene Buttons'-Kategorie zurück (legt sie bei Bedarf an)."""
        cat = next((c for c in data["categories"] if c["id"] == "custom"), None)
        if cat is None:
            cat = {"id": "custom", "name": "Eigene Buttons", "buttons": []}
            data["categories"].insert(0, cat)
        return cat

    def add_custom_button(self, btn: dict) -> str:
        """
        Fügt einen Benutzer-Button zur Kategorie 'Eigene Buttons' hinzu.
        Generiert eine eindeutige ID aus dem Label. Gibt die ID zurück.
        """
        import re
        data = copy.deepcopy(self.load_buttons())
        cat  = self._custom_category(data)

        label   = btn.get("label", "button")
        base_id = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "button"
        taken   = {b["id"] for b in cat["buttons"]}
        btn_id  = base_id
        counter = 2
        while btn_id in taken:
            btn_id = f"{base_id}_{counter}"
            counter += 1

        new_btn = copy.deepcopy(btn)
        new_btn["id"] = btn_id
        cat["buttons"].append(new_btn)
        self._save_buttons(data)
        return btn_id

    def update_custom_button(self, btn: dict):
        """Aktualisiert einen vorhandenen Benutzer-Button (Suche per id)."""
        data = copy.deepcopy(self.load_buttons())
        cat  = next((c for c in data["categories"] if c["id"] == "custom"), None)
        if cat is None:
            return
        for i, b in enumerate(cat["buttons"]):
            if b["id"] == btn["id"]:
                cat["buttons"][i] = copy.deepcopy(btn)
                break
        self._save_buttons(data)

    def delete_custom_button(self, btn_id: str):
        """Löscht einen Benutzer-Button. Entfernt die Kategorie wenn sie leer wird."""
        data = copy.deepcopy(self.load_buttons())
        cat  = next((c for c in data["categories"] if c["id"] == "custom"), None)
        if cat is None:
            return
        cat["buttons"] = [b for b in cat["buttons"] if b["id"] != btn_id]
        if not cat["buttons"]:
            data["categories"] = [c for c in data["categories"] if c["id"] != "custom"]
        self._save_buttons(data)

    # ── Standard-Config ────────────────────────────────────────────────────────

    def _default_config(self) -> dict:
        return {
            "version": "1.0",
            "brightness": 80,
            "active_scene": 0,
            "scenes": [
                self._empty_scene(0, "Szene 1"),
                self._empty_scene(1, "Szene 2"),
                self._empty_scene(2, "Szene 3"),
            ]
        }

    def _default_nav_buttons(self) -> list:
        return [
            {"id": "prev", "label": "Zurueck", "action": {"type": "scene_prev"}},
            {"id": "home", "label": "Home",    "action": {"type": "scene_home"}},
            {"id": "next", "label": "Weiter",  "action": {"type": "scene_next"}},
        ]

    def _empty_scene(self, index: int, name: str) -> dict:
        return {
            "id": f"scene_{index}",
            "name": name,
            "source_page": None,
            "buttons": [
                {"index": i, "label": "", "icon": None, "action": None}
                for i in range(1, 7)
            ],
            "knobs": [
                {"index": i, "label": "—", "action": None, "press_action": None}
                for i in range(1, 4)
            ],
            "nav_buttons": self._default_nav_buttons(),
        }


# Globale Instanz
cfg = ConfigManager()
