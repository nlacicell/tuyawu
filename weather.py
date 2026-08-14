import os
import sys
import json
import requests
import tinytuya


# ============================================================
# TUYA BEÁLLÍTÁSOK
# ============================================================

TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
TUYA_REGION = os.environ.get("TUYA_REGION", "eu")


# ============================================================
# WEATHER UNDERGROUND
# ============================================================

WU_STATION_ID = os.environ.get("WU_STATION_ID")
WU_STATION_KEY = os.environ.get("WU_STATION_KEY")


# ============================================================
# KÖRNYEZET ELLENŐRZÉSE
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
            "Hiányzó GitHub Secret: "
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
# HAGYOMÁNYOS TUYA STATUS
#
# Ez nálad jelenleg csak a beállításokat adja vissza.
# EZT NEM használjuk az időjárási méréshez.
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

    if not isinstance(response, dict):

        raise RuntimeError(
            f"Hibás Tuya válasz: {response!r}"
        )

    if response.get("success") is False:

        raise RuntimeError(
            f"Tuya hiba: "
            f"{response.get('code')} "
            f"{response.get('msg')}"
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

            if code:

                status[str(code)] = item.get(
                    "value"
                )

    print()
    print(
        f"Tuya státusz DP-k: {len(status)}"
    )

    print("-" * 60)

    for code, value in status.items():

        print(
            f"{code}: {value!r}"
        )

    print("-" * 60)

    return status


# ============================================================
# SHADOW PROPERTIES
#
# EZ A FONTOS LEKÉRDEZÉS!
#
# /v2.0/cloud/thing/{device_id}/shadow/properties
#
# A Tuya dokumentáció szerint itt vannak a készülék által
# a cloudba jelentett aktuális property-k.
# ============================================================

def get_shadow_properties(cloud):

    endpoint = (
        f"/v2.0/cloud/thing/"
        f"{TUYA_DEVICE_ID}/shadow/properties"
    )

    print()
    print("=" * 60)
    print("TUYA SHADOW PROPERTIES")
    print("=" * 60)

    print(
        f"Lekérés: {endpoint}"
    )

    try:

        response = cloud.cloudrequest(
            endpoint
        )

    except Exception as exc:

        raise RuntimeError(
            "A Shadow Properties lekérése "
            f"hibát adott: {exc}"
        )


    print()
    print("Tuya Shadow nyers válasz:")

    print(
        json.dumps(
            response,
            ensure_ascii=False,
            indent=2
        )
    )


    if not isinstance(response, dict):

        raise RuntimeError(
            "A Shadow válasz nem dictionary."
        )


    if response.get("success") is False:

        raise RuntimeError(
            f"Shadow API hiba: "
            f"{response.get('code')} "
            f"{response.get('msg')}"
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

            shadow[str(code)] = {
                "value": item.get("value"),
                "dp_id": item.get(
                    "dp_id",
                    item.get("dpId")
                ),
                "time": item.get(
                    "time"
                ),
                "custom_name": item.get(
                    "custom_name",
                    ""
                ),
            }


    print()
    print(
        f"Shadow property-k száma: "
        f"{len(shadow)}"
    )

    print("-" * 60)

    for code, data in shadow.items():

        print(
            f"{code}: "
            f"value={data['value']!r}, "
            f"dp={data['dp_id']!r}, "
            f"time={data['time']!r}, "
            f"name={data['custom_name']!r}"
        )

    print("-" * 60)

    return shadow


# ============================================================
# SZÁM KONVERTÁLÁSA
# ============================================================

def number(value):

    try:

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return None


# ============================================================
# UNIT_CONVERT DP-K KIZÁRÁSA
#
# Ezek NEM mérési adatok.
# ============================================================

def is_unit_setting(code):

    text = str(code).lower()

    forbidden = (
        "unit_convert",
        "unitconvert",
        "time_mode",
        "backlight",
    )

    for item in forbidden:

        if item in text:

            return True

    return False


# ============================================================
# PROPERTY KERESÉSE
# ============================================================

def find_property(
    shadow,
    exact_names,
    keywords
):

    # --------------------------------------------------------
    # 1. Pontos kód
    # --------------------------------------------------------

    for name in exact_names:

        if name in shadow:

            return name


    # --------------------------------------------------------
    # 2. Kulcsszavas keresés
    # --------------------------------------------------------

    candidates = []


    for code, data in shadow.items():

        if is_unit_setting(code):

            continue


        custom_name = str(
            data.get(
                "custom_name",
                ""
            )
        ).lower()


        text = (
            str(code).lower()
            + " "
            + custom_name
        )


        score = 0


        for keyword in keywords:

            if keyword in text:

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
        reverse=True
    )


    return candidates[0][1]


# ============================================================
# KÜLSŐ HŐMÉRSÉKLET KERESÉSE
#
# FONTOS:
# ELSŐDLEGESEN KÜLSŐ HŐMÉRSÉKLETET KERESÜNK.
# NEM az indoor_temperature-t.
# ============================================================

def find_outdoor_temperature(shadow):

    return find_property(
        shadow,

        (
            "outdoor_temperature",
            "outdoor_temp",
            "temperature_outdoor",
            "temp_outdoor",
            "va_temperature",
        ),

        (
            "outdoor_temperature",
            "outdoor_temp",
            "temperature_outdoor",
            "temp_outdoor",
            "outside_temperature",
            "outside_temp",
        )
    )


# ============================================================
# KÜLSŐ PÁRATARTALOM
# ============================================================

def find_outdoor_humidity(shadow):

    return find_property(
        shadow,

        (
            "outdoor_humidity",
            "humidity_outdoor",
            "hum_outdoor",
            "va_humidity",
        ),

        (
            "outdoor_humidity",
            "humidity_outdoor",
            "hum_outdoor",
            "outside_humidity",
        )
    )


# ============================================================
# LÉGNYOMÁS
# ============================================================

def find_pressure(shadow):

    return find_property(
        shadow,

        (
            "indoor_pressure",
            "pressure",
            "barometric_pressure",
            "pressure_value",
        ),

        (
            "pressure",
            "barometer",
            "barometric",
        )
    )


# ============================================================
# SZÉLSEBESSÉG
# ============================================================

def find_wind_speed(shadow):

    return find_property(
        shadow,

        (
            "wind_speed",
            "windspeed",
            "wind_speed_current",
        ),

        (
            "wind_speed",
            "windspeed",
        )
    )


# ============================================================
# SZÉLLÖKÉS
# ============================================================

def find_wind_gust(shadow):

    return find_property(
        shadow,

        (
            "wind_gust",
            "windgust",
            "gust_speed",
        ),

        (
            "wind_gust",
            "windgust",
            "gust",
        )
    )


# ============================================================
# CSAPADÉK
# ============================================================

def find_rain(shadow):

    return find_property(
        shadow,

        (
            "rainfall",
            "rain",
            "rain_amount",
            "precipitation",
        ),

        (
            "rainfall",
            "rain",
            "precipitation",
        )
    )


# ============================================================
# UV
# ============================================================

def find_uv(shadow):

    return find_property(
        shadow,

        (
            "uvi",
            "uv_index",
            "uv",
        ),

        (
            "uvi",
            "uv_index",
        )
    )


# ============================================================
# MÉRT ADATOK FELDOLGOZÁSA
# ============================================================


def find_relative_pressure_candidates(shadow):
    """Diagnosztika: relatív/tengerszinti nyomásra utaló property-k."""
    keywords = (
        "relative_pressure", "relativepressure", "pressure_relative",
        "relative_barometric", "sea_level_pressure", "sealevelpressure",
        "sea_level", "qnh", "rel_pressure"
    )
    results = []
    for code, data in shadow.items():
        t = (str(code).lower() + " " +
             str(data.get("custom_name", "")).lower())
        if any(k in t for k in keywords):
            results.append((code, data))
    return results


def print_light_diagnostics(shadow):
    """Diagnosztika a fény/napsugárzás/W/m² property-khez.
    A W/m² értéket egyelőre nem küldi a WU-ba."""
    keywords = (
        "light", "solar", "radiation", "irradiance",
        "w_m2", "wm2", "w/m2", "optical"
    )
    print()
    print("=" * 60)
    print("W/m² / FÉNY / NAPSUGÁRZÁS DIAGNOSZTIKA")
    print("=" * 60)
    found = False
    for code, data in shadow.items():
        t = (str(code).lower() + " " +
             str(data.get("custom_name", "")).lower())
        if any(k in t for k in keywords):
            found = True
            print(
                f"{code}: value={data.get('value')!r}, "
                f"dp={data.get('dp_id')!r}, "
                f"name={data.get('custom_name', '')!r}, "
                f"time={data.get('time')!r}"
            )
    if not found:
        print("Nem találtam fény/napsugárzás nevű property-t.")
    print("=" * 60)

def build_weather_data(shadow):

    print()
    print("=" * 60)
    print("IDŐJÁRÁSI ADATOK FELISMERÉSE")
    print("=" * 60)


    # --------------------------------------------------------
    # DP-k megkeresése
    # --------------------------------------------------------

    temp_code = find_outdoor_temperature(
        shadow
    )

    humidity_code = find_outdoor_humidity(
        shadow
    )

    pressure_code = find_pressure(
        shadow
    )

    # --------------------------------------------------------
    # RELATÍV / TENGERSZINTI NYOMÁS DIAGNOSZTIKA
    # --------------------------------------------------------
    relative_candidates = find_relative_pressure_candidates(shadow)

    print()
    print("=" * 60)
    print("RELATÍV / TENGERSZINTI NYOMÁS DIAGNOSZTIKA")
    print("=" * 60)

    if relative_candidates:
        for code, data in relative_candidates:
            print(
                f"{code}: value={data.get('value')!r}, "
                f"dp={data.get('dp_id')!r}, "
                f"name={data.get('custom_name', '')!r}, "
                f"time={data.get('time')!r}"
            )
    else:
        print(
            "Nincs név alapján azonosítható relative/QNH/"
            "sea-level pressure property."
        )

    print("=" * 60)

    wind_code = find_wind_speed(
        shadow
    )

    gust_code = find_wind_gust(
        shadow
    )

    rain_code = find_rain(
        shadow
    )

    uv_code = find_uv(
        shadow
    )


    print(
        f"Külső hőmérséklet DP: "
        f"{temp_code or 'NINCS'}"
    )

    print(
        f"Külső páratartalom DP: "
        f"{humidity_code or 'NINCS'}"
    )

    print(
        f"Légnyomás jelenlegi DP: "
        f"{pressure_code or 'NINCS'}"
    )

    print(
        f"Szélsebesség DP: "
        f"{wind_code or 'NINCS'}"
    )

    print(
        f"Széllökés DP: "
        f"{gust_code or 'NINCS'}"
    )

    print(
        f"Csapadék DP: "
        f"{rain_code or 'NINCS'}"
    )

    print(
        f"UV DP: "
        f"{uv_code or 'NINCS'}"
    )


    payload = {}


    # ========================================================
    # KÜLSŐ HŐMÉRSÉKLET
    # ========================================================

    if temp_code:

        raw = number(
            shadow[temp_code]["value"]
        )

        if raw is not None:

            # A Tuya időjárásállomásoknál a
            # tizedfokos érték:
            #
            # 308 -> 30.8 °C

            temp_c = raw / 10.0


            print()
            print(
                f"KÜLSŐ HŐMÉRSÉKLET: "
                f"{raw} -> "
                f"{temp_c:.1f} °C"
            )


            if -60 <= temp_c <= 70:

                temp_f = (
                    temp_c * 9.0 / 5.0
                    + 32.0
                )

                payload["tempf"] = (
                    f"{temp_f:.1f}"
                )


    # ========================================================
    # KÜLSŐ PÁRATARTALOM
    # ========================================================

    if humidity_code:

        raw = number(
            shadow[humidity_code]["value"]
        )

        if raw is not None:

            humidity = raw


            print()
            print(
                f"KÜLSŐ PÁRATARTALOM: "
                f"{humidity:.0f} %"
            )


            if 0 <= humidity <= 100:

                payload["humidity"] = str(
                    int(
                        round(
                            humidity
                        )
                    )
                )


    # ========================================================
    # LÉGNYOMÁS
    # ========================================================

    if pressure_code:

        raw = number(
            shadow[pressure_code]["value"]
        )

        if raw is not None:

            # Példa:
            #
            # 100120 -> 1001.20 hPa

            pressure_hpa = raw / 100.0


            print()
            print(
                f"LÉGNYOMÁS: "
                f"{raw} -> "
                f"{pressure_hpa:.2f} hPa"
            )


            if 850 <= pressure_hpa <= 1100:

                # hPa -> inch Hg

                pressure_inhg = (
                    pressure_hpa
                    * 0.0295299830714
                )

                payload["baromin"] = (
                    f"{pressure_inhg:.3f}"
                )


    # ========================================================
    # SZÉLSEBESSÉG
    # ========================================================

    if wind_code:

        raw = number(
            shadow[wind_code]["value"]
        )

        if raw is not None:

            # A készülék beállítása:
            #
            # windspeed_unit_convert = kmph
            #
            # A mért érték tizedes km/h.

            kmh = raw / 10.0

            mph = (
                kmh
                * 0.621371192
            )


            print()
            print(
                f"SZÉLSEBESSÉG: "
                f"{raw} -> "
                f"{kmh:.1f} km/h -> "
                f"{mph:.1f} mph"
            )


            if 0 <= mph <= 200:

                payload[
                    "windspeedmph"
                ] = f"{mph:.1f}"


    # ========================================================
    # SZÉLLÖKÉS
    # ========================================================

    if gust_code:

        raw = number(
            shadow[gust_code]["value"]
        )

        if raw is not None:

            kmh = raw / 10.0

            mph = (
                kmh
                * 0.621371192
            )


            print()
            print(
                f"SZÉLLÖKÉS: "
                f"{raw} -> "
                f"{kmh:.1f} km/h -> "
                f"{mph:.1f} mph"
            )


            if 0 <= mph <= 250:

                payload[
                    "windgustmph"
                ] = f"{mph:.1f}"


    # ========================================================
    # CSAPADÉK
    # ========================================================

    if rain_code:

        raw = number(
            shadow[rain_code]["value"]
        )

        if raw is not None:

            # mm / 10

            rain_mm = raw / 10.0

            rain_inch = (
                rain_mm / 25.4
            )


            print()
            print(
                f"CSAPADÉK: "
                f"{raw} -> "
                f"{rain_mm:.1f} mm -> "
                f"{rain_inch:.3f} inch"
            )


            if 0 <= rain_inch <= 100:

                payload["rainin"] = (
                    f"{rain_inch:.3f}"
                )


    # ========================================================
    # UV
    # ========================================================

    if uv_code:

        raw = number(
            shadow[uv_code]["value"]
        )

        if raw is not None:

            print()
            print(
                f"UV INDEX: {raw}"
            )

            if 0 <= raw <= 20:

                payload["UV"] = (
                    f"{raw:.1f}"
                )


    # ========================================================
    # W/m² DIAGNOSZTIKA
    # ========================================================
    print_light_diagnostics(shadow)

    # ========================================================
    # EREDMÉNY
    # ========================================================

    print()
    print("=" * 60)
    print("WEATHER UNDERGROUND PAYLOAD")
    print("=" * 60)


    if payload:

        for key, value in payload.items():

            print(
                f"{key} = {value}"
            )

    else:

        print(
            "NINCS FELISMERT MÉRT ADAT!"
        )


    print("=" * 60)


    return payload


# ============================================================
# WEATHER UNDERGROUND FELTÖLTÉS
# ============================================================

def upload_to_wu(payload):

    if not payload:

        raise RuntimeError(
            "Nincs feltölthető időjárási adat."
        )


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
    print("=" * 60)
    print(
        "WEATHER UNDERGROUND FELTÖLTÉS"
    )
    print("=" * 60)


    response = requests.get(
        url,
        params=params,
        timeout=30
    )


    response.raise_for_status()


    print(
        f"HTTP státusz: "
        f"{response.status_code}"
    )

    print(
        f"WU válasz: "
        f"{response.text.strip()}"
    )

    print("=" * 60)


# ============================================================
# FŐPROGRAM
# ============================================================

def main():

    check_environment()


    # --------------------------------------------------------
    # Tuya Cloud
    # --------------------------------------------------------

    cloud = create_cloud()


    # --------------------------------------------------------
    # Ez csak diagnosztika.
    #
    # Nálad várhatóan itt továbbra is csak a 6
    # unit/time/backlight adat jelenik meg.
    # --------------------------------------------------------

    get_status(
        cloud
    )


    # --------------------------------------------------------
    # VALÓDI MÉRT ADATOK
    #
    # INNEN KELL JÖNNIÜK!
    # --------------------------------------------------------

    shadow = get_shadow_properties(
        cloud
    )


    if not shadow:

        raise RuntimeError(
            "A Tuya Shadow Properties üres. "
            "A készülék nem jelentett mért "
            "adatot a Tuya Cloud felé."
        )


    # --------------------------------------------------------
    # Időjárási adatok
    # --------------------------------------------------------

    payload = build_weather_data(
        shadow
    )


    # --------------------------------------------------------
    # Feltöltés
    # --------------------------------------------------------

    if payload:

        upload_to_wu(
            payload
        )

    else:

        raise RuntimeError(
            "Nem sikerült időjárási adatot "
            "felismerni a Tuya Shadowból."
        )


    print()
    print("=" * 60)
    print("SIKERES FUTÁS")
    print("=" * 60)


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
