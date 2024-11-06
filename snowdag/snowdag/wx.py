import pandas as pd
import requests
import datetime
from dagster import (
    AssetsDefinition,
    asset,
    AssetExecutionContext,
    DailyPartitionsDefinition,
)
from dagster_aws.s3 import S3Resource
import os


def build_wx_station(code: str, name: str, s3: S3Resource) -> AssetsDefinition:
    @asset(
        partitions_def=DailyPartitionsDefinition(start_date="2023-10-01"),
        name=f"wx_{code}",
    )
    def _asset(context: AssetExecutionContext):
        grab_date = datetime.datetime.strptime(context.partition_key, "%Y-%m-%d")

        params = {
            "token": os.getenv("WX_API_KEY"),  # access token
            "stid": [code],  # mesonet station id
            "start": (grab_date - datetime.timedelta(days=1)).strftime("%Y%m%d0000"),
            "end": grab_date.strftime("%Y%m%d0000"),
        }

        resp = requests.get(
            "https://api.synopticdata.com/v2/stations/timeseries", params=params
        )
        resp.raise_for_status()
        i = resp.json()["STATION"][0]

        df = pd.DataFrame(i["OBSERVATIONS"])
        df["date_time"] = pd.to_datetime(df["date_time"]).dt.tz_convert(
            tz="America/Denver"
        )
        df["station"] = i["NAME"]
        df["station_id"] = i["STID"]

        parquet_data = df.to_parquet(index=False)

        s3_client = s3.get_client()

        s3_client.put_object(
            Bucket="snow-data",
            Key=f"wx_data/{context.partition_key}.parquet",
            Body=parquet_data,
        )

    return _asset
