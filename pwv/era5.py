import os

import cdsapi
import arrow

URL = "https://cds.climate.copernicus.eu/api/v2"


class ERA5:
    def __init__(self, api_key) -> None:
        self.api_key = api_key
        self.client = cdsapi.Client(key=self.api_key, url=URL)

    def get_latest_datetime_of_cds(self):
        nowhour = arrow.now(tz="utc").floor("hour")
        latest_cds_hour = nowhour.shift(days=-5)

        return latest_cds_hour

    def fetch_latest_surface(self, savepath="."):
        latest_cds_hour = self.get_latest_datetime_of_cds()
        year = latest_cds_hour.year
        month = latest_cds_hour.month
        day = latest_cds_hour.day
        hour = latest_cds_hour.hour

        savefp = os.path.join(savepath, latest_cds_hour.strftime("surface_%Y%m%d%H.nc"))
        self.client.retrieve(
            "reanalysis-era5-single-levels",
            {
                "product_type": "reanalysis",
                "format": "netcdf",
                "variable": [
                    "10m_u_component_of_wind",
                    "10m_v_component_of_wind",
                    "2m_temperature",
                    "mean_sea_level_pressure",
                ],
                "year": f"{year}",
                "month": f"{month:02}",
                "day": f"{day:02}",
                "time": f"{hour:02}:00",
            },
            savefp,
        )

        return savefp, latest_cds_hour

    def fetch_latest_upper(self, savepath="."):
        latest_cds_hour = self.get_latest_datetime_of_cds()
        year = latest_cds_hour.year
        month = latest_cds_hour.month
        day = latest_cds_hour.day
        hour = latest_cds_hour.hour

        savefp = os.path.join(savepath, latest_cds_hour.strftime("upper_%Y%m%d%H.nc"))
        self.client.retrieve(
            "reanalysis-era5-pressure-levels",
            {
                "product_type": "reanalysis",
                "format": "netcdf",
                "pressure_level": [
                    "50",
                    "100",
                    "150",
                    "200",
                    "250",
                    "300",
                    "400",
                    "500",
                    "600",
                    "700",
                    "850",
                    "925",
                    "1000",
                ],
                "variable": [
                    "geopotential",
                    "specific_humidity",
                    "temperature",
                    "u_component_of_wind",
                    "v_component_of_wind",
                ],
                "year": f"{year}",
                "month": f"{month:02}",
                "day": f"{day:02}",
                "time": f"{hour:02}:00",
            },
            savefp,
        )

        return savefp, latest_cds_hour


if __name__ == "__main__":
    era5 = ERA5("")  # 输入你自己的 CDS API Key
    era5.fetch_latest_surface()
    era5.fetch_latest_upper()
