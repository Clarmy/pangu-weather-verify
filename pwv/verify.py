import os
import re
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from cyeva import Comparison, WindComparison

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
STATION_INFO_FP = os.path.join(STATIC_DIR, "station_info.csv")
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")


def get_observation():
    df = pd.read_csv(os.path.join(TMP_DIR, "obervation.csv"))

    return df[["sid", "wind_speed", "wind_direction", "temperature"]]


def get_nearest_idx(points, point):
    return np.abs(points - point).argmin()


def get_pangu_station_idx():
    pangu_idx_fp = os.path.join(TMP_DIR, "pangu_station_idx.json")
    if os.path.exists(pangu_idx_fp):
        with open(pangu_idx_fp) as f:
            pangu_idx = json.load(f)
    else:
        wlon = np.linspace(0, 359.75, 1440)
        wlat = np.linspace(90, -90, 721)

        station_df = pd.read_csv(STATION_INFO_FP)
        sids = station_df["区站号"].tolist()
        lons = station_df["经度"].tolist()
        lats = station_df["纬度"].tolist()
        pangu_idx = {}
        for sid, lon, lat in zip(sids, lons, lats):
            ix = int(get_nearest_idx(wlon, lon))
            iy = int(get_nearest_idx(wlat, lat))
            pangu_idx[sid] = (iy, ix)

        with open(pangu_idx_fp, "w") as f:
            json.dump(pangu_idx, f)

    return pangu_idx


def uv_to_wind_speed_direction(u, v):
    """
    Convert u, v wind components to wind speed and wind direction.

    Parameters:
    u : np.ndarray
        Zonal wind component (m/s).
    v : np.ndarray
        Meridional wind component (m/s).

    Returns:
    speed : np.ndarray
        Wind speed (m/s).
    direction : np.ndarray
        Wind direction in degrees, where 0 degree reference is North (meteorological convention).
    """
    speed = np.sqrt(u**2 + v**2)
    direction = (np.arctan2(u, v) * (180 / np.pi) + 180) % 360

    return speed, direction


def extract_station_forecast_data(pangu_surf_fp, ecmwf_surf_fp, gfs_surf_fp):
    pangu_surf_array = np.load(pangu_surf_fp)
    ecmwf_surf_array = np.load(ecmwf_surf_fp)
    gfs_surf_array = np.load(gfs_surf_fp)
    pangu_idx = get_pangu_station_idx()
    sids = []

    pangu_u10s = []
    pangu_v10s = []
    pangu_t2ms = []

    ec_u10s = []
    ec_v10s = []
    ec_t2ms = []

    gfs_u10s = []
    gfs_v10s = []
    gfs_t2ms = []

    for sid, (iy, ix) in pangu_idx.items():
        pangu_data = pangu_surf_array[:, iy, ix]
        ec_data = ecmwf_surf_array[:, iy, ix]
        gfs_data = gfs_surf_array[:, iy, ix]
        sids.append(sid)
        pangu_u10s.append(pangu_data[1])
        pangu_v10s.append(pangu_data[2])
        pangu_t2ms.append(pangu_data[3])

        ec_u10s.append(ec_data[0])
        ec_v10s.append(ec_data[1])
        ec_t2ms.append(ec_data[2])

        gfs_u10s.append(gfs_data[0])
        gfs_v10s.append(gfs_data[1])
        gfs_t2ms.append(gfs_data[2])

    pangu_u10s = np.array(pangu_u10s)
    pangu_v10s = np.array(pangu_v10s)
    pangu_t2ms = np.array(pangu_t2ms)
    pangu_ws10s, pangu_wd10s = uv_to_wind_speed_direction(pangu_u10s, pangu_v10s)
    pangu_t2ms = pangu_t2ms - 273.15

    ec_u10s = np.array(ec_u10s)
    ec_v10s = np.array(ec_v10s)
    ec_t2ms = np.array(ec_t2ms)
    ec_ws10s, ec_wd10s = uv_to_wind_speed_direction(ec_u10s, ec_v10s)
    ec_t2ms = ec_t2ms - 273.15

    gfs_u10s = np.array(gfs_u10s)
    gfs_v10s = np.array(gfs_v10s)
    gfs_t2ms = np.array(gfs_t2ms)
    gfs_ws10s, gfs_wd10s = uv_to_wind_speed_direction(gfs_u10s, gfs_v10s)
    gfs_t2ms = gfs_t2ms - 273.15

    df = pd.DataFrame(
        {
            "pangu_temperature": pangu_t2ms,
            "pangu_wind_speed": pangu_ws10s,
            "pangu_wind_direction": pangu_wd10s,
            "ec_temperature": ec_t2ms,
            "ec_wind_speed": ec_ws10s,
            "ec_wind_direction": ec_wd10s,
            "gfs_temperature": gfs_t2ms,
            "gfs_wind_speed": gfs_ws10s,
            "gfs_wind_direction": gfs_wd10s,
            "sid": sids,
        }
    )

    return df


