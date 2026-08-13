import sys
import time
import base64
import struct
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


def unsigned_values(raw):
    """Return every possible unsigned integer interpretation, big/little endian."""
    result = []

    for size in (1, 2, 3, 4):
        if len(raw) < size:
            continue

        for offset in range(len(raw) - size + 1):
            chunk = raw[offset:offset + size]

            be = int.from_bytes(chunk, "big", signed=False)
            le = int.from_bytes(chunk, "little", signed=False)

            result.append(
                (offset, size, "BE", be, chunk.hex(" "))
            )

            if size > 1 and le != be:
                result.append(
                    (offset, size, "LE", le, chunk.hex(" "))
                )

    return result


def plausible_degree_values(raw):
    """
    Find RAW byte sequences that could represent:
      - exact degrees 0..360
      - tenths of degrees 0..3600
      - hundredths of degrees 0..36000
      - 16-sector index 0..15
    """
    candidates = []

    for offset, size, endian, value, hex_value in unsigned_values(raw):
        if 0 <= value <= 360:
            candidates.append(
                f"DEGREE_EXACT offset={offset} size={size} "
                f"{endian} raw={value} degrees={value} hex=[{hex_value}]"
            )

        if 0 <= value <= 3600 and value % 10 == 0:
            candidates.append(
                f"DEGREE_X10 offset={offset} size={size} "
                f"{endian} raw={value} degrees={value / 10:.1f} "
                f"hex=[{hex_value}]"
            )

        if 0 <= value <= 36000 and value % 100 == 0:
            candidates.append(
                f"DEGREE_X100 offset={offset} size={size} "
                f"{endian} raw={value} degrees={value / 100:.2f} "
                f"hex=[{hex_value}]"
            )

        if size == 1 and 0 <= value <= 15:
            candidates.append(
                f"SECTOR_16 offset={offset} raw={value} "
                f"degrees={value * 22.5:.1f} hex=[{hex_value}]"
            )

    return candidates


def find_tlv_fields(raw):
    """
    Treat each byte as a possible field code followed by a length byte.
    This is exploratory only; it does not assume that every sequence is TLV.
    """
    fields = []

    i = 0
    while i + 2 <= len(raw):
        code = raw[i]
        length = raw[i + 1]

        if length <= 8 and i + 2 + length <= len(raw):
            value = raw[i + 2:i + 2 + length]
            fields.append(
                (i, code, length, value)
            )

        i += 1

    return fields


def main():
    print("=" * 90)
    print("YT60307 RAW - MINDEN MEZŐ VIZSGÁLATA")
    print("=" * 90)
    print(f"Tuya régió: {weather.TUYA_REGION}")
    print(f"Device ID: {weather.TUYA_DEVICE_ID}")
    print(f"Intervallum: {INTERVAL_SECONDS} mp")
    print(f"Mérések: {SAMPLES}")
    print(f"Időtartam: kb. {SAMPLES * INTERVAL_SECONDS / 60:.1f} perc")
    print("=" * 90)

    cloud = weather.create_cloud()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as log:
        log.write("YT60307 RAW ALL-FIELDS ANALYSIS\n")
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

            log.write(f"\n{'=' * 120}\n")
            log.write(f"SAMPLE={sample}/{SAMPLES}\n")
            log.write(f"UTC={timestamp}\n")

            try:
                shadow = weather.get_shadow_properties(cloud)

                log.write(f"PROPERTY_COUNT={len(shadow)}\n")

                # Minden Tuya property.
                for code, item in shadow.items():
                    log.write(
                        f"PROPERTY code={code!r} "
                        f"dp_id={item.get('dp_id')!r} "
                        f"time={item.get('time')!r} "
                        f"value={item.get('value')!r}\n"
                    )

                # DP113 / outdoor_alert_display.
                item = shadow.get("outdoor_alert_display")

                if not isinstance(item, dict):
                    log.write("DP113=NOT_FOUND\n")
                    print("  DP113: NEM ÉRKEZETT")
                else:
                    b64 = item.get("value")
                    raw = decode_b64(b64)

                    log.write(f"DP113_BASE64={b64!r}\n")

                    if raw is None:
                        log.write("DP113_RAW=DECODE_FAILED\n")
                        print("  DP113: Base64 dekódolási hiba")
                    else:
                        log.write(f"DP113_LENGTH={len(raw)}\n")
                        log.write(f"DP113_HEX={raw.hex(' ')}\n")

                        # -------------------------------------------------
                        # 1. MINDEN 1/2/3/4 BYTE-OS LEHETSÉGES ÉRTÉK
                        # -------------------------------------------------
                        log.write("\n[ALL_NUMERIC_INTERPRETATIONS]\n")

                        for offset, size, endian, value, hx in unsigned_values(raw):
                            log.write(
                                f"offset={offset:03d} "
                                f"size={size} "
                                f"{endian} "
                                f"value={value} "
                                f"hex=[{hx}]\n"
                            )

                        # -------------------------------------------------
                        # 2. 0..360 KÖZÖTTI ÉS SKÁLÁZOTT ÉRTÉKEK
                        # -------------------------------------------------
                        candidates = plausible_degree_values(raw)

                        log.write("\n[PLAUSIBLE_WIND_DEGREES]\n")

                        if candidates:
                            for candidate in candidates:
                                log.write(candidate + "\n")
                        else:
                            log.write("NONE\n")

                        # -------------------------------------------------
                        # 3. LEHETSÉGES TLV MEZŐK
                        # -------------------------------------------------
                        log.write("\n[POSSIBLE_TLV_FIELDS]\n")

                        for offset, code, length, value in find_tlv_fields(raw):
                            log.write(
                                f"offset={offset:03d} "
                                f"code=0x{code:02X} "
                                f"length={length} "
                                f"value_hex=[{value.hex(' ')}] "
                                f"value_int_be={int.from_bytes(value, 'big')} "
                                f"value_int_le={int.from_bytes(value, 'little')}\n"
                            )

                        print(
                            f"  DP113: {len(raw)} byte | "
                            f"degree candidates: {len(candidates)}"
                        )

            except Exception as exc:
                print(f"  HIBA: {exc}", file=sys.stderr)
                log.write(f"ERROR={exc!r}\n")

            log.flush()

            if sample < SAMPLES:
                target = start + sample * INTERVAL_SECONDS
                delay = target - time.monotonic()

                if delay > 0:
                    time.sleep(delay)

    print("=" * 90)
    print(f"CAPTURE BEFEJEZVE: {OUTPUT_FILE}")
    print("=" * 90)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FATAL ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
