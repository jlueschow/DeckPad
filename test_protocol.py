"""
Test the corrected protocol: full init + image upload + finalize.
Upload one red 76×76 JPEG to button 1 using the exact sequence from the official app.
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
    d.text((38, 38), label, fill=(255, 255, 255), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

def main():
    dev = open_device()

    print("\n1. DIS")
    dev.write(list(_cmd(0x44, 0x49, 0x53)))
    time.sleep(0.05)

    print("2. LIG 30%")
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))
    time.sleep(0.05)

    print("3. QUCMD")
    dev.write(list(_cmd(0x51, 0x55, 0x43, 0x4d, 0x44, 0x11, 0x11, 0x00, 0x11, 0x00, 0x11)))
    time.sleep(0.05)

    print("4. LIG 30%")
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 30)))
    time.sleep(0.05)

    print("5. CLE all")
    dev.write(list(_cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 0x00, 0xff)))
    time.sleep(0.15)

    print("6. LIG 80%")
    dev.write(list(_cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 80)))
    time.sleep(0.05)

    # Upload red image to button 1
    jpeg = make_jpeg((220, 30, 30), "1")
    size = len(jpeg)
    print(f"\n7. BAT button 1 ({size} bytes)")
    dev.write(list(_cmd(0x42, 0x41, 0x54, 0x00, 0x00, (size >> 8) & 0xFF, size & 0xFF, 1)))

    offset, chunks = 0, 0
    while offset < size:
        chunk = jpeg[offset:offset + OUTPUT_SIZE]
        pkt = bytes([0x00]) + chunk + bytes(OUTPUT_SIZE - len(chunk))
        dev.write(list(pkt))
        offset += OUTPUT_SIZE
        chunks += 1
    print(f"   Sent {chunks} chunk(s)")

    print("\n8. STP")
    dev.write(list(_cmd(0x53, 0x54, 0x50)))
    time.sleep(0.05)

    print("9. CONNECT")
    dev.write(list(_cmd(0x43, 0x4f, 0x4e, 0x4e, 0x45, 0x43, 0x54)))
    time.sleep(0.5)

    print("\nDone — button 1 should show a red image.")
    dev.close()

if __name__ == "__main__":
    main()
