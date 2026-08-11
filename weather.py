import json
import math
import os
import sys
from typing import Any

import requests
import tinytuya


TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
TUYA_REGION = os.environ.get("TUYA_REGION", "eu")

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
WIND_DIRECTION_NAMES = (
    "wind_direction",
    "winddirection",
    "wind_dir",
    "windangle",
)
RAIN_NAMES = ("rain", "rainfall", "precipitation")


def require_environment():
    required = {
        "TUYA_ACCESS_ID": TUYA_ACCESS_ID,
        "TUYA_ACCESS_SECRET": TUYA_ACCESS_SECRET,
        "TUYA_DEVICE_ID": TUYA_DEVICE_ID,
        "WU_STATION_ID": WU_STATION_ID,
        "WU_STATION_KEY": WU_STATION_KEY,
    }

    missing = [name for name, value in required.items() if not value]

    if missing:
        raise RuntimeError(
            "Hiányzó környezeti változók: " + ", ".join(missing)
        )


def cloud_client():
    print(f"Tuya Cloud régió: {TUYA_REGION}")

    return tinytuya.Cloud(
        apiRegion=TUYA_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
    )


def check_response(response, endpoint):
    if not isinstance(response, dict):
        raise RuntimeError(
            f"Tuya hibás válasz ({endpoint}): {response!r}"
        )

    if "Error" in response or "Err" in response:
        raise RuntimeError(
            f"Tuya/TinyTuya hiba ({endpoint}): "
            f"Err={response.get('Err')!r}, "
            f"Error={response.get('Error')!r}, "
            f"Payload={response.get('Payload')!r}"
        )

    if response.get("success") is False:
        raise RuntimeError(
            f"Tuya API hiba ({endpoint}): "
            f"code={response.get('code')!r}, "
            f"msg={response.get('msg')!r}"
        )

    if "result" not in response:
        raise RuntimeError(
            f"Tuya válaszból hiányzik a result ({endpoint}): "
            f"{response!r}"
        )

    return response


def get_tuya_data():

    cloud = cloud_client()

    status_endpoint = (
        f"/v1.0/iot-03/devices/{TUYA_DEVICE_ID}/status"
    )

    spec_endpoint = (
        f"/v1.0/iot-03/devices/{TUYA_DEVICE_ID}/specification"
    )

    print()
    print("========================================")
    print("TUYA ADATOK LEKÉRÉSE")
    print("========================================")

    print(f"Tuya státusz lekérése: {status_endpoint}")

    # FONTOS:
    # A TinyTuya Cloud objektumnak nincs .get() metódusa.
    # A helyes metódus a getstatus().

    status_response = check_response(
        cloud.getstatus(TUYA_DEVICE_ID),
        status_endpoint,
    )

    status_result = status_response.get("result")

    if not isinstance(status_result, list):
        raise RuntimeError(
            f"A Tuya status result nem lista: {status_result!r}"
        )

    raw_status = {}

    for item in status_result:

        if not isinstance(item, dict):
            continue

        code = item.get("code")

        if code:
            raw_status[str(code)] = item.get("value")

    print()
    print(f"Tuya státusz DP-k: {len(raw_status)} db")
    print("----------------------------------------")

    for code, value in raw_status.items():
        print(f"{code}: {value!r}")

    print("----------------------------------------")
    print()

    # SPECIFICATION

    print(f"Tuya specifikáció lekérése: {spec_endpoint}")

    try:
        spec_response = check_response(
            cloud.getproperties(TUYA_DEVICE_ID),
            spec_endpoint,
        )

        spec_result = spec_response.get("result")

    except Exception as exc:
        print(
            "FIGYELEM: a specifikáció lekérése nem sikerült."
        )
        print(exc)

        # A státuszadatokat ettől még használjuk.
        spec_result = {}

    spec_by_code = {}

    if isinstance(spec_result, dict):

        statuses = spec_result.get("status", [])

        if isinstance(statuses, list):

            for item in statuses:

                if not isinstance(item, dict):
                    continue

                if not item.get("code"):
                    continue

                code = str(item["code"])

                values = item.get(
                    "values",
                    item.get("options", "{}"),
                )

                if isinstance(values, str):

                    try:
                        values = json.loads(values)
                    except Exception:
                        values = {}

                if not isinstance(values, dict):
                    values = {}

                spec_by_code[code] = {
                    "code": code,
                    "name": item.get("name")
                    or item.get("desc")
                    or "",
                    "type": item.get("type", ""),
                    "unit": values.get("unit", ""),
                    "scale": values.get("scale", 0),
                    "step": values.get("step", 1),
                    "min": values.get("min"),
                    "max": values.get("max"),
                    "raw_values": values,
                }

    print()
    print(
        f"Specifikációban szereplő DP-k: "
        f"{len(spec_by_code)} db"
    )

    for code, meta in spec_by_code.items():

        if code in raw_status:

            print(
                f"{code}: "
                f"name={meta['name']!r}, "
                f"type={meta['type']!r}, "
                f"unit={meta['unit']!r}, "
                f"scale={meta['scale']!r}, "
                f"value={raw_status[code]!r}"
            )

    return raw_status, spec_by_code


