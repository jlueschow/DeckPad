"""
AKP03E — Haupt-Einstiegspunkt.

Szenarien:
  Home     → Szenario 1: Produktivität
  Next →    Szenario 2: Studio
  Next →    Szenario 3: Voice Control
  Prev      navigiert zurück
"""

import threading
from akp03e import AKP03E, EventType, Event
from scenes import ALL_SCENES, get_button_icon, preload_knobs


class SceneManager:
    def __init__(self, device: AKP03E):
        self._dev   = device
        self._index = 0
        self._lock  = threading.Lock()

    @property
    def scene(self):
        return ALL_SCENES[self._index]

    def load(self, index: int):
        with self._lock:
            self._index = index % len(ALL_SCENES)
        print(f"\n── Szene: {self.scene.name} ({self._index + 1}/{len(ALL_SCENES)}) ──")
        self._upload_icons()

    def _upload_icons(self):
        for i, btn in enumerate(self.scene.buttons, start=1):
            try:
                jpeg = get_button_icon(btn)
                self._dev.set_button_image(i, jpeg)
            except Exception as e:
                print(f"  Icon {i} Fehler: {e}")
        self._dev.finalize_display()

    def next(self): self.load(self._index + 1)
    def prev(self): self.load(self._index - 1)
    def home(self): self.load(0)

    def handle_button(self, event: Event):
        btn = self.scene.buttons[event.index - 1]
        print(f"  [{self.scene.name}] Taste {event.index}: {btn.label}")
        if btn.action:
            threading.Thread(target=btn.action, daemon=True).start()

    def handle_knob_turn(self, event: Event):
        knob = self.scene.knobs[event.index - 1]
        if knob.on_turn:
            new_val = knob.on_turn(event.value)
            direction = "▲" if event.value > 0 else "▼"
            val_str = f" → {new_val}" if new_val is not None else ""
            print(f"  Regler {event.index}: {direction}{val_str}")
        # no handler = silent

    def handle_knob_press(self, event: Event):
        knob = self.scene.knobs[event.index - 1]
        print(f"  Regler {event.index}: Klick")
        if knob.on_press:
            threading.Thread(target=knob.on_press, daemon=True).start()


def main():
    device = AKP03E()
    device.connect()
    device.set_brightness(80)

    mgr = SceneManager(device)

    @device.on(EventType.BUTTON_DOWN)
    def on_button(e: Event):
        mgr.handle_button(e)

    @device.on(EventType.SCENE_DOWN)
    def on_scene(e: Event):
        if e.index == "home":
            mgr.home()
        elif e.index == "next":
            mgr.next()
        elif e.index == "prev":
            mgr.prev()

    @device.on(EventType.KNOB_TURN)
    def on_knob(e: Event):
        # Synchronous — VolumeKnob is thread-safe via Lock internally.
        # Running in the event thread is fine; osascript is fast after preload.
        mgr.handle_knob_turn(e)

    @device.on(EventType.KNOB_DOWN)
    def on_knob_press(e: Event):
        mgr.handle_knob_press(e)

    print("Lade Lautstärke-Werte...")
    preload_knobs()
    print("Lade Icons — einen Moment...")
    mgr.load(0)
    print("Bereit. Ctrl+C zum Beenden.\n")

    try:
        device.run()
    finally:
        device.disconnect()


if __name__ == "__main__":
    main()
