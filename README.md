# pangu-weather-verify

[![cc-by-nc-sa-shield](https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc-sa/4.0/)

本项目将提供一套简洁有效的流程来对盘古气象模型以及 ECMWF、GFS 的预报效果进行检验对比，以验证盘古模型在真实气象场中的预报效果。

## 背景
根据华为盘古气象模型团队在 [arxiv](https://arxiv.org/abs/2211.02556) 和 [nature](https://www.nature.com/articles/s41586-023-06185-3) 发表的论文显示，其模型准确率已经超越了 ECMWF 的 IFS 模型，但是这些论文中的检验结果都是在人工构造的理想化气象场中（ERA5）进行的，因此我们需要在真实的气象观测场中对盘古气象模型进行检验，以验证其在真实气象场中的准确率。

得益于盘古气象模型团队将其模型开源，我们可以在自己个人电脑上搭建盘古气象模型进行预报检验，[开源仓库地址](https://github.com/198808xc/Pangu-Weather)。

## 数据来源
本项目的所有数据均来源于互联网上的公开数据集，且数据获取的方式合理合法、公开透明。
### SURF 观测站数据
本项目将使用中国大陆地区在[中央气象台网站](http://www.nmc.cn/)上公布的2167个站点的观测数据作为检验的真值。观测站点信息来自于[中国气象数据网](http://data.cma.cn/Market/Detail/code/A.0012.0001/type/0.html)，[原始站点表格下载地址](http://image.data.cma.cn/static/doc/market/China_SURF_Station.xlsx)，在项目中站点列表（csv文件）对原始列表做了一些经纬度表示方法的转换，主要是将度分秒表示法转换为十进制表示法，以便于后续处理。本项目以爬虫的方式抓取中央气象台网站上的观测站点数据，受网络环境影响，在实际运行中抓取的数据无法保证100%完整，会有个别站点数据缺失，属于正常现象。

### ERA5 再分析数据
本项目使用的 ERA5 再分析数据作为盘古模型推理的原始输入数据，ERA5 数据集是免费公开的，但获取数据需要用户在 [cds](https://cds.climate.copernicus.eu/#!/home) 网站上[注册账号](https://cds.climate.copernicus.eu/user/register)，并[获取自己的 api_key](https://cds.climate.copernicus.eu/api-how-to) 才能进行下载，本项目不提供测试 api_key。

### ECMWF 预报数据
ECMWF 的预报产品有多种品类，本项目使用的是其中对外免费公开的实时预报数据集，获取渠道可以参考[这里](https://confluence.ecmwf.int/display/DAC/ECMWF+open+data:+real-time+forecasts)。本项目中 ECMWF 的实时预报数据作为盘古模型的对比预报数据（陪跑），用于对比盘古模型的预报效果。

### GFS 预报数据
我们使用 0.25 度分辨率的 GFS 预报数据作为另一个陪跑的对比预报，GFS 的获取链接：[这里](https://nomads.ncep.noaa.gov/gribfilter.php?ds=gfs_0p25_1hr)。

## 使用方法
本项目不作为 pip 包分发，您需要将本项目代码克隆到本地。
```bash
$ git clone https://github.com/Clarmy/pangu-weather-verify.git
```
建议使用 conda 创建虚拟环境：
```bash
$ conda create -n pwv -y python=3.8
$ conda activate pwv
```
有一些包我们从 conda 进行安装会方便一些：
```bash
$ conda install -y -c conda-forge pygrib
```
其他包我们可以直接使用 pip 进行批量安装：
```bash
$ pip install -r requirements/cpu.txt # CPU 版本
$ pip install -r requirements/gpu.txt # GPU 版本
```
将本项目以包的形式安装：
```bash
$ python setup.py install
```

配置 cds 的 api_key，先将自己的 api_key 填入 `pwv/secret.toml.template` 文件中：
```toml
cds_api_key = 'xxxxx:d76c469b-xxxx-yyyy-zzzz-fac92ea9f5f8'
```
然后将 `pwv/secret.toml.template` 改名为 `pwv/secret.toml` 即可完成配置。

下载模型文件：
* pangu_weather_1.onnx: [Google云盘](https://drive.google.com/file/d/1fg5jkiN_5dHzKb-5H9Aw4MOmfILmeY-S/view?usp=share_link)/[百度网盘](https://pan.baidu.com/s/1M7SAigVsCSH8hpw6DE8TDQ?pwd=ie0h)
* pangu_weather_3.onnx: [Google云盘](https://drive.google.com/file/d/1EdoLlAXqE9iZLt9Ej9i-JW9LTJ9Jtewt/view?usp=share_link)/[百度网盘](https://pan.baidu.com/s/197fZsoiCqZYzKwM7tyRrfg?pwd=gmcl)
* pangu_weather_6.onnx: [Google云盘](https://drive.google.com/file/d/1a4XTktkZa5GCtjQxDJb_fNaqTAUiEJu4/view?usp=share_link)/[百度网盘](https://pan.baidu.com/s/1q7IB7tNjqIwoGC7KVMPn4w?pwd=vxq3)
* pangu_weather_24.onnx: [Google云盘](https://drive.google.com/file/d/1lweQlxcn9fG0zKNW8ne1Khr9ehRTI6HP/view?usp=share_link)/[百度网盘](https://pan.baidu.com/s/179q2gkz2BrsOR6g3yfTVQg?pwd=eajy)

我们需要将模型文件存放在 `pwv/static` 目录下，`static` 内的文件结构如下：
```bash
.
├── pangu_weather_1.onnx
├── pangu_weather_24.onnx
├── pangu_weather_3.onnx
├── pangu_weather_6.onnx
└── station_info.csv
```

如果您只想做一次测评，可以执行任务：
```bash
$ python pwv/main.py
```
剩下的交给时间即可，最终结果在当前目录会新建一个 `resullts` 的目录，目录内生成两个文件: `compare-*.csv` 和 `verification_results-*.json`，其中 `compare-*.csv` 存储的是三套预报以及观测数据在每个观测站点上的对比列表。`verification_results-*.json` 存储的是每个观测站点上的检验指标结果。

如果您想每小时做一次测评，可以执行任务：
```bash
$ python scheduler.py
```

以下是一次测评的结果 `verification_results-*.json` 文件的内容：
```json
{
    "pangu": {
        "temperature": {
            "rmse": 2.7101,
            "mae": 2.0384,
            "accuracy_ratio_within_1deg": 32.3782,
            "accuracy_ratio_within_2deg": 59.0735,
            "accuracy_ratio_within_3deg": 78.51
        },
        "wind": {
            "speed_rmse": 1.7176,
            "speed_mae": 1.2681,
            "speed_accuracy_ratio_within_1ms": 51.1939,
            "speed_accuracy_ratio_within_2ms": 79.6084,
            "speed_accuracy_ratio_within_3ms": 93.2187,
            "scale_stronger_ratio": 36.0554,
            "scale_weaker_ratio": 25.5014,
            "scale_accuracy": 38.4432,
            "speed_score": 0.7185,
            "direction_score": 0.4326
        },
        "init_time": "2023-07-11T16:00:00+00:00",
        "forecast_hour_delta": 119
    },
    "ecmwf": {
        "temperature": {
            "rmse": 2.6694,
            "mae": 2.0125,
            "accuracy_ratio_within_1deg": 31.7574,
            "accuracy_ratio_within_2deg": 60.9838,
            "accuracy_ratio_within_3deg": 78.7966
        },
        "wind": {
            "speed_rmse": 1.6073,
            "speed_mae": 1.1812,
            "speed_accuracy_ratio_within_1ms": 52.9131,
            "speed_accuracy_ratio_within_2ms": 84.4317,
            "speed_accuracy_ratio_within_3ms": 94.2216,
            "scale_stronger_ratio": 34.8615,
            "scale_weaker_ratio": 24.4508,
            "scale_accuracy": 40.9742,
            "speed_score": 0.7326,
            "direction_score": 0.456
        },
        "init_time": "2023-07-16T00:00:00+00:00",
        "forecast_hour_delta": 15
    },
    "gfs": {
        "temperature": {
            "rmse": 3.2771,
            "mae": 2.5773,
            "accuracy_ratio_within_1deg": 22.6361,
            "accuracy_ratio_within_2deg": 46.4183,
            "accuracy_ratio_within_3deg": 66.8099
        },
        "wind": {
            "speed_rmse": 1.6419,
            "speed_mae": 1.2061,
            "speed_accuracy_ratio_within_1ms": 54.0115,
            "speed_accuracy_ratio_within_2ms": 81.4231,
            "speed_accuracy_ratio_within_3ms": 93.362,
            "scale_stronger_ratio": 35.9121,
            "scale_weaker_ratio": 21.5377,
            "scale_accuracy": 42.5979,
            "speed_score": 0.7402,
            "direction_score": 0.4563
        },
        "init_time": "2023-07-16T12:00:00+00:00",
        "forecast_hour_delta": 3
    },
    "observation_datetime": "2023-07-16T15:00:00+00:00"
}
```
