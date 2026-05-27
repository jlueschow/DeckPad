"""
Test basic CRT commands to see if protocol works at all.
Tests brightness, clear, and image upload.
"""
import hid, time

VENDOR_ID   = 0x0300
PRODUCT_ID  = 0x3002
USAGE_PAGE  = 0xFFA0
OUTPUT_SIZE = 1024

_CRT = bytes([0x00, 0x43, 0x52, 0x54, 0x00, 0x00])

def cmd(*payload):
    data = _CRT + bytes(payload)
    return data + bytes(OUTPUT_SIZE + 1 - len(data))

def open_device():
    for d in hid.enumerate(VENDOR_ID, PRODUCT_ID):
        if d["usage_page"] == USAGE_PAGE:
            path = d["path"]
            dev = hid.device()
            dev.open_path(path)
            dev.set_nonblocking(1)
            print(f"Opened: {path}")
            return dev
    raise RuntimeError("Device not found")

def main():
    dev = open_device()

    print("Step 1: Init (DIS)")
    dev.write(list(cmd(0x44, 0x49, 0x53)))
    time.sleep(0.3)

    print("Step 2: Set brightness to 10% — does screen dim?")
    dev.write(list(cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 10)))
    time.sleep(2)
    print("  (should be dim)")

    print("Step 3: Set brightness to 100%")
    dev.write(list(cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 100)))
    time.sleep(2)
    print("  (should be bright)")

    print("Step 4: Set brightness to 50%")
    dev.write(list(cmd(0x4c, 0x49, 0x47, 0x00, 0x00, 50)))
    time.sleep(1)

    print("Step 5: Clear button 1 (CLE)")
    dev.write(list(cmd(0x43, 0x4c, 0x45, 0x00, 0x00, 1)))
    time.sleep(0.5)
    print("  (button 1 should turn black)")

    print("Done.")
    dev.close()

if __name__ == "__main__":
    main()
