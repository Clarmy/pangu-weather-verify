# pangu-weather-verify
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
