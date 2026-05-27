"""
Protocol test: try different image sizes and upload variations.
"""

import hid, time, io
from PIL import Image, ImageDraw, ImageFont

VENDOR_ID  = 0x0300
PRODUCT_ID = 0x3002
USAGE_PAGE = 0xFFA0
OUTPUT_SIZE = 1024

_CRT = bytes([0x00, 0x43, 0x52, 0x54, 0x00, 0x00])

def cmd(*payload):
    data = _CRT + bytes(payload)
    return data + bytes(OUTPUT_SIZE + 1 - len(data))

def open_device():
    path = None
    for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if d["usage_page"] == USAGE_PAGE:
            path = d["path"]
            break
    if not path:
        raise RuntimeError("Device not found")
    dev = hid.device()
    dev.open_path(path)
    dev.set_nonblocking(1)
    print(f"Opened: {path}")
    return dev

def make_jpeg(size, color, label):
    img = Image.new("RGB", (size, size), color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 12)
    except Exception:
        font = ImageFont.load_default()
    draw.text((size//2, size//2), label, font=font, fill=(255,255,255), anchor="mm")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()

def ioreg_count():
    import subprocess
    r = subprocess.run(["ioreg", "-l", "-G", "0x18", "-p", "IOUSB"],
                       capture_output=True, text=True)
    for line in r.stdout.split("\n"):
        if "SetReportCount" in line:
            return line.strip()
    return "not found"

def upload_image(dev, button_index, jpeg_bytes, label=""):
    size = len(jpeg_bytes)
    print(f"  Button {button_index}: {size} bytes JPEG  {label}")

    # Send BAT header
    dev.write(list(cmd(0x42, 0x41, 0x54, 0x00, 0x00,
                       (size >> 8) & 0xFF, size & 0xFF,
                       button_index)))
    time.sleep(0.02)

    # Send data chunks
    offset = 0
    while offset < size:
        chunk = jpeg_bytes[offset:offset + OUTPUT_SIZE]
        pkt = bytes([0x00]) + chunk + bytes(OUTPUT_SIZE - len(chunk))
        dev.write(list(pkt))
        offset += OUTPUT_SIZE
        time.sleep(0.005)

    # Send STP flush
    dev.write(list(cmd(0x53, 0x54, 0x50)))
    time.sleep(0.05)

def main():
    dev = open_device()

    # Init
    dev.write(list(cmd(0x44, 0x49, 0x53)))
    time.sleep(0.3)

    print("\n=== TEST: 76×76 RED on button 1 (index 1) ===")
    before = ioreg_count()
    jpeg_76 = make_jpeg(76, (200, 30, 30), "76px")
    upload_image(dev, 1, jpeg_76, "76×76 red")
    after = ioreg_count()
    print(f"  Before: {before}")
    print(f"  After:  {after}")
    print("  → Does button 1 show red? (wait 2s)")
    time.sleep(2)

    print("\n=== TEST: 85×85 BLUE on button 2 (index 2) ===")
    jpeg_85 = make_jpeg(85, (30, 30, 200), "85px")
    upload_image(dev, 2, jpeg_85, "85×85 blue")
    time.sleep(2)

    print("\n=== TEST: 76×76 GREEN on button 3 (index 0, 0-based) ===")
    jpeg_76g = make_jpeg(76, (30, 200, 30), "idx0")
    upload_image(dev, 0, jpeg_76g, "76×76 green, index 0")
    time.sleep(2)

    print("\n=== TEST: Clear all buttons ===")
    for i in range(1, 7):
        dev.write(list(cmd(0x43, 0x4c, 0x45, 0x00, 0x00, i)))
        time.sleep(0.05)
    print("  Sent CLE 1-6")
    time.sleep(1)

    dev.close()
    print("\nDone. Check which tests had visual effect.")

if __name__ == "__main__":
    main()
