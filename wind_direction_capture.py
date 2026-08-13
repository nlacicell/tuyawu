import os
import sys
import json
import time
import base64
from datetime import datetime, timezone

# FONTOS:
# A működő weather.py-ból használjuk a Tuya Cloud kapcsolatot.
# Így a régió, Access ID, Secret és egyéb beállítások pontosan
# ugyanúgy működnek, mint a normál WU-feltöltő scripted.
#
# A repository gyökerében ennek a fájlnak együtt kell lennie:
#     weather.py
#     wind_direction_capture.py

try:
    import weather
except Exception as exc:
    print(f"Nem sikerült betölteni a weather.py fájlt: {exc}", file=sys.stderr)
    sys.exit(1)


INTERVAL_SECONDS = 10
SAMPLES = 10
OUTPUT_FILE = "wind_capture.log"


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

    result = []

    for i in range(len(raw) - 2):
        if raw[i] == 0x0E and raw[i + 1] == 0x01:
            result.append((i, raw[i + 2]))

    return result


def get_full_shadow_response(cloud, device_id):
    endpoint = (
        f"/v2.0/cloud/thing/"
        f"{device_id}/shadow/properties"
    )

    response = cloud.cloudrequest(endpoint)

    if not isinstance(response, dict):
        raise RuntimeError(
            f"A Tuya válasz nem dictionary: {response!r}"
        )

    if response.get("success") is False:
        raise RuntimeError(
            f"Tuya Shadow hiba: "
            f"{response.get('code')} "
            f"{response.get('msg')}"
        )

    return endpoint, response


def response_to_shadow(response):
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

            if not code:
                continue

            shadow[str(code)] = {
                "value": item.get("value"),
                "dp_id": item.get(
                    "dp_id",
                    item.get("dpId")
                ),
                "time": item.get("time"),
                "custom_name": item.get(
                    "custom_name",
                    ""
                ),
            }

    return shadow


def write_sample(log, sample_no, endpoint, response):
    timestamp = datetime.now(
        timezone.utc
    ).isoformat(
        timespec="milliseconds"
    )

    shadow = response_to_shadow(response)

    log.write("\n")
    log.write("=" * 120 + "\n")
    log.write(
        f"SAMPLE={sample_no}/{SAMPLES}\n"
    )
    log.write(
        f"UTC={timestamp}\n"
    )
    log.write(
        f"ENDPOINT={endpoint}\n"
    )
    log.write(
        f"PROPERTY_COUNT={len(shadow)}\n"
    )

    # A teljes Tuya válasz megőrzése.
    log.write(
        "FULL_TUYA_RESPONSE_JSON=\n"
    )
    log.write(
        json.dumps(
            response,
            ensure_ascii=False,
            indent=2
        )
    )
    log.write("\n")

    print(
        f"[{sample_no:03d}/{SAMPLES}] "
        f"{timestamp}  "
        f"properties={len(shadow)}"
    )

    for code, item in shadow.items():
        value = item.get("value")

        log.write(
            f"PROPERTY "
            f"code={code!r} "
            f"dp_id={item.get('dp_id')!r} "
            f"time={item.get('time')!r} "
            f"name={item.get('custom_name')!r} "
            f"value={value!r}\n"
        )

        raw = decode_b64(value)

        if raw is None:
            continue

        log.write(
            f"RAW "
            f"code={code!r} "
            f"length={len(raw)} "
            f"hex={raw.hex(' ')}\n"
        )

        for offset, byte_value in find_all_0e01(raw):
            log.write(
                f"FIELD_0E_01 "
                f"code={code!r} "
                f"offset={offset} "
                f"value={byte_value}\n"
            )

    # Kiemelten mentjük az eddig vizsgált DP113-at.
    dp113 = shadow.get(
        "outdoor_alert_display"
    )

    if dp113:
        raw_b64 = dp113.get("value")
        raw = decode_b64(raw_b64)

        log.write(
            f"DP113_BASE64={raw_b64!r}\n"
        )

        if raw is not None:
            log.write(
                f"DP113_HEX={raw.hex(' ')}\n"
            )

            for offset, byte_value in find_all_0e01(raw):
                log.write(
                    f"DP113_0E_01 "
                    f"offset={offset} "
                    f"value={byte_value}\n"
                )

    log.flush()


def main():
    # A weather.py saját környezet-ellenőrzését használjuk,
    # de WU kulcs nem szükséges a capture-hez.
    required = {
        "TUYA_ACCESS_ID":
            os.environ.get("TUYA_ACCESS_ID"),
        "TUYA_ACCESS_SECRET":
            os.environ.get("TUYA_ACCESS_SECRET"),
        "TUYA_DEVICE_ID":
            os.environ.get("TUYA_DEVICE_ID"),
    }

    missing = [
        name
        for name, value in required.items()
        if not value
    ]

    if missing:
        raise RuntimeError(
            "Hiányzó GitHub Secret: "
            + ", ".join(missing)
        )

    device_id = required[
        "TUYA_DEVICE_ID"
    ]

    # EZ A LÉNYEG:
    # a weather.py saját create_cloud() függvényét használjuk.
    # Nem állítunk be külön régiót.
    cloud = weather.create_cloud()

    print("=" * 80)
    print("YT60307 WIND DIRECTION RAW CAPTURE")
    print("=" * 80)
    print(
        "A Tuya Cloud kapcsolatot közvetlenül "
        "a működő weather.py biztosítja."
    )
    print(
        f"Intervallum: {INTERVAL_SECONDS} mp"
    )
    print(
        f"Mérések: {SAMPLES}"
    )
    print(
        f"Időtartam: kb. "
        f"{SAMPLES * INTERVAL_SECONDS / 60:.1f} perc"
    )
    print(
        "WU-feltöltés: NINCS"
    )
    print("=" * 80)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as log:

        log.write(
            "YT60307 WIND DIRECTION RAW CAPTURE\n"
        )
        log.write(
            "TUYA CONNECTION = weather.py create_cloud()\n"
        )
        log.write(
            f"INTERVAL_SECONDS={INTERVAL_SECONDS}\n"
        )
        log.write(
            f"SAMPLES={SAMPLES}\n"
        )
        log.write(
            f"DEVICE_ID={device_id}\n"
        )

        start = time.monotonic()

        for sample_no in range(
            1,
            SAMPLES + 1
        ):
            try:
                endpoint, response = (
                    get_full_shadow_response(
                        cloud,
                        device_id
                    )
                )

                write_sample(
                    log,
                    sample_no,
                    endpoint,
                    response
                )

            except Exception as exc:
                timestamp = datetime.now(
                    timezone.utc
                ).isoformat(
                    timespec="milliseconds"
                )

                print(
                    f"HIBA [{sample_no:03d}]: "
                    f"{exc}",
                    file=sys.stderr
                )

                log.write(
                    f"ERROR "
                    f"UTC={timestamp} "
                    f"sample={sample_no} "
                    f"error={exc!r}\n"
                )

                log.flush()

            if sample_no < SAMPLES:
                target = (
                    start
                    + sample_no
                    * INTERVAL_SECONDS
                )

                delay = (
                    target
                    - time.monotonic()
                )

                if delay > 0:
                    time.sleep(delay)

    print()
    print("=" * 80)
    print(
        f"CAPTURE BEFEJEZVE: "
        f"{OUTPUT_FILE}"
    )
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
