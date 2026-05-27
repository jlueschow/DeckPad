"""
AJAZZ AKP03E — USB HID driver
VID=0x0300, PID=0x3002, usage_page=0xFFA0
Protocol: 512-byte packets, "ACK\x00\x00OK" header
"""

import hid
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

VENDOR_ID    = 0x0300
PRODUCT_ID   = 0x3002
USAGE_PAGE   = 0xFFA0
INPUT_SIZE   = 512    # MaxInputReportSize  (device → host, button events)
OUTPUT_SIZE  = 1024   # MaxOutputReportSize (host → device, display commands)
PACKET_SIZE  = INPUT_SIZE  # kept for read() calls

# Event codes from byte[9] of incoming packets
_BUTTON_CODES = {0x01, 0x02, 0x03, 0x04, 0x05, 0x06}
_SCENE_CODES  = {0x25: "prev", 0x30: "home", 0x31: "next"}
_KNOB_CODES   = {
    0x50: (1, -1), 0x51: (1, +1),   # knob 1: CCW / CW
    0x90: (2, -1), 0x91: (2, +1),   # knob 2: CCW / CW
    0x60: (3, -1), 0x61: (3, +1),   # knob 3: CCW / CW
}
_KNOB_PRESS   = {0x35: 1, 0x33: 2, 0x34: 3}

# Command prefixes
_CRT = bytes([0x00, 0x43, 0x52, 0x54, 0x00, 0x00])

def _cmd(*payload):
    data = _CRT + bytes(payload)
    return data + bytes(OUTPUT_SIZE + 1 - len(data))


class EventType(Enum):
    BUTTON_DOWN   = "button_down"
    BUTTON_UP     = "button_up"
    SCENE_DOWN    = "scene_down"
    SCENE_UP      = "scene_up"
    KNOB_TURN     = "knob_turn"
    KNOB_DOWN     = "knob_down"
    KNOB_UP       = "knob_up"


@dataclass
class Event:
    type:  EventType
    index: int            # button 1–6, scene "prev"/"home"/"next", knob 1–3
    value: int = 0        # knob direction: +1 CW, -1 CCW; else 0


def _parse(data: bytes) -> Optional[Event]:
    if len(data) < 11:
        return None
    # Header check: ACK\x00\x00OK at bytes 0–6
    if data[0:3] != b'\x41\x43\x4b':
        return None

    code  = data[9]
    press = data[10] == 0x01

    if code in _BUTTON_CODES:
        idx = code  # 1–6
        return Event(EventType.BUTTON_DOWN if press else EventType.BUTTON_UP, idx)

    if code in _SCENE_CODES:
        label = _SCENE_CODES[code]
        return Event(EventType.SCENE_DOWN if press else EventType.SCENE_UP, label)

    if code in _KNOB_CODES:
        knob, direction = _KNOB_CODES[code]
        return Event(EventType.KNOB_TURN, knob, direction)

    if code in _KNOB_PRESS:
        knob = _KNOB_PRESS[code]
        return Event(EventType.KNOB_DOWN if press else EventType.KNOB_UP, knob)

    return None


class AKP03E:
    def __init__(self):
        self._dev = None
        self._handlers: dict[EventType, list[Callable]] = {}

    def connect(self):
        path = None
        seen = set()
        for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
            if d["usage_page"] == USAGE_PAGE and d["path"] not in seen:
                path = d["path"]
                seen.add(path)
                break
        if not path:
            raise RuntimeError("AKP03E nicht gefunden")
        self._dev = hid.device()
        self._dev.open_path(path)
        self._dev.set_nonblocking(1)
        # Init sequence — CONNECT first (keep-alive), then display init
        self._dev.write(list(_cmd(0x43, 0x4f, 0x4e, 0x4e, 0x45, 0x43, 0x54)))                     # CONNECT
        time.sleep(0.1)
        self._dev.write(list(_cmd(0x44, 0x49, 0x53)))                                              # DIS
        time.sleep(0.05)
        self._dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))                             # LIG 30%
        time.sleep(0.05)
        self._dev.write(list(_cmd(0x51, 0x55, 0x43, 0x4d, 0x44, 0x11, 0x11, 0x00, 0x11, 0x00, 0x11)))  # QUCMD
        time.sleep(0.05)
        self._dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))                             # LIG 30%
        time.sleep(0.05)
        self._dev.write(list(_cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 0x00, 0xff)))                     # CLE all
        time.sleep(0.15)

    def disconnect(self):
        if self._dev:
            self._dev.close()
            self._dev = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()

    # --- Event API ---

    def on(self, event_type: EventType):
        """Decorator: @device.on(EventType.BUTTON_DOWN)"""
        def decorator(fn):
            self._handlers.setdefault(event_type, []).append(fn)
            return fn
        return decorator

    def _dispatch(self, event: Event):
        for fn in self._handlers.get(event.type, []):
            fn(event)

    def run(self):
        """Blocking event loop."""
        print("AKP03E running — Ctrl+C to stop")
        try:
            while True:
                data = self._dev.read(PACKET_SIZE)
                if data:
                    event = _parse(bytes(data))
                    if event:
                        self._dispatch(event)
                time.sleep(0.005)
        except KeyboardInterrupt:
            pass

    # --- Commands ---

    def set_brightness(self, percent: int):
        """Set display brightness (0–100)."""
        percent = max(0, min(100, percent))
        self._dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, percent)))

    def clear_button(self, index: int):
        """Clear a single LCD button image (1–6)."""
        self._dev.write(list(_cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 0x00, index)))

    def clear_all(self):
        """Clear all LCD button images at once."""
        self._dev.write(list(_cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 0x00, 0xff)))

    def set_button_image(self, index: int, jpeg_bytes: bytes):
        """Upload a JPEG image to an LCD button (call finalize_display() after all buttons)."""
        size = len(jpeg_bytes)
        self._dev.write(list(_cmd(
            0x42, 0x41, 0x54, 0x00, 0x00,
            (size >> 8) & 0xFF, size & 0xFF,
            index
        )))
        offset = 0
        while offset < size:
            chunk = jpeg_bytes[offset:offset + OUTPUT_SIZE]
            pkt = bytes([0x00]) + chunk + bytes(OUTPUT_SIZE - len(chunk))
            self._dev.write(list(pkt))
            offset += OUTPUT_SIZE

    def finalize_display(self):
        """Send STP once after uploading all button images."""
        self._dev.write(list(_cmd(0x53, 0x54, 0x50)))                                    # STP


# --- Quick demo ---

if __name__ == "__main__":
    device = AKP03E()
    device.connect()

    @device.on(EventType.BUTTON_DOWN)
    def btn(e):
        print(f"LCD-Taste {e.index} gedrückt")

    @device.on(EventType.BUTTON_UP)
    def btn_up(e):
        print(f"LCD-Taste {e.index} losgelassen")

    @device.on(EventType.KNOB_TURN)
    def knob(e):
        direction = "CW" if e.value > 0 else "CCW"
        print(f"Regler {e.index}: {direction}")

    @device.on(EventType.KNOB_DOWN)
    def knob_press(e):
        print(f"Regler {e.index} gedrückt")

    @device.on(EventType.SCENE_DOWN)
    def scene(e):
        print(f"Scene-Taste: {e.index}")

    device.run()
    device.disconnect()
