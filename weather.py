import json
import math
import os
import sys
import time
from typing import Any

import requests
import tinytuya


# Tuya Cloud credentials (GitHub Actions Secrets / environment variables)
TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
TUYA_REGION = os.environ.get("TUYA_REGION", "eu")

# Optional explicit DP overrides. These are useful if a non-standard weather
# station uses unusual status-code names.
TUYA_TEMP_CODE = os.environ.get("TUYA_TEMP_CODE")
TUYA_HUMIDITY_CODE = os.environ.get("TUYA_HUMIDITY_CODE")
TUYA_PRESSURE_CODE = os.environ.get("TUYA_PRESSURE_CODE")
TUYA_WIND_SPEED_CODE = os.environ.get("TUYA_WIND_SPEED_CODE")
TUYA_WIND_GUST_CODE = os.environ.get("TUYA_WIND_GUST_CODE")
TUYA_WIND_DIRECTION_CODE = os.environ.get("TUYA_WIND_DIRECTION_CODE")
TUYA_RAIN_CODE = os.environ.get("TUYA_RAIN_CODE")

WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")


TEMP_NAMES = ("temperature", "temp", "thermal")
HUMIDITY_NAMES = ("humidity", "humid", "relative_humidity", "hum")
PRESSURE_NAMES = ("pressure", "barometer", "barometric")
WIND_SPEED_NAMES = ("wind_speed", "windspeed", "windvelocity", "wind_velocity")
WIND_GUST_NAMES = ("wind_gust", "gust_speed", "gust")
WIND_DIRECTION_NAMES = ("wind_direction", "winddirection", "wind_dir", "windangle")
RAIN_NAMES = ("rain", "rainfall", "precipitation")


