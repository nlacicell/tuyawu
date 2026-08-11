import json
import math
import os
import sys

import requests
import tinytuya


# ============================================================
# KÖRNYEZETI VÁLTOZÓK / GITHUB SECRETS
# ============================================================

TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")

TUYA_REGION = os.environ.get("TUYA_REGION", "eu")

WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")


# ============================================================
# OPCIONÁLIS KÉZI DP-KÓDOK
#
# Ezeket egyelőre NEM kell beállítanod.
# Ha a diagnosztikai futásból megtudjuk a pontos kódokat,
# akkor később megadhatjuk őket GitHub Secretként.
# ============================================================

TUYA_TEMP_CODE = os.environ.get("TUYA_TEMP_CODE")
TUYA_HUMIDITY_CODE = os.environ.get("TUYA_HUMIDITY_CODE")
TUYA_PRESSURE_CODE = os.environ.get("TUYA_PRESSURE_CODE")
TUYA_WIND_SPEED_CODE = os.environ.get("TUYA_WIND_SPEED_CODE")
TUYA_WIND_GUST_CODE = os.environ.get("TUYA_WIND_GUST_CODE")
TUYA_WIND_DIRECTION_CODE = os.environ.get("TUYA_WIND_DIRECTION_CODE")
TUYA_RAIN_CODE = os.environ.get("TUYA_RAIN_CODE")


# ============================================================
# KÖTELEZŐ ADATOK ELLENŐRZÉSE
# ============================================================

def check_environment():

    required = {
        "TUYA_ACCESS_ID": TUYA_ACCESS_ID,
        "TUYA_ACCESS_SECRET": TUYA_ACCESS_SECRET,
        "TUYA_DEVICE_ID": TUYA_DEVICE_ID,
        "WU_STATION_ID": WU_STATION_ID,
        "WU_STATION_KEY": WU_STATION_KEY,
    }

    missing = []

    for name, value in required.items():

        if not value:
            missing.append(name)

    if missing:

        raise RuntimeError(
            "Hiányzó GitHub Secret/környezeti változó: "
            + ", ".join(missing)
        )


# ============================================================
# TUYA CLOUD
# ============================================================

def create_cloud():

    print(
        f"Tuya Cloud régió: {TUYA_REGION}"
    )

    return tinytuya.Cloud(
        apiRegion=TUYA_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
    )


# ============================================================
# TUYA VÁLASZ ELLENŐRZÉSE
# ============================================================

def check_tuya_response(response, endpoint):

    if not isinstance(response, dict):

        raise RuntimeError(
            f"Érvénytelen Tuya válasz ({endpoint}): "
            f"{response!r}"
        )

    if "Error" in response:

        raise RuntimeError(
            f"TinyTuya hiba ({endpoint}): "
            f"Error={response.get('Error')!r}, "
            f"Err={response.get('Err')!r}"
        )

    if response.get("success") is False:

        raise RuntimeError(
            f"Tuya API hiba ({endpoint}): "
            f"code={response.get('code')!r}, "
            f"msg={response.get('msg')!r}"
        )

    return response


# ============================================================
# TUYA STATUS
# ============================================================

def get_status(cloud):

    endpoint = (
        f"/v1.0/iot-03/devices/"
        f"{TUYA_DEVICE_ID}/status"
    )

    print()
    print(
        f"Tuya státusz lekérése: {endpoint}"
    )

    response = cloud.getstatus(
        TUYA_DEVICE_ID
    )

    response = check_tuya_response(
        response,
        endpoint
    )

    result = response.get(
        "result",
        []
    )

    status = {}

    if isinstance(result, list):

        for item in result:

            if not isinstance(item, dict):
                continue

            code = item.get("code")

            if not code:
                continue

            status[str(code)] = item.get("value")

    print()
    print(
        f"Tuya státusz DP-k: {len(status)} db"
    )

    print("----------------------------------------")

    for code, value in status.items():

        print(
            f"{code}: {value!r}"
        )

    print("----------------------------------------")

    return status


# ============================================================
# TUYA SHADOW PROPERTIES
#
# Ez a fontos rész.
#
# A Tuya dokumentáció szerint:
#
# GET
# /v2.0/cloud/thing/{device_id}/shadow/properties
#
# a cloudban tárolt property-ket adja vissza.
# ============================================================

