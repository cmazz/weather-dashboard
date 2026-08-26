import hashlib
import hmac
import sqlite3
import time
import requests

API_KEY = "insert key here"
API_SECRET = "insert secret here"


def get_signature(params):
    sorted_keys = sorted(params.keys())
    param_str = "".join([f"{k}{params[k]}" for k in sorted_keys])
    return hmac.new(
        API_SECRET.encode("utf-8"),
        param_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def init_db():
    conn = sqlite3.connect("weather.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_weather (
            date TEXT PRIMARY KEY,
            temp_current REAL,
            temp_high REAL,
            temp_low REAL,
            humidity REAL,
            wind_speed REAL,
            bar_pressure REAL,
            dew_point REAL,
            rain_total REAL
        )
    """
    )
    conn.commit()
    conn.close()


def find_weather_sensor(sensors_list):
    for sensor in sensors_list:
        data_records = sensor.get("data", [])
        if not data_records:
            continue
        record = data_records[0]
        if any(
            k in record
            for k in ["temp", "temp_out", "hum", "hum_out", "wind_speed_last"]
        ):
            return record
    return None


def fetch_and_store():
    t = int(time.time())
    stations_params = {"api-key": API_KEY, "t": t}
    stations_sig = get_signature(stations_params)
    stations_url = f"https://api.weatherlink.com/v2/stations?api-key={API_KEY}&t={t}&api-signature={stations_sig}"

    res = requests.get(stations_url).json()
    if "stations" not in res or not res["stations"]:
        print("Failed to retrieve station details:", res)
        return

    station_id = res["stations"][0]["station_id"]

    t = int(time.time())
    current_params = {"api-key": API_KEY, "station-id": station_id, "t": t}
    current_sig = get_signature(current_params)
    current_url = f"https://api.weatherlink.com/v2/current/{station_id}?api-key={API_KEY}&t={t}&api-signature={current_sig}"

    res = requests.get(current_url).json()
    if "sensors" not in res:
        print("Error fetching sensor readings:", res)
        return

    record = find_weather_sensor(res["sensors"])
    if not record:
        print("No active weather sensor data found.")
        return

    date_str = time.strftime(
        "%Y-%m-%d", time.localtime(record.get("ts", time.time()))
    )
    temp = record.get("temp") or record.get("temp_out") or 0.0
    temp_high = record.get("temp_hi_day") or record.get("temp_out_hi_day") or temp
    temp_low = record.get("temp_lo_day") or record.get("temp_out_lo_day") or temp
    hum = record.get("hum") or record.get("hum_out") or 0.0
    wind = (
        record.get("wind_speed_last")
        or record.get("wind_speed_avg_last_10_min")
        or 0.0
    )
    pressure = (
        record.get("bar_sea_level")
        or record.get("bar_absolute")
        or record.get("bar")
        or 0.0
    )
    dew_point = record.get("dew_point") or record.get("dew_point_out") or 0.0
    rain = record.get("rain_day_in") or record.get("rainfall_daily_in") or 0.0

    conn = sqlite3.connect("weather.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO daily_weather VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            date_str,
            temp,
            temp_high,
            temp_low,
            hum,
            wind,
            pressure,
            dew_point,
            rain,
        ),
    )
    conn.commit()
    conn.close()
    print(
        f"Updated {date_str}: Temp {temp}°F (H: {temp_high}° / L: {temp_low}°), Hum {hum}%, Wind {wind}mph, Press {pressure}inHg, DewPt {dew_point}°F, Rain {rain}in"
    )


if __name__ == "__main__":
    init_db()
    fetch_and_store()