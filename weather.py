import os
import sys
import requests
import tinytuya


# ============================================================
# TUYA
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
# A TE IDŐJÁRÁSÁLLOMÁSOD TUYA DP-KÓDJAI
# ============================================================

OUTDOOR_TEMPERATURE = "outdoor_temperature"
OUTDOOR_HUMIDITY = "outdoor_humidity"

INDOOR_TEMPERATURE = "indoor_temperature"
INDOOR_HUMIDITY = "indoor_humidity"

PRESSURE = "indoor_pressure"

WIND_SPEED = "wind_speed"
WIND_GUST = "wind_gust"

RAIN = "rainfall"

UV_INDEX = "uvi"
LIGHT_INTENSITY = "light_intensity"


# ============================================================
# KÖRNYEZETI VÁLTOZÓK ELLENŐRZÉSE
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

def create_tuya_cloud():

    print(
        f"Tuya régió: {TUYA_REGION}"
    )

    return tinytuya.Cloud(
        apiRegion=TUYA_REGION,
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
    )


# ============================================================
# TUYA STATUS LEKÉRÉSE
# ============================================================

def get_tuya_status(cloud):

    print()
    print("=" * 60)
    print("TUYA ADATOK LEKÉRÉSE")
    print("=" * 60)

    print(
        "Tuya státusz lekérése..."
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
            "Tuya API hiba: "
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
        f"Tuya DP-k száma: {len(status)}"
    )

    print("-" * 60)

    for code, value in status.items():

        print(
            f"{code}: {value!r}"
        )

    print("-" * 60)

    return status


# ============================================================
# ÉRTÉK ÁTALAKÍTÁSA SZÁMMÁ
# ============================================================

def to_float(value):

    try:

        return float(value)

    except (
        TypeError,
        ValueError
    ):

        return None


# ============================================================
# KÜLSŐ HŐMÉRSÉKLET
# ============================================================

def get_outdoor_temperature(status):

    if OUTDOOR_TEMPERATURE not in status:

        print(
            "FIGYELEM: nincs "
            "outdoor_temperature DP!"
        )

        return None

    raw = to_float(
        status[
            OUTDOOR_TEMPERATURE
        ]
    )

    if raw is None:

        return None

    # A készülék 0,1 °C felbontásban adja.
    temperature_c = raw / 10.0

    print(
        f"KÜLSŐ HŐMÉRSÉKLET: "
        f"{raw} -> "
        f"{temperature_c:.1f} °C"
    )

    if not -60 <= temperature_c <= 70:

        print(
            "FIGYELEM: a külső "
            "hőmérséklet értéke "
            "életszerűtlen."
        )

        return None

    return temperature_c


# ============================================================
# BELSŐ HŐMÉRSÉKLET
# ============================================================

def get_indoor_temperature(status):

    if INDOOR_TEMPERATURE not in status:

        return None

    raw = to_float(
        status[
            INDOOR_TEMPERATURE
        ]
    )

    if raw is None:

        return None

    temperature_c = raw / 10.0

    print(
        f"BELSŐ HŐMÉRSÉKLET: "
        f"{raw} -> "
        f"{temperature_c:.1f} °C"
    )

    if not -60 <= temperature_c <= 70:

        return None

    return temperature_c


# ============================================================
# KÜLSŐ PÁRATARTALOM
# ============================================================

def get_outdoor_humidity(status):

    if OUTDOOR_HUMIDITY not in status:

        print(
            "FIGYELEM: nincs "
            "outdoor_humidity DP!"
        )

        return None

    humidity = to_float(
        status[
            OUTDOOR_HUMIDITY
        ]
    )

    if humidity is None:

        return None

    print(
        f"KÜLSŐ PÁRATARTALOM: "
        f"{humidity:.0f} %"
    )

    if not 0 <= humidity <= 100:

        return None

    return humidity


# ============================================================
# BELSŐ PÁRATARTALOM
# ============================================================

def get_indoor_humidity(status):

    if INDOOR_HUMIDITY not in status:

        return None

    humidity = to_float(
        status[
            INDOOR_HUMIDITY
        ]
    )

    if humidity is None:

        return None

    if not 0 <= humidity <= 100:

        return None

    print(
        f"BELSŐ PÁRATARTALOM: "
        f"{humidity:.0f} %"
    )

    return humidity


# ============================================================
# LÉGNYOMÁS
# ============================================================

def get_pressure(status):

    if PRESSURE not in status:

        print(
            "FIGYELEM: nincs "
            "indoor_pressure DP!"
        )

        return None

    raw = to_float(
        status[
            PRESSURE
        ]
    )

    if raw is None:

        return None

    # 100120 -> 1001.20 hPa

    pressure_hpa = raw / 100.0

    print(
        f"LÉGNYOMÁS: "
        f"{raw} -> "
        f"{pressure_hpa:.2f} hPa"
    )

    if not 850 <= pressure_hpa <= 1100:

        print(
            "FIGYELEM: a légnyomás "
            "értéke életszerűtlen."
        )

        return None

    return pressure_hpa


# ============================================================
# SZÉLSEBESSÉG
# ============================================================

