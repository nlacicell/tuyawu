import sys
import time
import base64
from datetime import datetime, timezone

import weather

INTERVAL_SECONDS = 10
SAMPLES = 120
OUTPUT_FILE = "wind_capture.log"


def decode_b64(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return base64.b64decode(value, validate=False)
    except Exception:
        return None


def find_0e01(raw):
    if raw is None:
        return []
    return [
        (i, raw[i + 2])
        for i in range(len(raw) - 2)
        if raw[i] == 0x0E and raw[i + 1] == 0x01
    ]


def get_wind_raw(shadow):
    item = shadow.get("outdoor_alert_display")
    if not isinstance(item, dict):
        return None, None
    value = item.get("value")
    return value, decode_b64(value)


def main():
    print("=" * 80)
    print("YT60307 WIND DIRECTION RAW CAPTURE - 120 MINTA")
    print("=" * 80)
    print(f"Tuya régió: {weather.TUYA_REGION}")
    print(f"Device ID: {weather.TUYA_DEVICE_ID}")
    print(f"Intervallum: {INTERVAL_SECONDS} mp")
    print(f"Mérések: {SAMPLES}")
    print(f"Időtartam: kb. {SAMPLES * INTERVAL_SECONDS / 60:.1f} perc")
    print("=" * 80)

    cloud = weather.create_cloud()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as log:
        log.write("YT60307 WIND DIRECTION RAW CAPTURE\n")
        log.write("SOURCE=weather.py\n")
        log.write(f"TUYA_REGION={weather.TUYA_REGION}\n")
        log.write(f"DEVICE_ID={weather.TUYA_DEVICE_ID}\n")
        log.write(f"INTERVAL_SECONDS={INTERVAL_SECONDS}\n")
        log.write(f"SAMPLES={SAMPLES}\n")
        log.write("=" * 120 + "\n")

        start = time.monotonic()

        for sample in range(1, SAMPLES + 1):
            timestamp = datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            )

            print(f"[{sample:03d}/{SAMPLES}] {timestamp}")
            log.write(f"\nSAMPLE={sample}/{SAMPLES}\n")
            log.write(f"UTC={timestamp}\n")

            try:
                shadow = weather.get_shadow_properties(cloud)

                log.write(f"PROPERTY_COUNT={len(shadow)}\n")

                # Minden property megmarad a későbbi elemzéshez.
                for code, item in shadow.items():
                    log.write(
                        f"PROPERTY code={code!r} "
                        f"dp_id={item.get('dp_id')!r} "
                        f"time={item.get('time')!r} "
                        f"value={item.get('value')!r}\n"
                    )

                # A teljes DP113 RAW adat külön, jól kereshető formában.
                b64, raw = get_wind_raw(shadow)

                if raw is not None:
                    log.write(f"DP113_BASE64={b64!r}\n")
                    log.write(f"DP113_LENGTH={len(raw)}\n")
                    log.write(f"DP113_HEX={raw.hex(' ')}\n")

                    fields = find_0e01(raw)

                    if fields:
                        for offset, value in fields:
                            log.write(
                                f"DP113_0E_01 offset={offset} value={value}\n"
                            )
                    else:
                        log.write("DP113_0E_01=NOT_FOUND\n")

                    print(
                        f"  DP113: {len(raw)} byte, "
                        f"0E01 mezők: {fields}"
                    )
                else:
                    log.write("DP113_BASE64=NOT_FOUND\n")
                    log.write("DP113_HEX=NOT_FOUND\n")
                    print("  DP113: NEM ÉRKEZETT")

            except Exception as exc:
                print(f"  HIBA: {exc}", file=sys.stderr)
                log.write(f"ERROR={exc!r}\n")

            log.flush()

            if sample < SAMPLES:
                target = start + sample * INTERVAL_SECONDS
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)

    print("=" * 80)
    print(f"CAPTURE BEFEJEZVE: {OUTPUT_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
