import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np

import onnxruntime as ort

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tmp")


def predict(input_surface_fp, input_upper_fp, step_mode=24, gpu=False):
    input_surface_fn = os.path.basename(input_surface_fp)
    input_upper_fn = os.path.basename(input_upper_fp)

    input_surf_ts = re.match(r"surface-(\d+).npy", input_surface_fn).group(1)
    input_upper_ts = re.match(r"upper-(\d+).npy", input_upper_fn).group(1)

    assert input_surf_ts == input_upper_ts

    new_surf_ts = int(input_surf_ts) + step_mode * 3600
    new_upper_ts = int(input_upper_ts) + step_mode * 3600

    output_surface_fp = os.path.join(
        os.path.dirname(input_surface_fp), f"surface-{new_surf_ts}.npy"
    )
    output_upper_fp = os.path.join(
        os.path.dirname(input_upper_fp), f"upper-{new_upper_ts}.npy"
    )

    if os.path.exists(output_surface_fp) and os.path.exists(output_upper_fp):
        return output_surface_fp, output_upper_fp

    modelfp = os.path.join(STATIC_DIR, f"pangu_weather_{step_mode}.onnx")
    # model = onnx.load(modelfp)

    # Set the behavier of onnxruntime
    options = ort.SessionOptions()
    options.enable_cpu_mem_arena = False
    options.enable_mem_pattern = False
    options.enable_mem_reuse = False
    # Increase the number for faster inference and more memory consumption
    options.intra_op_num_threads = 1

    if gpu:
        cuda_provider_options = {
            "arena_extend_strategy": "kSameAsRequested",
        }

        ort_session = ort.InferenceSession(
            modelfp,
            sess_options=options,
            providers=[("CUDAExecutionProvider", cuda_provider_options)],
        )
    else:
        ort_session = ort.InferenceSession(
            modelfp, sess_options=options, providers=["CPUExecutionProvider"]
        )

    # Load the upper-air numpy arrays
    input_upper_array = np.load(input_upper_fp).astype(np.float32)
    # Load the surface numpy arrays
    input_surface_array = np.load(input_surface_fp).astype(np.float32)

    # Run the inference session
    output_upper_array, output_surface_array = ort_session.run(
        None, {"input": input_upper_array, "input_surface": input_surface_array}
    )

    # Save the results
    # output_surface_fp, output_upper_fp = input_surface_fp, input_upper_fp

    np.save(output_upper_fp, output_upper_array)
    np.save(output_surface_fp, output_surface_array)

    return output_surface_fp, output_upper_fp


def iteratively_predict(init_timestamp, target_timestamp):
    input_surface_fp = os.path.join(TMP_DIR, f"surface-{init_timestamp}.npy")
    input_upper_fp = os.path.join(TMP_DIR, f"upper-{init_timestamp}.npy")

    steps = {24: 24 * 3600, 6: 6 * 3600, 3: 3 * 3600, 1: 1 * 3600}
    timestamp = init_timestamp

    forward_records = []
    while timestamp < target_timestamp:
        delta_hour = int((target_timestamp - timestamp) // 3600)

        for step, interval in steps.items():
            if delta_hour >= step:
                step_num = delta_hour // step
                for _ in range(step_num):
                    dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                    dtstr = dt.isoformat()
                    future_dtstr = (dt + timedelta(hours=step)).isoformat()
                    print(f"Predicting from {dtstr} to {future_dtstr}")
                    t0 = time.perf_counter()
                    input_surface_fp, input_upper_fp = predict(
                        input_surface_fp, input_upper_fp, step_mode=step
                    )
                    t1 = time.perf_counter()
                    print(f"Done. Time elapsed: {t1 - t0:.2f}s")
                    timestamp += interval
                    forward_records.append(step)
                break  # 当找到适合的步长并处理后，跳出当前循环进入下一个循环

    print("All done.")

    return {
        "surface_fp": input_surface_fp,
        "upper_fp": input_upper_fp,
        "forward_records": forward_records,
    }


if __name__ == "__main__":
    init_timestamp = int(sys.argv[1])
    target_timestamp = int(sys.argv[2])

    iteratively_predict(init_timestamp, target_timestamp)