def normalized_text(*values):

    return " ".join(
        str(value).lower()
        for value in values
        if value is not None
    )


def numeric(value):

    if isinstance(value, bool):
        return None

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def scaled_number(value, meta):

    number = numeric(value)

    if number is None:
        return None

    scale = 0

    if meta:

        try:
            scale = int(meta.get("scale", 0) or 0)
        except (TypeError, ValueError):
            scale = 0

    return number / (10 ** scale)


def unit_for(meta):

    if not meta:
        return ""

    return str(
        meta.get("unit") or ""
    ).strip().lower()


def find_code(
    raw_status,
    specification,
    override,
    candidates,
    name_candidates,
):

    # Ha Secretben megadtunk konkrét DP-t,
    # azt használjuk.

    if override:

        if override in raw_status:
            return override

        raise RuntimeError(
            f"A megadott DP kód ({override}) "
            f"nincs a Tuya státuszban."
        )

    # Először a jól ismert Tuya DP-k.

    for candidate in candidates:

        if candidate in raw_status:
            return candidate

    # Ezután név alapján keresünk.

    scored = []

    for code in raw_status:

        meta = specification.get(code, {})

        text = normalized_text(
            code,
            meta.get("name"),
            meta.get("desc"),
        )

        score = 0

        for word in name_candidates:

            if word in text:
                score += 3

        if score:
            scored.append((score, code))

    if not scored:
        return None

    scored.sort(reverse=True)

    return scored[0][1]


def convert_temperature(value, meta):

    temperature = scaled_number(value, meta)

    if temperature is None:
        return None

    unit = unit_for(meta)

    if unit in ("f", "°f", "fahrenheit"):
        return (temperature - 32) * 5 / 9

    if unit in ("k", "kelvin"):
        return temperature - 273.15

    return temperature


def convert_pressure_to_hpa(value, meta):

    pressure = scaled_number(value, meta)

    if pressure is None:
        return None

    unit = unit_for(meta)

    if unit in ("pa", "pascal", "pascals"):
        return pressure / 100

    if unit == "kpa":
        return pressure * 10

    if unit in ("inhg", "in hg"):
        return pressure * 33.8638867

    if unit in ("mmhg", "mm hg"):
        return pressure * 1.33322387

    # Ha nincs unit, akkor a nagyságrend alapján
    # próbáljuk eldönteni.

    if pressure > 2000:
        return pressure / 100

    return pressure


