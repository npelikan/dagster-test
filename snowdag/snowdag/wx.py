import pandas as pd
import requests
import datetime
from dagster import (
    AssetsDefinition,
    asset,
    AssetExecutionContext,
    DailyPartitionsDefinition,
    ConfigurableResource,
)
from dagster_aws.s3 import S3Resource
from .config import S3_BUCKET
from .utils import get_s3_objects


def build_wx_station(code: str, name: str) -> AssetsDefinition:
    @asset(
        partitions_def=DailyPartitionsDefinition(start_date="2024-11-01"),
        name=f"wx_{code}",
    )
    def _asset(
        context: AssetExecutionContext, s3: S3Resource, synoptic: ConfigurableResource
    ):
        s3_prefix = f"wx_data/{code}/"
        s3_filename = f"{s3_prefix}{context.partition_key}.parquet"
        s3_client = s3.get_client()

        prefix_keys = get_s3_objects(
            s3_client=s3_client, s3_bucket=S3_BUCKET, s3_prefix=s3_prefix
        )

        # Exit if key already exists.
        if s3_filename in (x["Key"] for x in prefix_keys):
            return None

        grab_date = datetime.datetime.strptime(context.partition_key, "%Y-%m-%d")

        params = {
            "token": synoptic.api_key,  # access token
            "stid": [code],  # mesonet station id
            "start": (grab_date - datetime.timedelta(days=1)).strftime("%Y%m%d0000"),
            "end": grab_date.strftime("%Y%m%d0000"),
        }

        resp = requests.get(
            "https://api.synopticdata.com/v2/stations/timeseries", params=params
        )
        resp.raise_for_status()
        try:
            i = resp.json()["STATION"][0]
        except Exception as e:
            context.log.error(f"Received malformed JSON response: {resp.json()}")
            raise e

        df = pd.DataFrame(i["OBSERVATIONS"])
        df["date_time"] = pd.to_datetime(df["date_time"]).dt.tz_convert(
            tz="America/Denver"
        )
        df["station"] = i["NAME"]
        df["station_id"] = i["STID"]

        parquet_data = df.to_parquet(index=False)

        s3_client = s3.get_client()

        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=s3_filename,
            Body=parquet_data,
        )

    return _asset
