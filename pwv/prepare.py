import os
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

import numpy as np
import netCDF4 as nc
import pandas as pd
import requests
import pygrib
import toml
import arrow
from tqdm import tqdm
from scipy.interpolate import griddata

from pwv.era5 import ERA5
from retrying import retry

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATION_INFO_FP = os.path.join(STATIC_DIR, "station_info.csv")
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")
OBS_DATA_URL_PATTERN = "http://www.nmc.cn/rest/weather?stationid={sid}"
ECMWF_DATA_DIR_URL_PATTERN = "https://data.ecmwf.int/forecasts/%Y%m%d/%Hz/ifs/0p25/oper"

SURFACE_FIELD_CONDITIONS = {
    "t2m": {"shortName": "2t", "typeOfLevel": "heightAboveGround"},
    "u10": {"shortName": "10u", "typeOfLevel": "heightAboveGround"},
    "v10": {"shortName": "10v", "typeOfLevel": "heightAboveGround"},
}
SURFACE_FIELD_ORDER = ["u10", "v10", "t2m"]
ERA5_API_KEY = toml.load(os.path.join(os.path.dirname(__file__), "secret.toml"))[
    "cds_api_key"
]


def get_station_info():
    df = pd.read_csv(STATION_INFO_FP)

    return df


def parse_obs_data(data, sid, ts):
    try:
        for passedchart in data["passedchart"]:
            timestr = passedchart["time"]
            dt = (
                datetime.fromisoformat(timestr)
                .replace(tzinfo=timezone(timedelta(hours=8)))
                .astimezone(timezone.utc)
            )
            # 取 ECMWF 的预报点
            if int(dt.timestamp()) != ts:
                continue
            else:
                wind_speed = passedchart["windSpeed"]
                wind_direction = passedchart["windDirection"]
                temperature = passedchart["temperature"]
                humidity = passedchart["humidity"]
                break
        else:
            return False
    except (KeyError, TypeError):
        return False
    else:
        if wind_speed > 9000 or temperature > 9000:
            return False
        return {
            "sid": sid,
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
    now_dt = arrow.now(tz="utc").floor("hour")
    round3dt = now_dt.replace(hour=now_dt.hour // 3 * 3)
    want_dt = round3dt.shift(hours=-3)
    want_ts = int(want_dt.timestamp())

    for sid in tqdm(sids):
        URL = OBS_DATA_URL_PATTERN.format(sid=sid) + f"&_={int(time.time()*1000)}"
        try:
            resp = requests.get(URL, timeout=5)
        except Exception:
            url_error_list.append(sid)
            continue
        if resp.ok:
            data = resp.json()["data"]
            if data:
                parsed_data = parse_obs_data(data, sid, want_ts)
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

    return dt, len(df)


@retry(stop_max_attempt_number=7)
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
    if r.ok:
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
        return True
    else:
        return None


@retry(stop_max_attempt_number=7)
def download_ecmwf_data(dt_batch: datetime, dt_obs: datetime):
    delta_hour = int((dt_obs - dt_batch).total_seconds() // 3600)
    step = delta_hour // 3 * 3
    if delta_hour - step > 1:
        step += 3

    url = dt_batch.astimezone(timezone.utc).strftime(
        os.path.join(ECMWF_DATA_DIR_URL_PATTERN, f"%Y%m%d%H%M%S-{step}h-oper-fc.grib2")
    )

    print(
        "Downloading the ECMWF forecast field closest to the observation time, "
        f"the forecast step is：{step}h"
    )
    fn = os.path.basename(url)
    ecmwf_fp = os.path.join(TMP_DIR, fn)
    res = download_file_in_chunks(url, ecmwf_fp)
    if res:
        print("Completed.")

        return ecmwf_fp


@retry(stop_max_attempt_number=7)
def download_gfs_data(dt_obs: datetime):
    print("Downloading GFS forecast field...")
    dt_batch = dt_obs.astimezone(timezone.utc).replace(
        hour=dt_obs.astimezone(timezone.utc).hour // 6 * 6
    )
    URL_PATTERN = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25_1hr.pl?dir=%2Fgfs.{datestr}%2F{hourstr}%2Fatmos&file=gfs.t{hourstr}z.pgrb2.0p25.f{step}&var_TMP=on&var_UGRD=on&var_VGRD=on&lev_2_m_above_ground=on&lev_10_m_above_ground=on"
    while True:
        delta_hour = int((dt_obs - dt_batch).total_seconds() // 3600)
        datestr = dt_batch.strftime("%Y%m%d")
        hourstr = dt_batch.strftime("%H")
        print(f"Checking {dt_batch}")
        if delta_hour <= 120:
            step = f"{delta_hour:03d}"
        else:
            step = delta_hour // 3 * 3
            if delta_hour - step > 1:
                step += 3
            step = f"{step:03d}"

        url = URL_PATTERN.format(datestr=datestr, hourstr=hourstr, step=step)
        print(f"Downloading from {url}")
        resp = requests.get(url, timeout=10, stream=True)
        if resp.ok:
            fn = f"gfs.t{hourstr}z.pgrb2.0p25.f{step}.grb"
            gfs_fp = os.path.join(TMP_DIR, fn)
            res = download_file_in_chunks(url, gfs_fp)
            if res:
                print("Completed.")
                return gfs_fp, dt_batch

        dt_batch -= timedelta(hours=6)


def interpolate(lons, lats, data):
    # data, lats, lons = msg.data()
    length = lons.shape[1]
    if lons.min() < 0:
        lons[..., : int(length / 2)] = lons[..., : int(length / 2)] + 360

    # np.concatenate([lons[720:], lons[:720]], axis=1)
    data1d = data.flatten()
    lats1d = lats.flatten()
    lons1d = lons.flatten()

    points = np.array([lons1d, lats1d]).T
    new_x = np.linspace(0, 359.75, 1440)
    new_y = np.linspace(90, -90, 721)

    grid_x, grid_y = np.meshgrid(new_x, new_y)
    new_data = griddata(points, data1d, (grid_x, grid_y), method="linear")

    return new_data


@retry(stop_max_attempt_number=7)
def download_era5_data(api_key):
    era5 = ERA5(api_key)
    surface_fp, dt = era5.fetch_latest_surface(TMP_DIR)
    upper_fp, dt = era5.fetch_latest_upper(TMP_DIR)

    return surface_fp, upper_fp, dt


def transfer_ecmwf(grib2_fp):
    messages = pygrib.open(grib2_fp)
    surface_dataset = {}
    print("Start transfering ECMWF data...")
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
    savefp = os.path.join(TMP_DIR, "surface-ecmwf.npy")
    np.save(savefp, surface_array)

    print("Finished.")

    return savefp


def transfer_gfs(grib2_fp):
    messages = pygrib.open(grib2_fp)
    surface_dataset = {}
    print("Start transfering GFS data...")
    for varname, conditions in SURFACE_FIELD_CONDITIONS.items():
        print(f"Processing {varname}...")
        msg = messages.select(**conditions)[0]

        data, _, _ = msg.data()
        surface_dataset[varname] = data

    surface_array = []
    for varname in SURFACE_FIELD_ORDER:
        surface_array.append(surface_dataset[varname])

    surface_array = np.stack(surface_array)
    savefp = os.path.join(TMP_DIR, "surface-gfs.npy")
    np.save(savefp, surface_array)

    print("Finished.")

    return savefp


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
        # reverse the vertical axis
        data = ds.variables[v][0, ::-1].data.astype(np.float32)
        array.append(data)

    array = np.stack(array)

    np.save(outfp, array)


def prepare_all():
    os.makedirs(TMP_DIR, exist_ok=True)

    dt_obs, obs_count = prepare_observation()

    dt_batch = dt_obs
    print("Searching for the ECMWF forecast batch closest to the observation time.")
    while True:
        batch_exist = check_ecmwf_dir_exist(dt_batch)
        if batch_exist:
            print(
                "Found the ECMWF forecast batch closest to the observation time, "
                f"the start time of which is：{dt_batch.isoformat()}"
            )
            ecmwfp = download_ecmwf_data(dt_batch, dt_obs)
            if ecmwfp:
                break
            else:
                print("Failed to download the file from this batch, try again.")
        dt_batch -= timedelta(hours=1)

    ecmwfarray_fp = transfer_ecmwf(ecmwfp)

    gfs_fp, gfs_batch_dt = download_gfs_data(dt_obs)
    gfsarray_fp = transfer_gfs(gfs_fp)

    surfacefp, upperfp, era5_dt = download_era5_data(ERA5_API_KEY)
    timestamp = int(era5_dt.timestamp())
    input_surface_fp = os.path.join(TMP_DIR, f"surface-{timestamp}.npy")
    transfer_surface(surfacefp, input_surface_fp)
    input_upper_fp = os.path.join(TMP_DIR, f"upper-{timestamp}.npy")
    transfer_upper(upperfp, input_upper_fp)
    print("Prepare work has been completed, you can continue to start prediction work.")

    return {
        "ecmwfarray_fp": ecmwfarray_fp,
        "gfsarray_fp": gfsarray_fp,
        "input_surface_fp": input_surface_fp,
        "input_upper_fp": input_upper_fp,
        "obs_dt": dt_obs,
        "ecmwf_batch_dt": dt_batch,
        "gfs_batch_dt": gfs_batch_dt,
        "era5_dt": era5_dt,
        "obs_count": obs_count,
    }


if __name__ == "__main__":
    prepare_all()
