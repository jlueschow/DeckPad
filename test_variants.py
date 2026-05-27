"""
Testet zwei Varianten der Upload-Sequenz:
  A) CONNECT am Anfang (wie mirajazz), KEIN CONNECT am Ende
  B) Kein CONNECT überhaupt — nur STP

Führe A aus, schau ob Bilder erscheinen.
Falls nicht: B ausprobieren.
"""

import hid, time, io, sys
from PIL import Image, ImageDraw

VENDOR_ID   = 0x0300
PRODUCT_ID  = 0x3002
USAGE_PAGE  = 0xFFA0
OUTPUT_SIZE = 1024
_CRT = bytes([0x00, 0x43, 0x52, 0x54, 0x00, 0x00])

def _cmd(*p):
    d = _CRT + bytes(p)
    return d + bytes(OUTPUT_SIZE + 1 - len(d))

def open_device():
    for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if d["usage_page"] == USAGE_PAGE:
            dev = hid.device()
            dev.open_path(d["path"])
            dev.set_nonblocking(1)
            return dev
    raise RuntimeError("Gerät nicht gefunden")

def make_jpeg(color, text):
    img = Image.new("RGB", (76, 76), color)
    ImageDraw.Draw(img).text((4, 30), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

COLORS = [
    ((200, 20,  20),  "ROT"),
    ((20,  180, 20),  "GRUEN"),
    ((20,  20,  200), "BLAU"),
    ((200, 180, 20),  "GELB"),
    ((20,  180, 180), "CYAN"),
    ((180, 20,  180), "LILA"),
]

def upload_all(dev, jpegs):
    for i, jpeg in enumerate(jpegs, start=1):
        size = len(jpeg)
        dev.write(list(_cmd(0x42, 0x41, 0x54, 0x00, 0x00,
                            (size >> 8) & 0xFF, size & 0xFF, i)))
        off = 0
        while off < size:
            chunk = jpeg[off:off + OUTPUT_SIZE]
            pkt = bytes([0x00]) + chunk + bytes(OUTPUT_SIZE - len(chunk))
            dev.write(list(pkt))
            off += OUTPUT_SIZE
        time.sleep(0.01)
    dev.write(list(_cmd(0x53, 0x54, 0x50)))   # STP


def variant_A(dev, jpegs):
    """CONNECT zuerst (wie mirajazz), dann Init+Upload, KEIN CONNECT am Ende."""
    print("\n=== Variante A: CONNECT am Anfang, kein CONNECT am Ende ===")
    dev.write(list(_cmd(0x43, 0x4f, 0x4e, 0x4e, 0x45, 0x43, 0x54)))  # CONNECT
    time.sleep(0.1)
    dev.write(list(_cmd(0x44, 0x49, 0x53)))                            # DIS
    time.sleep(0.05)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))            # LIG 30%
    time.sleep(0.05)
    dev.write(list(_cmd(0x51, 0x55, 0x43, 0x4d, 0x44,
                        0x11, 0x11, 0x00, 0x11, 0x00, 0x11)))          # QUCMD
    time.sleep(0.05)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))            # LIG 30%
    time.sleep(0.05)
    dev.write(list(_cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 0x00, 0xff)))    # CLE all
    time.sleep(0.15)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 80)))            # LIG 80%
    time.sleep(0.05)

    print("  Lade 6 Bilder...")
    upload_all(dev, jpegs)
    print("  STP gesendet — keine CONNECT am Ende")
    print("  → Erscheinen jetzt ROT/GRUEN/BLAU/GELB/CYAN/LILA?")
    time.sleep(3)


def variant_B(dev, jpegs):
    """Kein CONNECT überhaupt — nur Standard-Init + STP."""
    print("\n=== Variante B: Kein CONNECT, nur STP ===")
    dev.write(list(_cmd(0x44, 0x49, 0x53)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x51, 0x55, 0x43, 0x4d, 0x44,
                        0x11, 0x11, 0x00, 0x11, 0x00, 0x11)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 0x00, 0xff)))
    time.sleep(0.15)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 80)))
    time.sleep(0.05)

    print("  Lade 6 Bilder...")
    upload_all(dev, jpegs)
    print("  STP gesendet, kein CONNECT")
    print("  → Erscheinen jetzt ROT/GRUEN/BLAU/GELB/CYAN/LILA?")
    time.sleep(3)


if __name__ == "__main__":
    variant = sys.argv[1] if len(sys.argv) > 1 else "A"
    dev = open_device()
    print(f"Gerät geöffnet")
    jpegs = [make_jpeg(c, t) for c, t in COLORS]
    if variant == "B":
        variant_B(dev, jpegs)
    else:
        variant_A(dev, jpegs)
    dev.close()
    print("Fertig.")