def get_wind_speed(status):

    if WIND_SPEED not in status:

        return None

    raw = to_float(
        status[
            WIND_SPEED
        ]
    )

    if raw is None:

        return None

    # A készülék km/h-ban adja,
    # 0,1 km/h felbontással.

    kmh = raw / 10.0

    mph = kmh * 0.621371192

    print(
        f"SZÉLSEBESSÉG: "
        f"{raw} -> "
        f"{kmh:.1f} km/h -> "
        f"{mph:.1f} mph"
    )

    if not 0 <= mph <= 200:

        return None

    return mph


# ============================================================
# SZÉLLÖKÉS
# ============================================================

def get_wind_gust(status):

    if WIND_GUST not in status:

        return None

    raw = to_float(
        status[
            WIND_GUST
        ]
    )

    if raw is None:

        return None

    kmh = raw / 10.0

    mph = kmh * 0.621371192

    print(
        f"SZÉLLÖKÉS: "
        f"{raw} -> "
        f"{kmh:.1f} km/h -> "
        f"{mph:.1f} mph"
    )

    if not 0 <= mph <= 250:

        return None

    return mph


# ============================================================
# CSAPADÉK
# ============================================================

def get_rain(status):

    if RAIN not in status:

        return None

    raw = to_float(
        status[
            RAIN
        ]
    )

    if raw is None:

        return None

    # A készülék mm-ben adja.
    #
    # A logban 0 volt, ezért:
    # 0 mm -> 0 inch

    rain_mm = raw / 10.0

    rain_inches = rain_mm / 25.4

    print(
        f"CSAPADÉK: "
        f"{raw} -> "
        f"{rain_mm:.1f} mm -> "
        f"{rain_inches:.3f} inch"
    )

    if not 0 <= rain_inches <= 100:

        return None

    return rain_inches


# ============================================================
# UV INDEX
# ============================================================

def get_uv(status):

    if UV_INDEX not in status:

        return None

    uv = to_float(
        status[
            UV_INDEX
        ]
    )

    if uv is None:

        return None

    print(
        f"UV INDEX: {uv}"
    )

    if not 0 <= uv <= 20:

        return None

    return uv


# ============================================================
# WEATHER UNDERGROUND
# ============================================================

def upload_to_wunderground(
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
    print("=" * 60)
    print(
        "WEATHER UNDERGROUND FELTÖLTÉS"
    )
    print("=" * 60)

    for key, value in payload.items():

        print(
            f"{key} = {value}"
        )

    response = requests.get(
        url,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    print()
    print(
        f"WU HTTP: "
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

    cloud = create_tuya_cloud()

    status = get_tuya_status(
        cloud
    )

    print()
    print("=" * 60)
    print(
        "ÉRZÉKELŐADATOK"
    )
    print("=" * 60)

    # --------------------------------------------------------
    # FONTOS:
    # KÜLSŐ HŐMÉRSÉKLETET HASZNÁLUNK!
    # --------------------------------------------------------

    outdoor_temperature = (
        get_outdoor_temperature(
            status
        )
    )

    outdoor_humidity = (
        get_outdoor_humidity(
            status
        )
    )

    pressure = get_pressure(
        status
    )

    wind_speed = get_wind_speed(
        status
    )

    wind_gust = get_wind_gust(
        status
    )

    rain = get_rain(
        status
    )

    uv = get_uv(
        status
    )

    print("=" * 60)


    # ========================================================
    # WEATHER UNDERGROUND ADATOK
    # ========================================================

    payload = {}


    # Külső hőmérséklet
    #
    # WU Fahrenheitben várja.

    if outdoor_temperature is not None:

        temp_f = (
            outdoor_temperature
            * 9.0 / 5.0
            + 32.0
        )

        payload["tempf"] = (
            f"{temp_f:.1f}"
        )


    # Külső páratartalom

    if outdoor_humidity is not None:

        payload["humidity"] = str(
            int(
                round(
                    outdoor_humidity
                )
            )
        )


    # Légnyomás
    #
    # WU baromin = inch Hg

    if pressure is not None:

        pressure_inhg = (
            pressure
            * 0.0295299830714
        )

        payload["baromin"] = (
            f"{pressure_inhg:.3f}"
        )


    # Szélsebesség

    if wind_speed is not None:

        payload["windspeedmph"] = (
            f"{wind_speed:.1f}"
        )


    # Széllökés

    if wind_gust is not None:

        payload["windgustmph"] = (
            f"{wind_gust:.1f}"
        )


    # Csapadék

    if rain is not None:

        payload["rainin"] = (
            f"{rain:.3f}"
        )


    # UV

    if uv is not None:

        payload["UV"] = (
            f"{uv:.1f}"
        )


    print()
    print("=" * 60)
    print(
        "WEATHER UNDERGROUND PAYLOAD"
    )
    print("=" * 60)

    if not payload:

        raise RuntimeError(
            "Nem sikerült egyetlen "
            "Weather Underground adatot "
            "sem előállítani."
        )

    for key, value in payload.items():

        print(
            f"{key} = {value}"
        )

    print("=" * 60)


    # ========================================================
    # FELTÖLTÉS
    # ========================================================

    upload_to_wunderground(
        payload
    )

    print()
    print("=" * 60)
    print(
        "SIKERES FUTTATÁS"
    )
    print("=" * 60)


# ============================================================
# PROGRAM INDÍTÁSA
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
