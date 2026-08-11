import os
import sys
import json
import tinytuya

TUYA_ACCESS_ID = os.environ.get("TUYA_ACCESS_ID")
TUYA_ACCESS_SECRET = os.environ.get("TUYA_ACCESS_SECRET")
TUYA_DEVICE_ID = os.environ.get("TUYA_DEVICE_ID")
TUYA_REGION = "eu"


def check_environment():
    required = {
        "TUYA_ACCESS_ID": TUYA_ACCESS_ID,
        "TUYA_ACCESS_SECRET": TUYA_ACCESS_SECRET,
        "TUYA_DEVICE_ID": TUYA_DEVICE_ID,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(
            "Hiányzó GitHub Secret: " + ", ".join(missing)
        )


def create_cloud():
    print("=" * 70)
    print("YT60307 TUYA DIAGNOSZTIKA")
    print("=" * 70)
    print("Régió: eu")
    print(f"Device ID: {TUYA_DEVICE_ID}")
    return tinytuya.Cloud(
        apiRegion="eu",
        apiKey=TUYA_ACCESS_ID,
        apiSecret=TUYA_ACCESS_SECRET,
    )


def get_status(cloud):
    print()
    print("=" * 70)
    print("1. GETSTATUS")
    print("=" * 70)
    try:
        response = cloud.getstatus(TUYA_DEVICE_ID)
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return response
    except Exception as exc:
        print(f"HIBA: {exc}")
        return None


def request(cloud, label, endpoint):
    print()
    print("=" * 70)
    print(label)
    print("=" * 70)
    print(f"Endpoint: {endpoint}")
    try:
        response = cloud.cloudrequest(endpoint)
        print(json.dumps(response, ensure_ascii=False, indent=2))
        return response
    except Exception as exc:
        print(f"HIBA: {exc}")
        return None


def search_recursive(obj, path="root"):
    if isinstance(obj, dict):
        for key, value in obj.items():
            current = f"{path}.{key}"
            key_text = str(key).lower()

            if any(x in key_text for x in (
                "wind", "direction", "bearing", "azimuth"
            )):
                print()
                print(">>> LEHETSÉGES SZÉLIRÁNY / SZÉL ADAT <<<")
                print(f"PATH: {current}")
                print(f"KEY: {key}")
                if isinstance(value, (dict, list)):
                    print(json.dumps(
                        value, ensure_ascii=False, indent=2
                    ))
                else:
                    print(f"VALUE: {value!r}")

            if key_text in (
                "dp_id", "dpid", "dp", "code",
                "property", "property_code"
            ):
                print(f"DP/PROPERTY: {current} = {value!r}")

            search_recursive(value, current)

    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            search_recursive(value, f"{path}[{i}]")


def main():
    check_environment()
    cloud = create_cloud()

    results = {}

    results["STATUS"] = get_status(cloud)

    endpoints = {
        "SHADOW PROPERTIES":
            f"/v2.0/cloud/thing/{TUYA_DEVICE_ID}/shadow/properties",
        "DEVICE DETAILS":
            f"/v1.0/devices/{TUYA_DEVICE_ID}",
        "DEVICE FUNCTIONS":
            f"/v1.0/devices/{TUYA_DEVICE_ID}/functions",
        "DEVICE SPECIFICATIONS":
            f"/v1.0/devices/{TUYA_DEVICE_ID}/specifications",
    }

    for label, endpoint in endpoints.items():
        results[label] = request(cloud, label, endpoint)

    print()
    print("=" * 70)
    print("SZÉLIRÁNY / WIND KERESÉS")
    print("=" * 70)

    for label, data in results.items():
        if data is None:
            continue
        print()
        print(f"--- {label} ---")
        search_recursive(data)

    print()
    print("=" * 70)
    print("DIAGNOSZTIKA VÉGE")
    print("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"HIBA: {exc}", file=sys.stderr)
        sys.exit(1)
