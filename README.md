# Tuya → Weather Underground bridge

A script that reads the current status of a Tuya Cloud weather device and uploads the measurements to Weather Underground.

## How it works

The script makes two Tuya Cloud API calls per run:

1. `/v1.0/iot-03/devices/{device_id}/status` – current device values.
2. `/v1.0/iot-03/devices/{device_id}/specification` – the device's status definitions, including unit and `scale`.

The second call is important: Tuya numeric values can use a decimal scale, so the script no longer guesses things such as `/10` from the magnitude of a value.

The script also prints every returned DP and its specification to the GitHub Actions log. This makes unusual weather-station DP names easy to identify.

## Required GitHub Secrets

- `TUYA_ACCESS_ID`
- `TUYA_ACCESS_SECRET`
- `TUYA_DEVICE_ID`
- `WU_STATION_ID`
- `WU_STATION_KEY`

Optional:

- `TUYA_REGION` – defaults to `eu`
- `TUYA_TEMP_CODE`
- `TUYA_HUMIDITY_CODE`
- `TUYA_PRESSURE_CODE`
- `TUYA_WIND_SPEED_CODE`
- `TUYA_WIND_GUST_CODE`
- `TUYA_WIND_DIRECTION_CODE`
- `TUYA_RAIN_CODE`

Leave the optional DP secrets empty first. The script tries to identify the measurements from the Tuya status code and specification name. If the station uses unusual names, set the appropriate DP code explicitly.

## GitHub Actions

The included workflow runs every 10 minutes and can also be started manually with **Run workflow**.
