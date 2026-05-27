"""
Upload 6 farbige Bilder (rot/grün/blau/gelb/cyan/magenta) auf alle 6 Buttons.
Exakte Init-Sequenz wie offizielle App.
"""

import hid, time, io
from PIL import Image, ImageDraw

VENDOR_ID   = 0x0300
PRODUCT_ID  = 0x3002
USAGE_PAGE  = 0xFFA0
OUTPUT_SIZE = 1024

_CRT = bytes([0x00, 0x43, 0x52, 0x54, 0x00, 0x00])

def _cmd(*payload):
    data = _CRT + bytes(payload)
    return data + bytes(OUTPUT_SIZE + 1 - len(data))

def open_device():
    for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if d["usage_page"] == USAGE_PAGE:
            dev = hid.device()
            dev.open_path(d["path"])
            dev.set_nonblocking(1)
            print(f"Opened: {d['path']}")
            return dev
    raise RuntimeError("Device not found")

def make_jpeg(color, label):
    img = Image.new("RGB", (76, 76), color)
    d = ImageDraw.Draw(img)
    d.text((38, 38), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

BUTTONS = [
    ((220, 30,  30),  "1 ROT"),
    ((30,  180, 30),  "2 GRN"),
    ((30,  30,  220), "3 BLU"),
    ((220, 200, 30),  "4 GEL"),
    ((30,  200, 200), "5 CYA"),
    ((200, 30,  200), "6 MAG"),
]

def main():
    dev = open_device()

    print("\n── Init ──")
    dev.write(list(_cmd(0x44, 0x49, 0x53)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x51, 0x55, 0x43, 0x4d, 0x44, 0x11, 0x11, 0x00, 0x11, 0x00, 0x11)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))
    time.sleep(0.05)
    dev.write(list(_cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 0x00, 0xff)))
    time.sleep(0.15)
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 80)))
    time.sleep(0.05)

    print("\n── Bilder ──")
    for i, (color, label) in enumerate(BUTTONS, start=1):
        jpeg = make_jpeg(color, label)
        size = len(jpeg)
        print(f"  Button {i}: {size} bytes")
        dev.write(list(_cmd(0x42, 0x41, 0x54, 0x00, 0x00,
                            (size >> 8) & 0xFF, size & 0xFF, i)))
        offset = 0
        while offset < size:
            chunk = jpeg[offset:offset + OUTPUT_SIZE]
            pkt = bytes([0x00]) + chunk + bytes(OUTPUT_SIZE - len(chunk))
            dev.write(list(pkt))
            offset += OUTPUT_SIZE
        time.sleep(0.01)

    print("\n── Finalize ──")
    dev.write(list(_cmd(0x53, 0x54, 0x50)))       # STP
    time.sleep(0.05)
    dev.write(list(_cmd(0x43, 0x4f, 0x4e, 0x4e, 0x45, 0x43, 0x54)))  # CONNECT
    time.sleep(1)

    print("Fertig — alle 6 Buttons sollten Farben zeigen.")
    dev.close()

if __name__ == "__main__":
    main()
