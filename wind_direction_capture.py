import sys
import time
from datetime import datetime, timezone

# A működő weather.py-t használjuk közvetlenül.
# Nem másoljuk újra a Tuya kapcsolatfelépítését és a Shadow lekérdezést.

import weather

INTERVAL_SECONDS = 10
SAMPLES = 10
OUTPUT_FILE = "wind_capture.log"


def main():
    print("=" * 80)
    print("YT60307 WIND DIRECTION - 10 MINTÁS TESZT")
    print("=" * 80)

    # Ugyanazok a beállítások, amelyeket a weather.py használ.
    print(f"Tuya régió: {weather.TUYA_REGION}")
    print(f"Device ID: {weather.TUYA_DEVICE_ID}")

    # Pontosan a működő weather.py create_cloud() függvénye.
    cloud = weather.create_cloud()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as log:
        log.write("YT60307 WIND DIRECTION CAPTURE TEST\n")
        log.write("SOURCE=weather.py\n")
        log.write(f"TUYA_REGION={weather.TUYA_REGION}\n")
        log.write(f"DEVICE_ID={weather.TUYA_DEVICE_ID}\n")
        log.write(f"INTERVAL_SECONDS={INTERVAL_SECONDS}\n")
        log.write(f"SAMPLES={SAMPLES}\n")
        log.write("=" * 100 + "\n")

        start = time.monotonic()

        for sample in range(1, SAMPLES + 1):
            timestamp = datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            )

            print()
            print(f"--- MINTA {sample}/{SAMPLES} | {timestamp} ---")

            log.write(
                f"\nSAMPLE={sample}/{SAMPLES}\n"
                f"UTC={timestamp}\n"
            )

            try:
                # EZ A MŰKÖDŐ weather.py SAJÁT FÜGGVÉNYE.
                shadow = weather.get_shadow_properties(cloud)

                log.write(
                    f"PROPERTY_COUNT={len(shadow)}\n"
                )

                print(
                    f"Shadow property-k: {len(shadow)}"
                )

                for code, item in shadow.items():
                    value = item.get("value")
                    dp_id = item.get("dp_id")
                    prop_time = item.get("time")

                    line = (
                        f"PROPERTY "
                        f"code={code!r} "
                        f"dp_id={dp_id!r} "
                        f"time={prop_time!r} "
                        f"value={value!r}"
                    )

                    print(line)
                    log.write(line + "\n")

                if not shadow:
                    log.write(
                        "WARNING=EMPTY_SHADOW\n"
                    )

            except Exception as exc:
                print(
                    f"HIBA: {exc}",
                    file=sys.stderr
                )

                log.write(
                    f"ERROR={exc!r}\n"
                )

            log.flush()

            if sample < SAMPLES:
                target = (
                    start
                    + sample * INTERVAL_SECONDS
                )

                delay = target - time.monotonic()

                if delay > 0:
                    time.sleep(delay)

    print()
    print("=" * 80)
    print("TESZT BEFEJEZVE")
    print(f"Eredmény: {OUTPUT_FILE}")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            f"FATAL ERROR: {exc}",
            file=sys.stderr
        )
        sys.exit(1)