def sinlge_verify(df, init_dt, obs_dt, prefix="pangu"):
    fct_temp = df[f"{prefix}_temperature"].values
    obs_temp = df["temperature"].values
    cp_temp = Comparison(observation=obs_temp, forecast=fct_temp)
    temp_rmse = cp_temp.calc_rmse()
    temp_mae = cp_temp.calc_mae()
    accuracy_ratio_within_1deg = cp_temp.calc_diff_accuracy_ratio(limit=1)
    accuracy_ratio_within_2deg = cp_temp.calc_diff_accuracy_ratio(limit=2)
    accuracy_ratio_within_3deg = cp_temp.calc_diff_accuracy_ratio(limit=3)

    fct_temp_result = {
        "rmse": temp_rmse,
        "mae": temp_mae,
        "accuracy_ratio_within_1deg": accuracy_ratio_within_1deg,
        "accuracy_ratio_within_2deg": accuracy_ratio_within_2deg,
        "accuracy_ratio_within_3deg": accuracy_ratio_within_3deg,
    }

    fct_speed = df[f"{prefix}_wind_speed"].values
    fct_direction = df[f"{prefix}_wind_direction"].values
    obs_speed = df["wind_speed"].values
    obs_direction = df["wind_direction"].values
    cp_wind = WindComparison(
        obs_spd=obs_speed,
        fct_spd=fct_speed,
        obs_dir=obs_direction,
        fct_dir=fct_direction,
    )
    wind_rmse = cp_wind.calc_rmse()
    wind_mae = cp_wind.calc_mae()
    accuracy_ratio_within_1ms = cp_wind.calc_diff_accuracy_ratio(limit=1)
    accuracy_ratio_within_2ms = cp_wind.calc_diff_accuracy_ratio(limit=2)
    accuracy_ratio_within_3ms = cp_wind.calc_diff_accuracy_ratio(limit=3)
    scale_stronger_ratio = cp_wind.calc_wind_scale_stronger_ratio()
    scale_weaker_ratio = cp_wind.calc_wind_scale_weaker_ratio()
    scale_accuracy = cp_wind.calc_wind_scale_accuracy_ratio()
    speed_score = cp_wind.calc_speed_score()
    direction_score = cp_wind.calc_dir_score()

    fct_wind_result = {
        "speed_rmse": wind_rmse,
        "speed_mae": wind_mae,
        "speed_accuracy_ratio_within_1ms": accuracy_ratio_within_1ms,
        "speed_accuracy_ratio_within_2ms": accuracy_ratio_within_2ms,
        "speed_accuracy_ratio_within_3ms": accuracy_ratio_within_3ms,
        "scale_stronger_ratio": scale_stronger_ratio,
        "scale_weaker_ratio": scale_weaker_ratio,
        "scale_accuracy": scale_accuracy,
        "speed_score": speed_score,
        "direction_score": direction_score,
    }

    result = {
        "temperature": fct_temp_result,
        "wind": fct_wind_result,
        "init_time": init_dt.isoformat(),
        "forecast_hour_delta": int((obs_dt - init_dt).total_seconds() / 3600),
    }

    return result


def verify(
    pangu_surface_fp,
    ec_surface_fp,
    gfs_surface_fp,
    era5_dt,
    obs_dt,
    ecmwf_batch_dt,
    gfs_batch_dt,
):
    print("Verifying...")
    df_predict = extract_station_forecast_data(
        pangu_surface_fp, ec_surface_fp, gfs_surface_fp
    )
    df_obs = get_observation()

    df_predict["sid"] = df_predict["sid"].astype(int)
    df_obs["sid"] = df_obs["sid"].astype(int)

    df = pd.merge(
        df_predict,
        df_obs,
        left_on="sid",
        right_on="sid",
        how="inner",
    )

    df = df[
        [
            "sid",
            "temperature",
            "pangu_temperature",
            "ec_temperature",
            "gfs_temperature",
            "wind_speed",
            "pangu_wind_speed",
            "ec_wind_speed",
            "gfs_wind_speed",
            "wind_direction",
            "pangu_wind_direction",
            "ec_wind_direction",
            "gfs_wind_direction",
        ]
    ]
    df.to_csv("./compare.csv", index=False)

    pangu_result = sinlge_verify(df, era5_dt, obs_dt, "pangu")
    ec_result = sinlge_verify(df, ecmwf_batch_dt, obs_dt, "ec")
    gfs_result = sinlge_verify(df, gfs_batch_dt, obs_dt, "gfs")

    result = {
        "pangu": pangu_result,
        "ecmwf": ec_result,
        "gfs": gfs_result,
        "observation_datetime": obs_dt.isoformat(),
    }

    with open("./verification_results.json", "w") as f:
        json.dump(
            result,
            f,
            indent=4,
        )
    print(
        'Verification has been done and results are saved to "./verification_results.json".'
    )


if __name__ == "__main__":
    pass
