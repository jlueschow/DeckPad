"""
Scene definitions for AKP03E.
Each scene defines 6 LCD buttons and 3 knob handlers.
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
import actions
import icons


@dataclass
class Button:
    label:    str
    symbol:   str
    color:    tuple
    action:   Optional[Callable] = None  # called on button DOWN
    app_path: Optional[str]      = None  # .app-Pfad für echtes Icon (NSWorkspace)


@dataclass
class Knob:
    on_turn:  Optional[Callable] = None   # called with direction (+1/-1)
    on_press: Optional[Callable] = None


@dataclass
class Scene:
    name:    str
    buttons: list[Button]           # exactly 6
    knobs:   list[Knob] = field(default_factory=lambda: [Knob(), Knob(), Knob()])


# ── Szenario 1: Produktivität ──────────────────────────────────────────────

_vol_out    = actions.MediaVolumeKnob()
_brightness = actions.MediaBrightnessKnob()


def preload_knobs():
    pass  # no preloading needed with media key approach

SCENE_PRODUKTIVITAET = Scene(
    name="Produktivität",
    buttons=[
        Button("Obsidian",  "📓", (30, 90, 60),
               lambda: actions.open_app("Obsidian"),
               app_path="/Applications/05 Prototyp/Obsidian.app"),
        Button("Claude",    "🤖", (180, 100, 20),
               lambda: actions.open_app("Claude"),
               app_path="/Applications/05 Prototyp/Claude.app"),
        Button("Kalender",  "📅", (140, 50, 140),
               lambda: actions.open_app("Calendar"),
               app_path="/Volumes/Daten Johannes/08 Promotion/04 Software/AJAZZ AKP03E/assets/calendar_icon.png"),
        Button("Mail",      "✉", (180, 50, 50),
               lambda: actions.open_app("Mail"),
               app_path="/System/Applications/Mail.app"),
        Button("Safari",    "🧭", (0, 120, 200),
               lambda: actions.open_app("Safari"),
               app_path="/System/Volumes/Preboot/Cryptexes/App/System/Applications/Safari.app"),
        Button("Chrome",    "🌐", (30, 130, 60),
               lambda: actions.open_app("Google Chrome"),
               app_path="/Applications/Google Chrome.app"),
    ],
    knobs=[
        Knob(on_turn=_vol_out.turn),       # Regler 1: Ausgabelautstärke (mit OSD)
        Knob(on_turn=_vol_out.turn),       # Regler 2: auch Lautstärke (Mikrofon-Gain braucht CoreAudio)
        Knob(on_turn=_brightness.turn),    # Regler 3: Display-Helligkeit via BetterDisplay
    ]
)

# ── Szenario 2: Studio / TH OWL ───────────────────────────────────────────

_vol_monitor = actions.MediaVolumeKnob()

SCENE_STUDIO = Scene(
    name="Studio",
    buttons=[
        Button("Dante\nCtrl",   "🎛", (30, 60, 100),
               lambda: actions.open_app("Dante Controller")),
        Button("Preset 1",      "1️⃣", (40, 80, 40),
               lambda: _dante_preset(1)),
        Button("Preset 2",      "2️⃣", (40, 80, 40),
               lambda: _dante_preset(2)),
        Button("Clr\nRouting",  "🚫", (120, 40, 40),
               lambda: _dante_clear()),
        Button("DDM\nWeb UI",   "🌐", (60, 60, 100),
               lambda: actions.open_url("http://localhost")),   # DDM URL anpassen
        Button("Aufnahme",      "⏺", (180, 30, 30),
               lambda: _start_recording()),
    ],
    knobs=[
        Knob(on_turn=_vol_monitor.turn),    # Regler 1: Monitor-Lautstärke
        Knob(),
        Knob(),
    ]
)

# ── Szenario 3: Dante Voice Control ───────────────────────────────────────

SCENE_VOICE = Scene(
    name="Voice Ctrl",
    buttons=[
        Button("🎤 Sprache",  "🎤", (80, 20, 80),
               lambda: _voice_control_toggle()),
        Button("Route A",     "A",  (30, 80, 80),
               lambda: _dante_preset(3)),
        Button("Route B",     "B",  (30, 80, 80),
               lambda: _dante_preset(4)),
        Button("Route C",     "C",  (30, 80, 80),
               lambda: _dante_preset(5)),
        Button("Route D",     "D",  (30, 80, 80),
               lambda: _dante_preset(6)),
        Button("Stop",        "⏹", (120, 40, 40),
               lambda: _voice_control_stop()),
    ],
    knobs=[
        Knob(),   # Kanal-Gains — nach Bedarf belegen
        Knob(),
        Knob(),
    ]
)

# ── Alle Szenen in Reihenfolge ────────────────────────────────────────────

ALL_SCENES: list[Scene] = [
    SCENE_PRODUKTIVITAET,
    SCENE_STUDIO,
    SCENE_VOICE,
]


# ── Stub-Aktionen (Dante + Voice) ─────────────────────────────────────────

def _dante_preset(n: int):
    print(f"[Dante] Lade Preset {n} — hier DDM-API-Call eintragen")


def _dante_clear():
    print("[Dante] Alle Subscriptions trennen — hier DDM-API-Call eintragen")


def _start_recording():
    print("[Studio] Aufnahme starten — hier DAW-Aktion eintragen")


def _voice_control_toggle():
    print("[Voice] Sprachsteuerung aktivieren")


def _voice_control_stop():
    print("[Voice] Sprachsteuerung stoppen")


# ── Icon-Cache ────────────────────────────────────────────────────────────

_icon_cache: dict[str, bytes] = {}


def get_button_icon(btn: Button) -> bytes:
    key = f"{btn.app_path or btn.label}|{btn.symbol}|{btn.color}"
    if key not in _icon_cache:
        if btn.app_path:
            try:
                _icon_cache[key] = icons.load_app_icon(btn.app_path)
            except Exception as e:
                print(f"  [Icon-Warnung] {btn.label}: {e} — Fallback auf Emoji")
                _icon_cache[key] = icons.make_icon(btn.label, btn.symbol, btn.color)
        else:
            _icon_cache[key] = icons.make_icon(btn.label, btn.symbol, btn.color)
    return _icon_cache[key]
