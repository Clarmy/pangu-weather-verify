import os
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np
import netCDF4 as nc
import pandas as pd
import requests
import pygrib
from tqdm import tqdm
from scipy.interpolate import griddata

from era5 import ERA5

ERA5_API_KEY = "" # 输入你自己的 CDS API Key
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATION_INFO_FP = os.path.join(STATIC_DIR, "station_info.csv")
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
OBS_DATA_URL_PATTERN = "http://www.nmc.cn/rest/weather?stationid={sid}"
ECMWF_DATA_DIR_URL_PATTERN = "https://data.ecmwf.int/forecasts/%Y%m%d/%Hz/0p4-beta/oper"

SURFACE_FIELD_CONDITIONS = {
    "mslp": {"shortName": "msl", "typeOfLevel": "meanSea"},
    "t2m": {"shortName": "2t", "typeOfLevel": "heightAboveGround"},
    "u10": {"shortName": "10u", "typeOfLevel": "heightAboveGround"},
    "v10": {"shortName": "10v", "typeOfLevel": "heightAboveGround"},
}
SURFACE_FIELD_ORDER = ["mslp", "u10", "v10", "t2m"]

UPPER_LEVELS = [1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150, 100, 50]
UPPER_FIELD_CONDITIONS = {}
UPPER_FIELD_ORDER = ["gh", "q", "t", "u", "v"]

for field in ["q", "t", "gh", "u", "v"]:
    UPPER_FIELD_CONDITIONS[field] = [
        {"shortName": field, "level": lev} for lev in UPPER_LEVELS
    ]

os.makedirs(TMP_DIR, exist_ok=True)


def get_station_info():
    df = pd.read_csv(STATION_INFO_FP)

    return df


def parse_obs_data(data):
    try:
        for passedchart in data["passedchart"]:
            timestr = passedchart["time"]
            dt = (
                datetime.fromisoformat(timestr)
                .replace(tzinfo=timezone(timedelta(hours=8)))
                .astimezone(timezone.utc)
            )
            # 取 ECMWF 的预报点
            if dt.hour % 3 != 0:
                continue
            else:
                wind_speed = passedchart["windSpeed"]
                wind_direction = passedchart["windDirection"]
                temperature = passedchart["temperature"]
                humidity = passedchart["humidity"]
                break
    except (KeyError, TypeError):
        return False

    return {
        "datetime": dt,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "temperature": temperature,
        "humidity": humidity,
    }


def prepare_observation():
    station_df = get_station_info()

    url_error_list = []
    data_error_list = []
    sids = station_df["区站号"].tolist()
    records = []
    dts = []
    print("Downloading observation data...")
    for sid in tqdm(sids):
        URL = OBS_DATA_URL_PATTERN.format(sid=sid)
        try:
            resp = requests.get(URL, timeout=3)
        except Exception:
            url_error_list.append(sid)
            continue
        if resp.ok:
            data = resp.json()["data"]
            if data:
                parsed_data = parse_obs_data(data)
                if parsed_data:
                    records.append(parsed_data)
                    dt = parsed_data["datetime"]
                    dts.append(dt)
                else:
                    data_error_list.append(sid)
            else:
                continue

    if len(set(dts)) > 1:
        most_common_dt = Counter(dts).most_common(1)[0][0]
        other_dts = set(dts) - set([most_common_dt])
        for dt in other_dts:
            idx = dts.index(dt)
            del dts[idx]
            del records[idx]

    assert len(set(dts)) == 1

    dt = dts[0]
    df = pd.DataFrame(records)
    df.to_csv(os.path.join(TMP_DIR, "obervation.csv"), index=False)
    print(
        "Observation data download is completed, "
        f"a total of {len(df)} observation stations' data downloaded, "
        f"the observation time is: {dt.isoformat()} "
    )

    return dt


def check_ecmwf_dir_exist(dt: datetime):
    url = dt.astimezone(timezone.utc).strftime(ECMWF_DATA_DIR_URL_PATTERN)
    try:
        resp = requests.get(url, timeout=3)
    except Exception:
        return False
    else:
        if resp.ok:
            return True
        else:
            return False


def download_file_in_chunks(url, dest_path, chunk_size=1024):
    r = requests.get(url, stream=True)
    with open(dest_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)


