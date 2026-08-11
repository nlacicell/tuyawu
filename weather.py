import os
import json
import tinytuya

# --- 1. PROJEKT ÉS ESZKÖZ ADATOK (GITHUB SECRETS) ---
ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")

def discover_tuya_devices():
    cloud = tinytuya.Cloud(
        apiRegion="eu",
        apiKey=ACCESS_ID,
        apiSecret=ACCESS_SECRET,
        nodeId=DEVICE_ID
    )

    print("--- 1. LÉPÉS: AZ ÖSSZES ESZKÖZ LEKÉRÉSE A FIÓKBÓL ---")
    try:
        devices = cloud.getdevices()
        print(json.dumps(devices, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Hiba az eszközök lekérésekor: {e}")
        devices = []

    print("\n--- 2. LÉPÉS: AZ ÖSSZES ESZKÖZ AKTUÁLIS STÁTUSZA ---")
    if devices and isinstance(devices, list):
        for dev in devices:
            dev_id = dev.get("id")
            name = dev.get("name", "Ismeretlen nevű eszköz")
            print(f"\n>>> Lekérdezés: {name} (ID: {dev_id}) <<<")
            
            try:
                status = cloud.getstatus(dev_id)
                print(json.dumps(status, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"Hiba a(z) {name} státuszának lekérésekor: {e}")
    else:
        print("Nem található egyetlen eszköz sem, vagy hiba történt a listázáskor.")

# --- FŐ PROGRAMFUTTATÁS ---
if __name__ == "__main__":
    discover_tuya_devices()