def convert_wind_speed_to_mph(value, meta):

    speed = scaled_number(value, meta)

    if speed is None:
        return None

    unit = unit_for(meta)

    if unit in (
        "m/s",
        "mps",
        "meter per second",
        "meters per second",
    ):
        return speed * 2.2369363

    if unit in (
        "km/h",
        "kmh",
        "kph",
        "kilometer per hour",
        "kilometers per hour",
    ):
        return speed * 0.6213712

    if unit in ("mph", "mi/h"):
        return speed

    if unit in ("knot", "knots", "kt", "kts"):
        return speed * 1.1507794

    # Tuya időjárásállomásoknál gyakori,
    # ha nincs unit megadva.

    return speed * 2.2369363


def convert_rain_to_inches(value, meta):

    rain = scaled_number(value, meta)

    if rain is None:
        return None

    unit = unit_for(meta)

    if unit in (
        "mm",
        "millimeter",
        "millimeters",
    ):
        return rain / 25.4

    if unit in (
        "cm",
        "centimeter",
        "centimeters",
    ):
        return rain / 2.54

    if unit in (
        "in",
        "inch",
        "inches",
    ):
        return rain

    return rain / 25.4


def parse_sensor_data(raw_status, specification):

    print()
    print("========================================")
    print("ÉRZÉKELŐK FELISMERÉSE")
    print("========================================")

    temp_code = find_code(
        raw_status,
        specification,
        TUYA_TEMP_CODE,
        (
            "va_temperature",
            "temp_current",
            "temperature",
            "outdoor_temp",
            "temp",
        ),
        TEMP_NAMES,
    )

    humidity_code = find_code(
        raw_status,
        specification,
        TUYA_HUMIDITY_CODE,
        (
            "va_humidity",
            "humidity",
            "outdoor_humidity",
            "hum",
        ),
        HUMIDITY_NAMES,
    )

    pressure_code = find_code(
        raw_status,
        specification,
        TUYA_PRESSURE_CODE,
        (
            "pressure",
            "va_pressure",
            "barometer",
            "barometric_pressure",
        ),
        PRESSURE_NAMES,
    )

    wind_speed_code = find_code(
        raw_status,
        specification,
        TUYA_WIND_SPEED_CODE,
        (
            "wind_speed",
            "windspeed",
            "wind_speed_current",
        ),
        WIND_SPEED_NAMES,
    )

    wind_gust_code = find_code(
        raw_status,
        specification,
        TUYA_WIND_GUST_CODE,
        (
            "wind_gust",
            "windgust",
            "gust_speed",
        ),
        WIND_GUST_NAMES,
    )

    wind_direction_code = find_code(
        raw_status,
        specification,
        TUYA_WIND_DIRECTION_CODE,
        (
            "wind_direction",
            "winddirection",
            "wind_dir",
        ),
        WIND_DIRECTION_NAMES,
    )

    rain_code = find_code(
        raw_status,
        specification,
        TUYA_RAIN_CODE,
        (
            "rain",
            "rainfall",
            "rain_amount",
        ),
        RAIN_NAMES,
    )

    print(f"Hőmérséklet:   {temp_code or 'NINCS'}")
    print(f"Páratartalom:  {humidity_code or 'NINCS'}")
    print(f"Légnyomás:     {pressure_code or 'NINCS'}")
    print(f"Szélsebesség:  {wind_speed_code or 'NINCS'}")
    print(f"Széllökés:     {wind_gust_code or 'NINCS'}")
    print(f"Szélirány:     {wind_direction_code or 'NINCS'}")
    print(f"Csapadék:      {rain_code or 'NINCS'}")

    payload = {
        "software": "TuyaWeatherBridge/3.1"
    }

    # HŐMÉRSÉKLET

    if temp_code:

        temp_c = convert_temperature(
            raw_status[temp_code],
            specification.get(temp_code),
        )

        print(
            f"Hőmérséklet érték: "
            f"{raw_status[temp_code]!r} -> "
            f"{temp_c!r} °C"
        )

        if temp_c is not None and -80 <= temp_c <= 80:

            payload["tempf"] = (
                f"{temp_c * 9 / 5 + 32:.1f}"
            )

    # PÁRATARTALOM

    if humidity_code:

        humidity = scaled_number(
            raw_status[humidity_code],
            specification.get(humidity_code),
        )

        print(
            f"Páratartalom érték: "
            f"{raw_status[humidity_code]!r} -> "
            f"{humidity!r} %"
        )

        if humidity is not None and 0 <= humidity <= 100:

            payload["humidity"] = int(round(humidity))

    # LÉGNYOMÁS

    if pressure_code:

        pressure_hpa = convert_pressure_to_hpa(
            raw_status[pressure_code],
            specification.get(pressure_code),
        )

        print(
            f"Légnyomás érték: "
            f"{raw_status[pressure_code]!r} -> "
            f"{pressure_hpa!r} hPa"
        )

        if (
            pressure_hpa is not None
            and 800 <= pressure_hpa <= 1200
        ):

            payload["barom"] = (
                f"{pressure_hpa * 0.0295299831:.2f}"
            )

    # SZÉLSEBESSÉG

    if wind_speed_code:

        wind_mph = convert_wind_speed_to_mph(
            raw_status[wind_speed_code],
            specification.get(wind_speed_code),
        )

        if (
            wind_mph is not None
            and 0 <= wind_mph <= 200
        ):

            payload["windspeedmph"] = (
                f"{wind_mph:.1f}"
            )

    # SZÉLLÖKÉS

    if wind_gust_code:

        gust_mph = convert_wind_speed_to_mph(
            raw_status[wind_gust_code],
            specification.get(wind_gust_code),
        )

        if (
            gust_mph is not None
            and 0 <= gust_mph <= 250
        ):

            payload["windgustmph"] = (
                f"{gust_mph:.1f}"
            )

    # SZÉLIRÁNY

    if wind_direction_code:

        direction = scaled_number(
            raw_status[wind_direction_code],
            specification.get(wind_direction_code),
        )

        if (
            direction is not None
            and 0 <= direction <= 360
        ):

            payload["winddir"] = str(
                int(round(direction)) % 360
            )

    # CSAPADÉK

    if rain_code:

        rain_in = convert_rain_to_inches(
            raw_status[rain_code],
            specification.get(rain_code),
        )

        if (
            rain_in is not None
            and 0 <= rain_in <= 100
        ):

            payload["rainin"] = f"{rain_in:.2f}"

    print()
    print("========================================")
    print("WEATHER UNDERGROUND ADATOK")
    print("========================================")

    for key, value in payload.items():
        print(f"{key} = {value}")

    print("========================================")

    core = {
        key: payload[key]
        for key in (
            "tempf",
            "humidity",
            "barom",
        )
        if key in payload
    }

    if not core:

        raise RuntimeError(
            "Nem sikerült felismerni a Tuya "
            "hőmérséklet/páratartalom/légnyomás adatokat."
        )

    return payload


def upload_to_wunderground(weather_data):

    url = (
        "https://weatherstation.wunderground.com/"
        "weatherstation/updateweatherstation.php"
    )

    params = {
        "ID": WU_STATION_ID,
        "PASSWORD": WU_STATION_KEY,
        "dateutc": "now",
        "action": "updateraw",
        **weather_data,
    }

    print()
    print("Weather Underground feltöltés...")

    response = requests.get(
        url,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    print(
        f"WU válasz: "
        f"{response.status_code} - "
        f"{response.text.strip()}"
    )

    if "success" not in response.text.lower():

        raise RuntimeError(
            "Weather Underground elutasította "
            f"a frissítést: {response.text}"
        )


def main():

    require_environment()

    raw_status, specification = get_tuya_data()

    weather_data = parse_sensor_data(
        raw_status,
        specification,
    )

    upload_to_wunderground(weather_data)

    print()
    print("SIKERES FUTTATÁS!")


if __name__ == "__main__":

    try:
        main()

    except Exception as exc:

        print(
            f"HIBA: {exc}",
            file=sys.stderr,
        )

        sys.exit(1)
