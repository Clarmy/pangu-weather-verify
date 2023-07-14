import os
import json
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
from tqdm import tqdm

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATION_INFO_FP = os.path.join(STATIC_DIR, "station_info.csv")
DATA_URL_PATTERN = "http://www.nmc.cn/rest/weather?stationid={sid}"


def get_station_info():
    df = pd.read_csv(STATION_INFO_FP)

    return df


def parse_data(data):
    try:
        passedchart0 = data["passedchart"][0]
        timestr = passedchart0['time']
        wind_speed = passedchart0["windSpeed"]
        wind_direction = passedchart0["windDirection"]
        temperature = passedchart0["temperature"]
        humidity = passedchart0["humidity"]

        dt = datetime.fromisoformat(timestr).replace(
            tzinfo=timezone(timedelta(hours=8))
        )
    except (KeyError, TypeError):
        return False

    return {
        "datetime": dt,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "temperature": temperature,
        "humidity": humidity,
    }


if __name__ == "__main__":
    station_df = get_station_info()

    url_error_list = []
    data_error_list = []
    sids = station_df["区站号"].tolist()
    records = []
    for sid in tqdm(sids):
        URL = DATA_URL_PATTERN.format(sid=sid)
        try:
            resp = requests.get(URL, timeout=3)
        except Exception:
            url_error_list.append(sid)
            continue
        if resp.ok:
            data = resp.json()["data"]
            if data:
                parsed_data = parse_data(data)
                if parsed_data:
                    records.append(parsed_data)
                else:
                    data_error_list.append(sid)
            else:
                continue

    df = pd.DataFrame(records)
    df.to_csv("./test.csv", index=False)

    with open("bad_list.json", "w") as f:
        json.dump(url_error_list, f)

    with open("bad_data_list.json", "w") as f:
        json.dump(data_error_list, f)
