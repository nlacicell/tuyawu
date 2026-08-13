import os
import sys
import json
import time
import base64
from datetime import datetime, timezone
import tinytuya

TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
TUYA_REGION = os.environ.get("TUYA_REGION", "eu")

INTERVAL_SECONDS = 10
SAMPLES = 120
OUTPUT_FILE = "wind_capture.log"

def create_cloud():
    return tinytuya.Cloud(
        apiRegion=TUYA_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
    )

def get_shadow_properties(cloud):
    endpoint = f"/v2.0/cloud/thing/{TUYA_DEVICE_ID}/shadow/properties"
    response = cloud.cloudrequest(endpoint)

    if not isinstance(response, dict):
        raise RuntimeError(f"Nem dictionary válasz: {response!r}")
    if response.get("success") is False:
        raise RuntimeError(
            f"Tuya Shadow hiba: {response.get('code')} {response.get('msg')}"
        )

    result = response.get("result", {})
    properties = result.get("properties", []) if isinstance(result, dict) else []
    shadow = {}

    if isinstance(properties, list):
        for item in properties:
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            if code:
                shadow[str(code)] = {
                    "value": item.get("value"),
                    "dp_id": item.get("dp_id", item.get("dpId")),
                    "time": item.get("time"),
                    "custom_name": item.get("custom_name", ""),
                }
    return shadow, response

def decode_b64(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        return None

def find_all_0e01(raw):
    if raw is None:
        return []
    return [
        (i, raw[i + 2])
        for i in range(len(raw) - 2)
        if raw[i] == 0x0E and raw[i + 1] == 0x01
    ]

def log_sample(log, sample_no, shadow, response):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log.write("\n" + "=" * 110 + "\n")
    log.write(f"SAMPLE={sample_no}/{SAMPLES}\n")
    log.write(f"UTC={timestamp}\n")
    log.write(f"PROPERTY_COUNT={len(shadow)}\n")
    log.write("FULL_TUYA_RESPONSE_JSON=\n")
    log.write(json.dumps(response, ensure_ascii=False, indent=2))
    log.write("\n")

    print(f"[{sample_no:03d}/{SAMPLES}] {timestamp} properties={len(shadow)}")

    for code, item in shadow.items():
        value = item.get("value")
        log.write(
            f"PROPERTY code={code!r} dp_id={item.get('dp_id')!r} "
            f"time={item.get('time')!r} custom_name={item.get('custom_name')!r} "
            f"value={value!r}\n"
        )

        raw = decode_b64(value)
        if raw is not None:
            log.write(
                f"RAW code={code!r} length={len(raw)} hex={raw.hex(' ')}\n"
            )
            for offset, byte_value in find_all_0e01(raw):
                log.write(
                    f"FIELD_0E_01 code={code!r} offset={offset} value={byte_value}\n"
                )

    dp113 = shadow.get("outdoor_alert_display")
    if dp113:
        raw_b64 = dp113.get("value")
        raw = decode_b64(raw_b64)
        log.write(f"DP113_BASE64={raw_b64!r}\n")
        if raw is not None:
            log.write(f"DP113_HEX={raw.hex(' ')}\n")
            for offset, byte_value in find_all_0e01(raw):
                log.write(
                    f"DP113_0E_01 offset={offset} value={byte_value}\n"
                )
    log.flush()

def main():
    required = {
        "TUYA_ACCESS_ID": TUYA_ACCESS_ID,
        "TUYA_ACCESS_SECRET": TUYA_ACCESS_SECRET,
        "TUYA_DEVICE_ID": TUYA_DEVICE_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError("Hiányzó GitHub Secret: " + ", ".join(missing))

    print("YT60307 WIND DIRECTION RAW CAPTURE")
    print("A működő weather.py ugyanazon Shadow Properties API-ját használja.")
    print(f"{SAMPLES} mérés, {INTERVAL_SECONDS} másodpercenként.")

    cloud = create_cloud()
    start = time.monotonic()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as log:
        log.write("YT60307 WIND DIRECTION RAW CAPTURE\n")
        log.write(f"INTERVAL_SECONDS={INTERVAL_SECONDS}\n")
        log.write(f"SAMPLES={SAMPLES}\n")
        log.write(f"DEVICE_ID={TUYA_DEVICE_ID}\n")

        for sample_no in range(1, SAMPLES + 1):
            try:
                shadow, response = get_shadow_properties(cloud)
                log_sample(log, sample_no, shadow, response)
            except Exception as exc:
                ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
                print(f"HIBA [{sample_no:03d}]: {exc}", file=sys.stderr)
                log.write(f"ERROR UTC={ts} sample={sample_no} error={exc!r}\n")
                log.flush()

            if sample_no < SAMPLES:
                target = start + sample_no * INTERVAL_SECONDS
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)

    print(f"CAPTURE BEFEJEZVE: {OUTPUT_FILE}")

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
