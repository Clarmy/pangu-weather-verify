from prepare import prepare_all
from predict import iteratively_predict
from verify import verify

if __name__ == "__main__":
    prepare_result = prepare_all()
    ecmwfarray_fp = prepare_result["ecmwfarray_fp"]
    gfsarray_fp = prepare_result["gfsarray_fp"]
    gfs_batch_dt = prepare_result["gfs_batch_dt"]
    era5_dt = prepare_result["era5_dt"]
    ecmwf_batch_dt = prepare_result["ecmwf_batch_dt"]
    obs_dt = prepare_result["obs_dt"]
    predict_result = iteratively_predict(
        int(era5_dt.timestamp()), int(obs_dt.timestamp())
    )
    surface_fp = predict_result["surface_fp"]
    verify(
        surface_fp,
        ecmwfarray_fp,
        gfsarray_fp,
        era5_dt,
        obs_dt,
        ecmwf_batch_dt,
        gfs_batch_dt,
    )
