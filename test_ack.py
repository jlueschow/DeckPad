"""
Test: read ACK responses from device after each command.
"""

import hid, time, io
from PIL import Image, ImageDraw, ImageFont

VENDOR_ID   = 0x0300
PRODUCT_ID  = 0x3002
USAGE_PAGE  = 0xFFA0
OUTPUT_SIZE = 1024
INPUT_SIZE  = 512

_CRT = bytes([0x00, 0x43, 0x52, 0x54, 0x00, 0x00])

def cmd(*payload):
    data = _CRT + bytes(payload)
    return data + bytes(OUTPUT_SIZE + 1 - len(data))

def open_device():
    for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if d["usage_page"] == USAGE_PAGE and d["usage"] == 0x01:
            path = d["path"]
            dev = hid.device()
            dev.open_path(path)
            dev.set_nonblocking(1)
            print(f"Opened (usage=0x01): {path}")
            return dev
    raise RuntimeError("Device not found")

def read_response(dev, timeout_ms=200, label=""):
    """Read any pending responses from device."""
    deadline = time.time() + timeout_ms / 1000
    responses = []
    while time.time() < deadline:
        data = dev.read(INPUT_SIZE)
        if data:
            b = bytes(data)
            responses.append(b)
            print(f"  [{label}] ACK: {b[:16].hex()} ...")
        else:
            time.sleep(0.005)
    if not responses:
        print(f"  [{label}] (no response)")
    return responses

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

def main():
    dev = open_device()

    print("\n=== Init (DIS) ===")
    dev.write(list(cmd(0x44, 0x49, 0x53)))
    read_response(dev, 300, "DIS")

    print("\n=== Set brightness 80% ===")
    dev.write(list(cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 80)))
    read_response(dev, 200, "LIG")

    # Generate 76×76 JPEG
    jpeg_bytes = make_jpeg(76, (200, 30, 30), "RED")
    size = len(jpeg_bytes)
    print(f"\n=== Upload image to button 1 ({size} bytes JPEG 76×76) ===")

    # BAT header
    print("  Sending BAT header...")
    dev.write(list(cmd(0x42, 0x41, 0x54, 0x00, 0x00,
                       (size >> 8) & 0xFF, size & 0xFF, 1)))
    read_response(dev, 300, "BAT")

    # Data chunks
    offset = 0
    chunk_num = 0
    while offset < size:
        chunk = jpeg_bytes[offset:offset + OUTPUT_SIZE]
        pkt = bytes([0x00]) + chunk + bytes(OUTPUT_SIZE - len(chunk))
        dev.write(list(pkt))
        chunk_num += 1
        offset += OUTPUT_SIZE
        time.sleep(0.01)

    print(f"  Sent {chunk_num} chunk(s)")
    read_response(dev, 200, "chunks")

    # STP flush
    print("  Sending STP...")
    dev.write(list(cmd(0x53, 0x54, 0x50)))
    read_response(dev, 500, "STP")

    print("\n=== Waiting 3s — check button 1 ===")
    time.sleep(3)

    # Now try WITHOUT STP
    print("\n=== Upload WITHOUT STP to button 2 ===")
    jpeg_bytes2 = make_jpeg(76, (30, 30, 200), "BLUE")
    size2 = len(jpeg_bytes2)
    dev.write(list(cmd(0x42, 0x41, 0x54, 0x00, 0x00,
                       (size2 >> 8) & 0xFF, size2 & 0xFF, 2)))
    read_response(dev, 300, "BAT2")
    offset = 0
    while offset < size2:
        chunk = jpeg_bytes2[offset:offset + OUTPUT_SIZE]
        pkt = bytes([0x00]) + chunk + bytes(OUTPUT_SIZE - len(chunk))
        dev.write(list(pkt))
        offset += OUTPUT_SIZE
        time.sleep(0.01)
    print("  Sent chunks (no STP)")
    read_response(dev, 500, "chunks2")

    time.sleep(2)
    print("\nDone.")
    dev.close()

if __name__ == "__main__":
    main()
