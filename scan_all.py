"""
AKP03E Scanner — 512-Byte-Pakete, Init-Befehl, ein Interface.
"""

import hid
import time

VENDOR_ID  = 0x0300
PRODUCT_ID = 0x3002

# Initialisierung: "CRT DIS" — weckt das Vendor-Interface auf
INIT_CMD = bytes([
    0x00,
    0x43, 0x52, 0x54, 0x00, 0x00,
    0x44, 0x49, 0x53,
] + [0x00] * (513 - 9))

PACKET_SIZE = 512


def find_vendor_path():
    """Gibt den Path des Vendor-Interface zurück (usage_page=0xFFA0)."""
    seen = set()
    for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if d["usage_page"] == 0xFFA0 and d["path"] not in seen:
            seen.add(d["path"])
            return d["path"]
    return None


def scan(duration_s=25):
    path = find_vendor_path()
    if not path:
        print("AKP03E nicht gefunden!")
        return

    print(f"Öffne Interface: {path}")
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(1)

    print("Sende Init-Befehl (CRT DIS)...")
    dev.write(list(INIT_CMD))
    time.sleep(0.3)

    print(f"\nLese {duration_s}s — alle Tasten drücken und Regler drehen:\n")
    start = time.time()
    event_count = 0

    while time.time() - start < duration_s:
        data = dev.read(PACKET_SIZE)
        if data:
            nonzero = [i for i, b in enumerate(data) if b != 0]
            hex_preview = " ".join(f"{data[i]:02X}@{i}" for i in nonzero[:12])
            print(f"  [{time.strftime('%H:%M:%S')}] {len(data)} bytes — nonzero: {hex_preview or '(alle null)'}")
            event_count += 1
        time.sleep(0.005)

    dev.close()
    print(f"\n{event_count} Events empfangen.")


if __name__ == "__main__":
    scan()