def get_shadow_properties(cloud):

    endpoint = (
        f"/v2.0/cloud/thing/"
        f"{TUYA_DEVICE_ID}/shadow/properties"
    )

    print()
    print(
        f"Tuya Shadow lekérése: {endpoint}"
    )

    response = cloud.cloudrequest(
        endpoint
    )

    print()
    print("Teljes Shadow válasz:")
    print("----------------------------------------")

    print(
        json.dumps(
            response,
            ensure_ascii=False,
            indent=2
        )
    )

    print("----------------------------------------")

    response = check_tuya_response(
        response,
        endpoint
    )

    result = response.get(
        "result",
        {}
    )

    properties = []

    if isinstance(result, dict):

        properties = result.get(
            "properties",
            []
        )

    shadow = {}

    if isinstance(properties, list):

        for item in properties:

            if not isinstance(item, dict):
                continue

            code = item.get("code")

            if not code:
                continue

            code = str(code)

            shadow[code] = {
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

    print()
    print(
        f"Shadow property-k: {len(shadow)} db"
    )

    print("----------------------------------------")

    for code, item in shadow.items():

        print(
            f"{code}: "
            f"value={item['value']!r}, "
            f"dp_id={item['dp_id']!r}, "
            f"time={item['time']!r}, "
            f"name={item['custom_name']!r}"
        )

    print("----------------------------------------")

    return shadow


# ============================================================
# TUYA DEVICE PROPERTIES / SPECIFICATION
# ============================================================

def get_device_properties(cloud):

    print()
    print(
        "Tuya device properties lekérése..."
    )

    try:

        response = cloud.getproperties(
            TUYA_DEVICE_ID
        )

    except Exception as exc:

        print(
            "A getproperties() hívás hibát adott:"
        )

        print(exc)

        return {}


    if not isinstance(response, dict):

        return {}

    if response.get("success") is False:

        print(
            "A Tuya getproperties sikertelen:"
        )

        print(response)

        return {}

    result = response.get(
        "result",
        []
    )

    specification = {}

    # Egyes TinyTuya/Tuya válaszok listaként adják.

    if isinstance(result, list):

        for item in result:

            if not isinstance(item, dict):
                continue

            code = item.get("code")

            if not code:
                continue

            values = item.get(
                "values",
                {}
            )

            if isinstance(values, str):

                try:
                    values = json.loads(values)

                except Exception:
                    values = {}

            if not isinstance(values, dict):

                values = {}

            specification[str(code)] = {
                "name": item.get(
                    "name",
                    item.get("desc", "")
                ),
                "type": item.get(
                    "type",
                    ""
                ),
                "unit": values.get(
                    "unit",
                    ""
                ),
                "scale": values.get(
                    "scale",
                    0
                ),
                "step": values.get(
                    "step",
                    1
                ),
                "min": values.get(
                    "min"
                ),
                "max": values.get(
                    "max"
                ),
            }

    # Más formátum esetén dictionary.

    elif isinstance(result, dict):

        statuses = result.get(
            "status",
            []
        )

        if isinstance(statuses, list):

            for item in statuses:

                if not isinstance(item, dict):
                    continue

                code = item.get("code")

                if not code:
                    continue

                values = item.get(
                    "values",
                    {}
                )

                if isinstance(values, str):

                    try:
                        values = json.loads(values)

                    except Exception:
                        values = {}

                if not isinstance(values, dict):

                    values = {}

                specification[str(code)] = {
                    "name": item.get(
                        "name",
                        item.get("desc", "")
                    ),
                    "type": item.get(
                        "type",
                        ""
                    ),
                    "unit": values.get(
                        "unit",
                        ""
                    ),
                    "scale": values.get(
                        "scale",
                        0
                    ),
                    "step": values.get(
                        "step",
                        1
                    ),
                    "min": values.get(
                        "min"
                    ),
                    "max": values.get(
                        "max"
                    ),
                }

    print()
    print(
        f"Tuya specifikációs DP-k: "
        f"{len(specification)} db"
    )

    return specification


# ============================================================
# SEGÉDFÜGGVÉNYEK
# ============================================================

def normalize_text(value):

    if value is None:
        return ""

    return str(value).lower().strip()


def number(value):

    if isinstance(value, bool):

        return None

    try:

        result = float(value)

    except (
        TypeError,
        ValueError
    ):

        return None

    if not math.isfinite(result):

        return None

    return result


def get_scale(meta):

    if not meta:
        return 0

    try:

        return int(
            meta.get(
                "scale",
                0
            ) or 0
        )

    except (
        TypeError,
        ValueError
    ):

        return 0


def apply_scale(value, meta):

    value = number(value)

    if value is None:
        return None

    scale = get_scale(meta)

    return value / (
        10 ** scale
    )


def get_unit(meta):

    if not meta:
        return ""

    return normalize_text(
        meta.get(
            "unit",
            ""
        )
    )


# ============================================================
# DP KERESÉS
# ============================================================

def find_property(
    shadow,
    specification,
    manual_code,
    exact_codes,
    keywords
):

    # 1. Kézi megadás elsőbbséget élvez.

    if manual_code:

        if manual_code in shadow:

            return manual_code

        print(
            f"FIGYELEM: a megadott DP "
            f"({manual_code}) nincs a Shadowban."
        )

        return None


    # 2. Pontosan ismert kódok.

    for code in exact_codes:

        if code in shadow:

            return code


    # 3. Név / kód alapján keresés.

    candidates = []

    for code, item in shadow.items():

        meta = specification.get(
            code,
            {}
        )

        custom_name = normalize_text(
            item.get(
                "custom_name",
                ""
            )
        )

        spec_name = normalize_text(
            meta.get(
                "name",
                ""
            )
        )

        code_text = normalize_text(
            code
        )

        # FONTOS:
        # A unit_convert DP-ket kizárjuk.
        #
        # Ezek csak a kijelző egységét állítják,
        # nem mérési adatok.

        combined = " ".join(
            (
                code_text,
                custom_name,
                spec_name
            )
        )

        if (
            "unit_convert" in combined
            or "unitconvert" in combined
            or "_unit_" in combined
        ):

            continue

        score = 0

        for keyword in keywords:

            if keyword in combined:

                score += 1

        if score > 0:

            candidates.append(
                (
                    score,
                    code
                )
            )

    if not candidates:

        return None

    candidates.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return candidates[0][1]


# ============================================================
# HŐMÉRSÉKLET
# ============================================================

def temperature_celsius(
    value,
    meta
):

    value = apply_scale(
        value,
        meta
    )

    if value is None:
        return None

    unit = get_unit(meta)

    if unit in (
        "f",
        "°f",
        "fahrenheit"
    ):

        return (
            value - 32
        ) * 5 / 9

    if unit in (
        "k",
        "kelvin"
    ):

        return (
            value - 273.15
        )

    return value


# ============================================================
# PÁRATARTALOM
# ============================================================

def humidity_percent(
    value,
    meta
):

    value = apply_scale(
        value,
        meta
    )

    if value is None:
        return None

    return value


# ============================================================
# LÉGNYOMÁS
# ============================================================

def pressure_hpa(
    value,
    meta
):

    value = apply_scale(
        value,
        meta
    )

    if value is None:
        return None

    unit = get_unit(meta)

    if unit in (
        "pa",
        "pascal",
        "pascals"
    ):

        return value / 100


    if unit in (
        "kpa",
    ):

        return value * 10


    if unit in (
        "inhg",
        "in hg"
    ):

        return value * 33.8638867


    if unit in (
        "mmhg",
        "mm hg"
    ):

        return value * 1.33322387


    # Ha a Tuya nem ad egységet,
    # nagyságrend alapján próbáljuk eldönteni.

    if value > 20000:

        return value / 100


    if value > 2000:

        return value / 100


    return value


# ============================================================
# SZÉLSEBESSÉG
# ============================================================

def wind_mph(
    value,
    meta
):

    value = apply_scale(
        value,
        meta
    )

    if value is None:
        return None

    unit = get_unit(meta)

    if unit in (
        "m/s",
        "mps",
        "ms",
        "meter per second",
        "meters per second"
    ):

        return value * 2.2369363


    if unit in (
        "km/h",
        "kmh",
        "kph",
        "kmph",
        "kilometer per hour",
        "kilometers per hour"
    ):

        return value * 0.6213712


    if unit in (
        "mph",
        "mi/h"
    ):

        return value


    if unit in (
        "knot",
        "knots",
        "kt",
        "kts"
    ):

        return value * 1.1507794


    # Ha nincs egység,
    # időjárásállomásoknál gyakori az m/s.

    return value * 2.2369363


# ============================================================
# SZÉLIRÁNY
# ============================================================

def wind_direction(
    value,
    meta
):

    value = apply_scale(
        value,
        meta
    )

    if value is None:
        return None

    return value % 360


# ============================================================
# CSAPADÉK
# ============================================================

def rain_inches(
    value,
    meta
):

    value = apply_scale(
        value,
        meta
    )

    if value is None:
        return None

    unit = get_unit(meta)

    if unit in (
        "mm",
        "millimeter",
        "millimeters"
    ):

        return value / 25.4


    if unit in (
        "cm",
        "centimeter",
        "centimeters"
    ):

        return value / 2.54


    if unit in (
        "in",
        "inch",
        "inches"
    ):

        return value


    return value / 25.4


# ============================================================
# IDŐJÁRÁSI ADATOK FELISMERÉSE
# ============================================================

def parse_weather_data(
    shadow,
    specification
):

    print()
    print(
        "========================================"
    )
    print(
        "IDŐJÁRÁSI ADATOK FELISMERÉSE"
    )
    print(
        "========================================"
    )


    temperature_code = find_property(
        shadow,
        specification,
        TUYA_TEMP_CODE,

        (
            "va_temperature",
            "temperature",
            "temp_current",
            "outdoor_temp",
            "temp"
        ),

        (
            "temperature",
            "temp"
        )
    )


    humidity_code = find_property(
        shadow,
        specification,
        TUYA_HUMIDITY_CODE,

        (
            "va_humidity",
            "humidity",
            "outdoor_humidity",
            "hum"
        ),

        (
            "humidity",
            "humid"
        )
    )


    pressure_code = find_property(
        shadow,
        specification,
        TUYA_PRESSURE_CODE,

        (
            "va_pressure",
            "pressure",
            "barometer",
            "barometric_pressure"
        ),

        (
            "pressure",
            "barometer"
        )
    )


    wind_speed_code = find_property(
        shadow,
        specification,
        TUYA_WIND_SPEED_CODE,

        (
            "wind_speed",
            "windspeed",
            "wind_speed_current"
        ),

        (
            "wind_speed",
            "windspeed",
            "wind velocity"
        )
    )


    wind_gust_code = find_property(
        shadow,
        specification,
        TUYA_WIND_GUST_CODE,

        (
            "wind_gust",
            "windgust",
            "gust_speed"
        ),

        (
            "wind_gust",
            "windgust",
            "gust"
        )
    )


    wind_direction_code = find_property(
        shadow,
        specification,
        TUYA_WIND_DIRECTION_CODE,

        (
            "wind_direction",
            "winddirection",
            "wind_dir"
        ),

        (
            "wind_direction",
            "winddirection",
            "wind_dir"
        )
    )


    rain_code = find_property(
        shadow,
        specification,
        TUYA_RAIN_CODE,

        (
            "rain",
            "rainfall",
            "rain_amount",
            "precipitation"
        ),

        (
            "rain",
            "rainfall",
            "precipitation"
        )
    )


    print(
        f"Hőmérséklet DP:  "
        f"{temperature_code or 'NINCS'}"
    )

    print(
        f"Páratartalom DP: "
        f"{humidity_code or 'NINCS'}"
    )

    print(
        f"Légnyomás DP:    "
        f"{pressure_code or 'NINCS'}"
    )

    print(
        f"Szélsebesség DP: "
        f"{wind_speed_code or 'NINCS'}"
    )

    print(
        f"Széllökés DP:    "
        f"{wind_gust_code or 'NINCS'}"
    )

    print(
        f"Szélirány DP:    "
        f"{wind_direction_code or 'NINCS'}"
    )

    print(
        f"Csapadék DP:     "
        f"{rain_code or 'NINCS'}"
    )


    # ========================================================
    # WEATHER UNDERGROUND PAYLOAD
    # ========================================================

    payload = {
        "software": "TuyaWeatherBridge/4.0"
    }


    # --------------------------------------------------------
    # HŐMÉRSÉKLET
    # --------------------------------------------------------

    if temperature_code:

        item = shadow[
            temperature_code
        ]

        value = item.get(
            "value"
        )

        meta = specification.get(
            temperature_code,
            {}
        )

        temp_c = temperature_celsius(
            value,
            meta
        )

        print()
        print(
            f"Hőmérséklet: "
            f"raw={value!r}, "
            f"unit={get_unit(meta)!r}, "
            f"scale={get_scale(meta)}, "
            f"-> {temp_c!r} °C"
        )

        if (
            temp_c is not None
            and -80 <= temp_c <= 80
        ):

            temp_f = (
                temp_c * 9 / 5
            ) + 32

            payload["tempf"] = (
                f"{temp_f:.1f}"
            )


    # --------------------------------------------------------
    # PÁRATARTALOM
    # --------------------------------------------------------

    if humidity_code:

        item = shadow[
            humidity_code
        ]

        value = item.get(
            "value"
        )

        meta = specification.get(
            humidity_code,
            {}
        )

        humidity = humidity_percent(
            value,
            meta
        )

        print()
        print(
            f"Páratartalom: "
            f"raw={value!r}, "
            f"scale={get_scale(meta)}, "
            f"-> {humidity!r} %"
        )

        if (
            humidity is not None
            and 0 <= humidity <= 100
        ):

            payload["humidity"] = str(
                int(round(humidity))
            )


    # --------------------------------------------------------
    # LÉGNYOMÁS
    # --------------------------------------------------------

    if pressure_code:

        item = shadow[
            pressure_code
        ]

        value = item.get(
            "value"
        )

        meta = specification.get(
            pressure_code,
            {}
        )

        pressure = pressure_hpa(
            value,
            meta
        )

        print()
        print(
            f"Légnyomás: "
            f"raw={value!r}, "
            f"unit={get_unit(meta)!r}, "
            f"scale={get_scale(meta)}, "
            f"-> {pressure!r} hPa"
        )

        if (
            pressure is not None
            and 800 <= pressure <= 1200
        ):

            # Weather Underground barom mező:
            # inch Hg

            pressure_inhg = (
                pressure * 0.0295299831
            )

            payload["baromin"] = (
                f"{pressure_inhg:.3f}"
            )


    # --------------------------------------------------------
    # SZÉLSEBESSÉG
    # --------------------------------------------------------

    if wind_speed_code:

        item = shadow[
            wind_speed_code
        ]

        value = item.get(
            "value"
        )

        meta = specification.get(
            wind_speed_code,
            {}
        )

        speed = wind_mph(
            value,
            meta
        )

        print()
        print(
            f"Szélsebesség: "
            f"raw={value!r}, "
            f"unit={get_unit(meta)!r}, "
            f"scale={get_scale(meta)}, "
            f"-> {speed!r} mph"
        )

        if (
            speed is not None
            and 0 <= speed <= 200
        ):

            payload[
                "windspeedmph"
            ] = f"{speed:.1f}"


    # --------------------------------------------------------
    # SZÉLLÖKÉS
    # --------------------------------------------------------

    if wind_gust_code:

        item = shadow[
            wind_gust_code
        ]

        value = item.get(
            "value"
        )

        meta = specification.get(
            wind_gust_code,
            {}
        )

        gust = wind_mph(
            value,
            meta
        )

        print()
        print(
            f"Széllökés: "
            f"raw={value!r}, "
            f"unit={get_unit(meta)!r}, "
            f"scale={get_scale(meta)}, "
            f"-> {gust!r} mph"
        )

        if (
            gust is not None
            and 0 <= gust <= 250
        ):

            payload[
                "windgustmph"
            ] = f"{gust:.1f}"


    # --------------------------------------------------------
    # SZÉLIRÁNY
    # --------------------------------------------------------

    if wind_direction_code:

        item = shadow[
            wind_direction_code
        ]

        value = item.get(
            "value"
        )

        meta = specification.get(
            wind_direction_code,
            {}
        )

        direction = wind_direction(
            value,
            meta
        )

        print()
        print(
            f"Szélirány: "
            f"raw={value!r}, "
            f"scale={get_scale(meta)}, "
            f"-> {direction!r} fok"
        )

        if (
            direction is not None
            and 0 <= direction <= 360
        ):

            payload["winddir"] = str(
                int(round(direction)) % 360
            )


    # --------------------------------------------------------
    # CSAPADÉK
    # --------------------------------------------------------

    if rain_code:

        item = shadow[
            rain_code
        ]

        value = item.get(
            "value"
        )

        meta = specification.get(
            rain_code,
            {}
        )

        rain = rain_inches(
            value,
            meta
        )

        print()
        print(
            f"Csapadék: "
            f"raw={value!r}, "
            f"unit={get_unit(meta)!r}, "
            f"scale={get_scale(meta)}, "
            f"-> {rain!r} inch"
        )

        if (
            rain is not None
            and 0 <= rain <= 100
        ):

            payload["rainin"] = (
                f"{rain:.3f}"
            )


    # ========================================================
    # EREDMÉNY
    # ========================================================

    print()
    print(
        "========================================"
    )
    print(
        "WEATHER UNDERGROUND ADATOK"
    )
    print(
        "========================================"
    )

    for key, value in payload.items():

        print(
            f"{key} = {value}"
        )

    print(
        "========================================"
    )


    # Diagnosztikai futásnál most ne állítsuk le
    # a programot csak azért, mert még nem tudjuk
    # a megfelelő DP-kódokat.
    #
    # Ha egyik valódi időjárási adatot sem találtuk,
    # akkor csak figyelmeztetünk.

    weather_fields = (
        "tempf",
        "humidity",
        "baromin",
        "windspeedmph",
        "windgustmph",
        "winddir",
        "rainin",
    )

    found = [
        key
        for key in weather_fields
        if key in payload
    ]

    if not found:

        print()
        print(
            "FIGYELEM: egyelőre egyetlen "
            "időjárási mérési adatot sem "
            "sikerült automatikusan felismerni."
        )

        print(
            "A Shadowban kiírt DP-k alapján "
            "be tudjuk állítani a pontos "
            "kódokat."
        )

    return payload


# ============================================================
# WEATHER UNDERGROUND FELTÖLTÉS
# ============================================================

def upload_weather_underground(
    payload
):

    url = (
        "https://weatherstation.wunderground.com/"
        "weatherstation/updateweatherstation.php"
    )

    params = {
        "ID": WU_STATION_ID,
        "PASSWORD": WU_STATION_KEY,
        "dateutc": "now",
        "action": "updateraw",
    }

    params.update(
        payload
    )

    print()
    print(
        "Weather Underground feltöltés..."
    )

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    text = response.text.strip()

    print(
        f"WU HTTP státusz: "
        f"{response.status_code}"
    )

    print(
        f"WU válasz: {text}"
    )

    if (
        response.status_code != 200
    ):

        raise RuntimeError(
            "Weather Underground HTTP "
            "hibát adott."
        )

    if (
        "success" not in text.lower()
        and "ok" not in text.lower()
    ):

        print(
            "FIGYELEM: a Weather Underground "
            "válasza nem tartalmazta a "
            "'success' vagy 'ok' szót."
        )


# ============================================================
# FŐPROGRAM
# ============================================================

def main():

    check_environment()

    cloud = create_cloud()

    # --------------------------------------------------------
    # 1. Normál Tuya status
    # --------------------------------------------------------

    status = get_status(
        cloud
    )


    # --------------------------------------------------------
    # 2. Cloud Shadow Properties
    #
    # EZT HASZNÁLJUK A VALÓDI MÉRÉSEKHEZ.
    # --------------------------------------------------------

    shadow = get_shadow_properties(
        cloud
    )


    # --------------------------------------------------------
    # 3. Specification / metaadatok
    # --------------------------------------------------------

    specification = get_device_properties(
        cloud
    )


    # --------------------------------------------------------
    # 4. Ha nincs Shadow adat,
    #    a normál statusból is készítünk
    #    egy minimális struktúrát.
    #
    # DE:
    # unit_convert mezőket nem fogjuk
    # mérési adatként használni.
    # --------------------------------------------------------

    if not shadow:

        print()
        print(
            "FIGYELEM: a Shadow nem adott "
            "property-ket."
        )

        print(
            "A normál status adatait "
            "diagnosztikai célból megőrizzük."
        )

        for code, value in status.items():

            shadow[code] = {
                "value": value,
                "dp_id": None,
                "time": None,
                "custom_name": "",
            }


    # --------------------------------------------------------
    # 5. Időjárási adatok felismerése
    # --------------------------------------------------------

    weather_payload = parse_weather_data(
        shadow,
        specification
    )


    # --------------------------------------------------------
    # 6. Feltöltés csak akkor,
    #    ha legalább egy valódi mérési adat van.
    # --------------------------------------------------------

    weather_fields = (
        "tempf",
        "humidity",
        "baromin",
        "windspeedmph",
        "windgustmph",
        "winddir",
        "rainin",
    )

    found = [
        key
        for key in weather_fields
        if key in weather_payload
    ]

    if found:

        upload_weather_underground(
            weather_payload
        )

        print()
        print(
            "========================================"
        )
        print(
            "SIKERES FUTTATÁS"
        )
        print(
            "========================================"
        )

    else:

        print()
        print(
            "Nincs feltöltés, mert még nincs "
            "felismert időjárási mérési adat."
        )

        print(
            "Ez most szándékos: előbb meg kell "
            "találnunk a készülék tényleges DP-kódjait."
        )

        # Diagnosztikai célból sikeresen kilépünk,
        # hogy az Actions log teljes egészében
        # látható legyen.

        return


# ============================================================
# INDÍTÁS
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as exc:

        print(
            f"HIBA: {exc}",
            file=sys.stderr
        )

        sys.exit(1)
