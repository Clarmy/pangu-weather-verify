import os
import json

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


def extract_pangu_station_data(surf_fp):
    surf_array = np.load(surf_fp)
    pangu_idx = get_pangu_station_idx()
    sids = []
    u10s = []
    v10s = []
    t2ms = []
    for sid, (iy, ix) in pangu_idx.items():
        data = surf_array[:, iy, ix]
        u10s.append(data[1])
        v10s.append(data[2])
        t2ms.append(data[3])
        sids.append(sid)

    u10s = np.array(u10s)
    v10s = np.array(v10s)
    t2ms = np.array(t2ms)
    ws10s, wd10s = uv_to_wind_speed_direction(u10s, v10s)
    t2ms = t2ms - 273.15

    df = pd.DataFrame(
        {
            "temperature": t2ms,
            "wind_speed": ws10s,
            "wind_direction": wd10s,
            "sid": sids,
        }
    )

    return df


def verify(surface_fp):
    print("Verifying...")
    df_pangu = extract_pangu_station_data(surface_fp)
    df_obs = get_observation()

    df_pangu["sid"] = df_pangu["sid"].astype(int)
    df_obs["sid"] = df_obs["sid"].astype(int)

    df = pd.merge(
        df_pangu,
        df_obs,
        left_on="sid",
        right_on="sid",
        how="inner",
        suffixes=("_pangu", "_obs"),
    )

    pangu_temp = df["temperature_pangu"].values
    obs_temp = df["temperature_obs"].values
    cp_temp = Comparison(observation=obs_temp, forecast=pangu_temp)
    temp_rmse = cp_temp.calc_rmse()
    temp_mae = cp_temp.calc_mae()
    accuracy_ratio_within_1deg = cp_temp.calc_diff_accuracy_ratio(limit=1)
    accuracy_ratio_within_2deg = cp_temp.calc_diff_accuracy_ratio(limit=2)
    accuracy_ratio_within_3deg = cp_temp.calc_diff_accuracy_ratio(limit=3)

    temp_result = {
        "rmse": temp_rmse,
        "mae": temp_mae,
        "accuracy_ratio_within_1deg": accuracy_ratio_within_1deg,
        "accuracy_ratio_within_2deg": accuracy_ratio_within_2deg,
        "accuracy_ratio_within_3deg": accuracy_ratio_within_3deg,
    }

    pangu_speed = df["wind_speed_pangu"].values
    pangu_direction = df["wind_direction_pangu"].values
    obs_speed = df["wind_speed_obs"].values
    obs_direction = df["wind_direction_obs"].values
    cp_wind = WindComparison(
        obs_spd=obs_speed,
        fct_spd=pangu_speed,
        obs_dir=obs_direction,
        fct_dir=pangu_direction,
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

    wind_result = {
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

    result = {"temperature": temp_result, "wind": wind_result}
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
    verify(
        "/Users/clarmylee/github/pangu-weather-verify/pwv/tmp/surface-1689433200.npy"
    )