def download_ecmwf_data(dt_batch: datetime, dt_obs: datetime):
    delta_hour = int((dt_obs - dt_batch).total_seconds() // 3600)
    step = delta_hour // 3 * 3
    if delta_hour - step > 1:
        step += 3

    url = dt_obs.astimezone(timezone.utc).strftime(
        os.path.join(ECMWF_DATA_DIR_URL_PATTERN, f"%Y%m%d%H%M%S-{step}h-oper-fc.grib2")
    )

    print(
        "Downloading the ECMWF forecast field closest to the observation time, "
        f"the forecast step is：{step}h"
    )
    ecmwf_fp = os.path.join(TMP_DIR, "ecmwf-forecast.grib2")
    download_file_in_chunks(url, ecmwf_fp)
    print("Completed.")

    return ecmwf_fp


def interpolate(lons, lats, data):
    # data, lats, lons = msg.data()
    data1d = data.flatten()
    lats1d = lats.flatten()
    lons1d = lons.flatten()

    points = np.array([lats1d, lons1d]).T
    new_x = np.linspace(0, 359.75, 1440)
    new_y = np.linspace(90, -90, 721)

    grid_x, grid_y = np.meshgrid(new_x, new_y)
    new_data = griddata(points, data1d, (grid_x, grid_y), method="linear")

    return new_data


def download_era5_data(api_key):
    era5 = ERA5(api_key)
    surface_fp, dt = era5.fetch_latest_surface(TMP_DIR)
    upper_fp, dt = era5.fetch_latest_upper(TMP_DIR)

    return surface_fp, upper_fp, dt


def transfer_ecmwf(grib2_fp):
    messages = pygrib.open(grib2_fp)
    surface_dataset = {}
    for varname, conditions in SURFACE_FIELD_CONDITIONS.items():
        print(f"Processing {varname}...")
        msg = messages.select(**conditions)[0]
        data, lats, lons = msg.data()
        data = interpolate(lons, lats, data)
        surface_dataset[varname] = data

    surface_array = []
    for varname in SURFACE_FIELD_ORDER:
        surface_array.append(surface_dataset[varname])

    surface_array = np.stack(surface_array)
    np.save(os.path.join(TMP_DIR, "surface.npy"), surface_array)

    upper_dataset = {}
    for varname, conditions in UPPER_FIELD_CONDITIONS.items():
        array = []
        for condition in conditions:
            lev = condition["level"]
            print(f"Processing {varname} at {lev}...")
            try:
                msg = messages.select(**condition)[0]
            except ValueError as err:
                print(condition)
                raise err
            data, lats, lons = msg.data()
            if varname == "gh":
                print(f"gh0.mean(): {data.mean()}")
                data = data * 9.80665
                print(f"gh1.mean(): {data.mean()}")

            data = interpolate(lons, lats, data)
            array.append(data)

        array = np.stack(array)
        upper_dataset[varname] = array

    upper_array = []
    for varname in UPPER_FIELD_ORDER:
        upper_array.append(upper_dataset[varname])

    upper_array = np.stack(upper_array)
    np.save(os.path.join(TMP_DIR, "upper.npy"), upper_array)

    print("Finished.")


def transfer_surface(infp, outfp):
    ds = nc.Dataset(infp)
    VAR_ORDER = ["msl", "u10", "v10", "t2m"]
    array = []
    for v in VAR_ORDER:
        print(f"Processing {v}...")
        data = ds.variables[v][0].data.astype(np.float32)
        array.append(data)

    array = np.stack(array)

    np.save(outfp, array)


def transfer_upper(infp, outfp):
    ds = nc.Dataset(infp)
    VAR_ORDER = ["z", "q", "t", "u", "v"]
    array = []
    for v in VAR_ORDER:
        print(f"Processing {v}...")
        data = ds.variables[v][0].data.astype(np.float32)
        array.append(data)

    array = np.stack(array)

    np.save(outfp, array)


def prepare_all():
    dt_obs = prepare_observation()

    dt_batch = dt_obs
    print("Searching for the ECMWF forecast batch closest to the observation time.")
    while True:
        batch_exist = check_ecmwf_dir_exist(dt_batch)
        if batch_exist:
            print(
                "Found the ECMWF forecast batch closest to the observation time, "
                f"the start time of which is：{dt_batch.isoformat()}"
            )
            break
        dt_batch -= timedelta(hours=1)

    ecmwfp = download_ecmwf_data(dt_batch, dt_obs)
    surfacefp, upperfp, era5_dt = download_era5_data(ERA5_API_KEY)
    timestamp = int(era5_dt.timestamp())
    input_surface_fp = os.path.join(TMP_DIR, f"surface-{timestamp}.npy")
    transfer_surface(surfacefp, input_surface_fp)
    os.remove(surfacefp)
    input_upper_fp = os.path.join(TMP_DIR, f"upper-{timestamp}.npy")
    transfer_upper(upperfp, input_upper_fp)
    os.remove(upperfp)
    print("Prepare work has been completed, you can continue to start prediction work.")

    return {
        "ecmwfp": ecmwfp,
        "input_surface_fp": input_surface_fp,
        "input_upper_fp": input_upper_fp,
        "obs_dt": dt_obs,
        "ecmwf_batch_dt": dt_batch,
        "era5_dt": era5_dt,
    }


if __name__ == "__main__":
    prepare_all()
