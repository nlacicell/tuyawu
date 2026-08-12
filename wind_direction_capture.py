import os
import sys
import json
import time
from datetime import datetime, timezone
import base64
import binascii

import tinytuya


# ============================================================
# TUYA BEÁLLÍTÁSOK
# ============================================================

TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
TUYA_REGION = os.environ.get("TUYA_REGION", "eu")

# ============================================================
# TESZT BEÁLLÍTÁSOK
# ============================================================

INTERVAL_SECONDS = 10
SAMPLES = 120              # 20 perc
OUTPUT_FILE = "wind_capture.log"


def check_environment():
    required = {
        "TUYA_ACCESS_ID": TUYA_ACCESS_ID,
        "TUYA_ACCESS_SECRET": TUYA_ACCESS_SECRET,
        "TUYA_DEVICE_ID": TUYA_DEVICE_ID,
    }

    missing = [name for name, value in required.items() if not value]

    if missing:
        raise RuntimeError(
            "Hiányzó GitHub Secret: " + ", ".join(missing)
        )


def create_cloud():
    print(f"Tuya Cloud régió: {TUYA_REGION}")
    return tinytuya.Cloud(
        apiRegion=TUYA_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
    )


def get_shadow(cloud):
    endpoint = (
        f"/v2.0/cloud/thing/"
        f"{TUYA_DEVICE_ID}/shadow/properties"
    )

    response = cloud.cloudrequest(endpoint)

    if not isinstance(response, dict):
        raise RuntimeError(f"Hibás Tuya válasz: {response!r}")

    if response.get("success") is False:
        raise RuntimeError(
            f"Shadow API hiba: "
            f"{response.get('code')} {response.get('msg')}"
        )

    result = response.get("result", {})
    properties = []

    if isinstance(result, dict):
        properties = result.get("properties", [])

    shadow = {}

    if isinstance(properties, list):
        for item in properties:
            if not isinstance(item, dict):
                continue

            code = item.get("code")
            if code:
                shadow[str(code)] = item

    return shadow


def get_value(item):
    if isinstance(item, dict):
        return item.get("value")
    return item


def decode_base64(value):
    if not isinstance(value, str) or not value:
        return None

    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        return None


def find_0e_fields(raw):
    """
    Megkeresi az összes 0e 01 XX előfordulást.
    Nem feltételezzük, hogy ez a szélirány.
    """
    found = []

    if not raw:
        return found

    for i in range(len(raw) - 2):
        if raw[i] == 0x0E and raw[i + 1] == 0x01:
            found.append({
                "offset": i,
                "value": raw[i + 2],
            })

    return found


def write_sample(log, sample_no, shadow):
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat(timespec="seconds")

    print()
    print("=" * 80)
    print(f"MINTA {sample_no}/{SAMPLES}   {timestamp}")
    print("=" * 80)

    log.write("\n" + "=" * 100 + "\n")
    log.write(f"SAMPLE={sample_no}/{SAMPLES}\n")
    log.write(f"UTC={timestamp}\n")

    # Minden Tuya property neve, értéke és DP azonosítója.
    for code, item in shadow.items():
        value = get_value(item)

        dp_id = item.get("dp_id")
        ptype = item.get("type")
        timestamp_value = item.get("time")

        line = (
            f"PROPERTY code={code!r} "
            f"dp_id={dp_id!r} "
            f"type={ptype!r} "
            f"time={timestamp_value!r} "
            f"value={value!r}"
        )

        print(line)
        log.write(line + "\n")

        # RAW/Base64 érték külön hex dumpként is.
        raw = decode_base64(value)

        if raw is not None and len(raw) > 0:
            hex_value = raw.hex(" ")

            log.write(
                f"RAW code={code!r} "
                f"length={len(raw)} "
                f"hex={hex_value}\n"
            )

            fields = find_0e_fields(raw)

            for field in fields:
                print(
                    f"  0e 01 XX: offset={field['offset']} "
                    f"XX={field['value']}"
                )

                log.write(
                    f"FIELD_0E_01 offset={field['offset']} "
                    f"value={field['value']}\n"
                )

    # Külön kiemeljük a jelenlegi DP113 jelöltet.
    dp113 = shadow.get("outdoor_alert_display")

    if dp113:
        value = get_value(dp113)
        raw = decode_base64(value)

        print()
        print("DP113 / outdoor_alert_display RAW:")
        print(f"Base64: {value}")
        print(f"HEX:    {raw.hex(' ') if raw else 'NINCS'}")

        log.write(f"DP113_BASE64={value!r}\n")

        if raw:
            log.write(f"DP113_HEX={raw.hex(' ')}\n")

            fields = find_0e_fields(raw)

            for field in fields:
                log.write(
                    f"DP113_0E_01 offset={field['offset']} "
                    f"value={field['value']}\n"
                )

    log.flush()


def main():
    check_environment()

    print("=" * 80)
    print("YT60307 SZÉLIRÁNY RAW CAPTURE")
    print("=" * 80)
    print(f"Intervallum: {INTERVAL_SECONDS} másodperc")
    print(f"Mérések:     {SAMPLES}")
    print(f"Időtartam:   kb. {SAMPLES * INTERVAL_SECONDS / 60:.1f} perc")
    print(f"Log fájl:    {OUTPUT_FILE}")
    print()
    print("Ez a program NEM tölt fel semmit a Weather Undergroundra.")
    print("Csak a Tuya Cloud adatokat rögzíti.")
    print("=" * 80)

    cloud = create_cloud()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as log:
        log.write("YT60307 WIND DIRECTION RAW CAPTURE\n")
        log.write(f"INTERVAL_SECONDS={INTERVAL_SECONDS}\n")
        log.write(f"SAMPLES={SAMPLES}\n")
        log.write(f"DEVICE_ID={TUYA_DEVICE_ID}\n")
        log.write("=" * 100 + "\n")

        start = time.monotonic()

        for sample_no in range(1, SAMPLES + 1):
            try:
                shadow = get_shadow(cloud)
                write_sample(log, sample_no, shadow)

            except Exception as exc:
                timestamp = datetime.now(timezone.utc).isoformat(
                    timespec="seconds"
                )

                print(
                    f"HIBA {sample_no}/{SAMPLES}: {exc}",
                    file=sys.stderr
                )

                log.write(
                    f"ERROR UTC={timestamp} "
                    f"sample={sample_no} "
                    f"error={exc!r}\n"
                )
                log.flush()

            if sample_no < SAMPLES:
                target = start + sample_no * INTERVAL_SECONDS
                delay = target - time.monotonic()

                if delay > 0:
                    time.sleep(delay)

    print()
    print("=" * 80)
    print("CAPTURE BEFEJEZVE")
    print("=" * 80)
    print(f"Az eredmény: {OUTPUT_FILE}")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"HIBA: {exc}", file=sys.stderr)
        sys.exit(1)
