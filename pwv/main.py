from prepare import prepare_all
from predict import iteratively_predict
from verify import verify

if __name__ == "__main__":
    prepare_result = prepare_all()
    era5_dt = prepare_result["era5_dt"]
    obs_dt = prepare_result["obs_dt"]
    predict_result = iteratively_predict(int(era5_dt.timestamp()), int(obs_dt.timestamp()))
    surface_fp = predict_result["surface_fp"]
    verify(surface_fp)