def require_environment() -> None:
    required = {
        "TUYA_ACCESS_ID": TUYA_ACCESS_ID,
        "TUYA_ACCESS_SECRET": TUYA_ACCESS_SECRET,
        "TUYA_DEVICE_ID": TUYA_DEVICE_ID,
        "WU_STATION_ID": WU_STATION_ID,
        "WU_STATION_KEY": WU_STATION_KEY,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError("Hiányzó környezeti változók: " + ", ".join(missing))


def cloud_client() -> tinytuya.Cloud:
    print(f"Tuya Cloud régió: {TUYA_REGION}")
    return tinytuya.Cloud(
        apiRegion=TUYA_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
    )


def validate_cloud_response(response: Any, endpoint: str) -> dict[str, Any]:
    if not isinstance(response, dict):
        raise RuntimeError(f"Tuya hibás válasz ({endpoint}): {response!r}")

    if response.get("success") is False:
        raise RuntimeError(
            f"Tuya API hiba ({endpoint}): "
            f"code={response.get('code')!r}, msg={response.get('msg')!r}"
        )

    if "result" not in response:
        raise RuntimeError(f"Tuya válaszból hiányzik a result ({endpoint}): {response!r}")

    return response


def get_tuya_data() -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    """Read status + specification exactly once each from Tuya Cloud.

    The specification tells us which status codes exist and, importantly,
    what unit and scale each numeric value uses.
    """
    cloud = cloud_client()

    status_endpoint = f"/v1.0/iot-03/devices/{TUYA_DEVICE_ID}/status"
    spec_endpoint = f"/v1.0/iot-03/devices/{TUYA_DEVICE_ID}/specification"

    print(f"Tuya státusz lekérése: {status_endpoint}")
    status_response = validate_cloud_response(cloud.get(status_endpoint), status_endpoint)
    status_result = status_response.get("result")
    if not isinstance(status_result, list):
        raise RuntimeError(f"A Tuya status result nem lista: {status_result!r}")

    raw_status: dict[str, Any] = {}
    for item in status_result:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        if code:
            raw_status[str(code)] = item.get("value")

    print(f"Tuya státusz DP-k ({len(raw_status)} db):")
    for code, value in raw_status.items():
        print(f"  {code}: {value!r}")

    print(f"Tuya specifikáció lekérése: {spec_endpoint}")
    spec_response = validate_cloud_response(cloud.get(spec_endpoint), spec_endpoint)
    spec_result = spec_response.get("result")
    if not isinstance(spec_result, dict):
        raise RuntimeError(f"A Tuya specification result nem objektum: {spec_result!r}")

    spec_by_code: dict[str, dict[str, Any]] = {}
    statuses = spec_result.get("status", [])
    if isinstance(statuses, list):
        for item in statuses:
            if not isinstance(item, dict) or not item.get("code"):
                continue
            code = str(item["code"])
            values = item.get("values", item.get("options", "{}"))
            if isinstance(values, str):
                try:
                    values = json.loads(values) if values else {}
                except json.JSONDecodeError:
                    values = {}
            if not isinstance(values, dict):
                values = {}
            spec_by_code[code] = {
                "code": code,
                "name": item.get("name") or item.get("desc") or "",
                "type": item.get("type", ""),
                "unit": values.get("unit", ""),
                "scale": values.get("scale", 0),
                "step": values.get("step", 1),
                "min": values.get("min"),
                "max": values.get("max"),
                "raw_values": values,
            }

    print(f"Tuya specifikációs státuszok ({len(spec_by_code)} db):")
    for code, meta in spec_by_code.items():
        if code in raw_status:
            print(
                f"  {code}: name={meta['name']!r}, type={meta['type']!r}, "
                f"unit={meta['unit']!r}, scale={meta['scale']!r}, "
                f"value={raw_status[code]!r}"
            )

    return raw_status, spec_by_code


def normalized_text(*values: Any) -> str:
    return " ".join(str(v).lower() for v in values if v is not None)


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def scaled_number(value: Any, meta: dict[str, Any] | None) -> float | None:
    number = numeric(value)
    if number is None:
        return None

    scale = 0
    if meta:
        try:
            scale = int(meta.get("scale", 0) or 0)
        except (TypeError, ValueError):
            scale = 0

    # Tuya's scale means decimal places / a power of ten.
    return number / (10 ** scale)


def unit_for(code: str, meta: dict[str, Any] | None) -> str:
    return str((meta or {}).get("unit") or "").strip().lower()


def find_code(
    raw_status: dict[str, Any],
    spec: dict[str, dict[str, Any]],
    override: str | None,
    code_candidates: tuple[str, ...],
    name_candidates: tuple[str, ...],
) -> str | None:
    if override:
        if override in raw_status:
            return override
        raise RuntimeError(f"A megadott DP kód ({override}) nincs a Tuya státuszban.")

    # Exact/common Tuya codes first.
    for candidate in code_candidates:
        if candidate in raw_status:
            return candidate

    # Then use both code and specification name/description.
    scored: list[tuple[int, str]] = []
    for code in raw_status:
        meta = spec.get(code, {})
        text = normalized_text(code, meta.get("name"), meta.get("desc"))
        score = sum(3 for word in name_candidates if word in text)
        if score:
            scored.append((score, code))

    if not scored:
        return None
    scored.sort(reverse=True)
    return scored[0][1]


def convert_temperature(value: Any, meta: dict[str, Any] | None) -> float | None:
    celsius = scaled_number(value, meta)
    if celsius is None:
        return None

    unit = unit_for("", meta)
    if unit in {"f", "°f", "fahrenheit"}:
        return (celsius - 32.0) * 5.0 / 9.0
    if unit in {"k", "kelvin"}:
        return celsius - 273.15
    return celsius


def convert_pressure_to_hpa(value: Any, meta: dict[str, Any] | None) -> float | None:
    pressure = scaled_number(value, meta)
    if pressure is None:
        return None

    unit = unit_for("", meta)
    if unit in {"pa", "pascal", "pascals"}:
        return pressure / 100.0
    if unit in {"kpa"}:
        return pressure * 10.0
    if unit in {"inhg", "in hg", "in"}:
        return pressure * 33.8638866667
    if unit in {"mmhg", "mm hg"}:
        return pressure * 1.33322387415
    # Weather-station pressure codes without a unit are commonly reported
    # either in hPa or Pa. Do not invent a fixed value; infer from magnitude.
    if pressure > 2000:
        return pressure / 100.0
    return pressure


def convert_wind_speed_to_mph(value: Any, meta: dict[str, Any] | None) -> float | None:
    speed = scaled_number(value, meta)
    if speed is None:
        return None
    unit = unit_for("", meta)
    if unit in {"m/s", "mps", "meter per second", "meters per second"}:
        return speed * 2.2369362921
    if unit in {"km/h", "kmh", "kph", "kilometer per hour", "kilometers per hour"}:
        return speed * 0.6213711922
    if unit in {"mph", "mi/h"}:
        return speed
    if unit in {"knot", "knots", "kt", "kts"}:
        return speed * 1.150779448
    # If a wind code has no unit in the specification, m/s is the least
    # surprising fallback for Tuya weather devices.
    return speed * 2.2369362921


def convert_rain_to_inches(value: Any, meta: dict[str, Any] | None) -> float | None:
    rain = scaled_number(value, meta)
    if rain is None:
        return None
    unit = unit_for("", meta)
    if unit in {"mm", "millimeter", "millimeters"}:
        return rain / 25.4
    if unit in {"cm", "centimeter", "centimeters"}:
        return rain / 2.54
    if unit in {"in", "inch", "inches"}:
        return rain
    return rain / 25.4


def parse_sensor_data(raw_status: dict[str, Any], spec: dict[str, dict[str, Any]]) -> dict[str, str | int]:
    """Map the real Tuya status/specification to Weather Underground fields."""
    print("\n--- Érzékelők felismerése ---")

    temp_code = find_code(
        raw_status,
        spec,
        TUYA_TEMP_CODE,
        ("va_temperature", "temp_current", "temperature", "outdoor_temp", "temp"),
        TEMP_NAMES,
    )
    humidity_code = find_code(
        raw_status,
        spec,
        TUYA_HUMIDITY_CODE,
        ("va_humidity", "humidity", "outdoor_humidity", "hum"),
        HUMIDITY_NAMES,
    )
    pressure_code = find_code(
        raw_status,
        spec,
        TUYA_PRESSURE_CODE,
        ("pressure", "va_pressure", "barometer", "barometric_pressure"),
        PRESSURE_NAMES,
    )
    wind_speed_code = find_code(
        raw_status,
        spec,
        TUYA_WIND_SPEED_CODE,
        ("wind_speed", "windspeed", "wind_speed_current"),
        WIND_SPEED_NAMES,
    )
    wind_gust_code = find_code(
        raw_status,
        spec,
        TUYA_WIND_GUST_CODE,
        ("wind_gust", "windgust", "gust_speed"),
        WIND_GUST_NAMES,
    )
    wind_direction_code = find_code(
        raw_status,
        spec,
        TUYA_WIND_DIRECTION_CODE,
        ("wind_direction", "winddirection", "wind_dir"),
        WIND_DIRECTION_NAMES,
    )
    rain_code = find_code(
        raw_status,
        spec,
        TUYA_RAIN_CODE,
        ("rain", "rainfall", "rain_amount"),
        RAIN_NAMES,
    )

    print(f"  Hőmérséklet: {temp_code or 'NINCS'}")
    print(f"  Páratartalom: {humidity_code or 'NINCS'}")
    print(f"  Légnyomás: {pressure_code or 'NINCS'}")
    print(f"  Szélsebesség: {wind_speed_code or 'NINCS'}")
    print(f"  Széllökés: {wind_gust_code or 'NINCS'}")
    print(f"  Szélirány: {wind_direction_code or 'NINCS'}")
    print(f"  Csapadék: {rain_code or 'NINCS'}")

    payload: dict[str, str | int] = {"software": "TuyaWeatherBridge/3.0"}

    if temp_code:
        temp_c = convert_temperature(raw_status[temp_code], spec.get(temp_code))
        if temp_c is not None and -80 <= temp_c <= 80:
            payload["tempf"] = f"{temp_c * 9 / 5 + 32:.1f}"
        else:
            print(f"FIGYELEM: érvénytelen hőmérséklet: {temp_c!r}")

    if humidity_code:
        humidity = scaled_number(raw_status[humidity_code], spec.get(humidity_code))
        if humidity is not None and 0 <= humidity <= 100:
            payload["humidity"] = int(round(humidity))
        else:
            print(f"FIGYELEM: érvénytelen páratartalom: {humidity!r}")

    if pressure_code:
        pressure_hpa = convert_pressure_to_hpa(raw_status[pressure_code], spec.get(pressure_code))
        if pressure_hpa is not None and 800 <= pressure_hpa <= 1200:
            payload["barom"] = f"{pressure_hpa * 0.0295299830714:.2f}"
        else:
            print(f"FIGYELEM: érvénytelen légnyomás: {pressure_hpa!r} hPa")

    if wind_speed_code:
        wind_mph = convert_wind_speed_to_mph(raw_status[wind_speed_code], spec.get(wind_speed_code))
        if wind_mph is not None and 0 <= wind_mph <= 200:
            payload["windspeedmph"] = f"{wind_mph:.1f}"

    if wind_gust_code:
        gust_mph = convert_wind_speed_to_mph(raw_status[wind_gust_code], spec.get(wind_gust_code))
        if gust_mph is not None and 0 <= gust_mph <= 250:
            payload["windgustmph"] = f"{gust_mph:.1f}"

    if wind_direction_code:
        direction = scaled_number(raw_status[wind_direction_code], spec.get(wind_direction_code))
        if direction is not None and 0 <= direction <= 360:
            payload["winddir"] = str(int(round(direction)) % 360)

    if rain_code:
        rain_in = convert_rain_to_inches(raw_status[rain_code], spec.get(rain_code))
        if rain_in is not None and 0 <= rain_in <= 100:
            payload["rainin"] = f"{rain_in:.2f}"

    # Do not upload fake values. Temperature/humidity/pressure are the core
    # station values; if none of them were found, the Tuya mapping is wrong.
    core = {key: payload[key] for key in ("tempf", "humidity", "barom") if key in payload}
    if not core:
        raise RuntimeError(
            "A Tuya státuszból nem sikerült hőmérsékletet, páratartalmat vagy "
            "légnyomást felismerni. A logban látható DP-k alapján állítsd be a "
            "TUYA_TEMP_CODE / TUYA_HUMIDITY_CODE / TUYA_PRESSURE_CODE secret(eket)."
        )

    print(f"Feldolgozott Weather Underground adatok: {payload}")
    return payload


def upload_to_wunderground(weather_data: dict[str, str | int]) -> None:
    url = "https://weatherstation.wunderground.com/weatherstation/updateweatherstation.php"
    params = {
        "ID": WU_STATION_ID,
        "PASSWORD": WU_STATION_KEY,
        "dateutc": "now",
        "action": "updateraw",
        **weather_data,
    }

    print("Feltöltés a Weather Undergroundra...")
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    print(f"WU válasz: {response.status_code} - {response.text.strip()}")

    if response.text.strip().lower() not in {"success", "success\n"}:
        # WU sometimes returns additional text, so do not fail merely because
        # the response is not exactly the single word 'success'.
        if "success" not in response.text.lower():
            raise RuntimeError(f"Weather Underground elutasította a frissítést: {response.text}")


def main() -> None:
    require_environment()
    raw_status, specification = get_tuya_data()
    weather_payload = parse_sensor_data(raw_status, specification)
    upload_to_wunderground(weather_payload)
    print("Sikeres futtatás!")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"HIBA: {exc}", file=sys.stderr)
        sys.exit(1)
