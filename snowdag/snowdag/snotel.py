import pandas as pd
import zeep
from functools import reduce
import requests
import os
from pathlib import Path
from dagster import (
    AssetsDefinition,
    asset,
    AssetExecutionContext,
    DailyPartitionsDefinition,
)
import datetime
from dagster_aws.s3 import S3Resource


def filter_valdict(d):
    return {k: v for k, v in d.items() if k in ("dateTime", "value")}


def process_site(i, sensor_code):
    i = zeep.helpers.serialize_object(i)
    df = pd.DataFrame.from_records(filter_valdict(x) for x in i["values"])

    if df.shape[0] == 0:
        return None

    df["siteCode"] = i["stationTriplet"]
    df["dateTime"] = pd.to_datetime(df["dateTime"])
    df = df.set_index(["siteCode", "dateTime"])
    df["value"] = df["value"].astype(float)
    df = df.rename(columns={"value": sensor_code})
    return df


def get_single_sensor_data(
    snotel_client, site_codes, sensor_code, start_date, end_date
):
    resp = snotel_client.service.getHourlyData(
        stationTriplets=site_codes,
        elementCd=sensor_code,
        ordinal=1,
        beginDate=start_date,
        endDate=end_date,
    )
    sites = [process_site(x, sensor_code=sensor_code) for x in resp]
    return pd.concat((x for x in sites if x is not None))


def get_snotel_data(snotel_client, site_codes, sensor_codes, start_date, end_date):
    dfl = (
        get_single_sensor_data(
            snotel_client,
            sensor_code=x,
            site_codes=site_codes,
            start_date=start_date,
            end_date=end_date,
        )
        for x in sensor_codes
    )
    df = reduce(lambda l, r: pd.merge(l, r, left_index=True, right_index=True), dfl)
    for sensor_code in sensor_codes:
        if sensor_code not in df.columns:
            df[sensor_code] = 0
    return df


def build_snotel_station(code: str, name: str) -> AssetsDefinition:
    friendly_name = code.replace(":", "_")

    @asset(
        partitions_def=DailyPartitionsDefinition(start_date="2023-10-01"),
        name=f"snotel_{friendly_name}",
    )
    def _asset(context: AssetExecutionContext, s3: S3Resource):
        client = zeep.Client(
            "https://wcc.sc.egov.usda.gov/awdbWebService/services?WSDL"
        )
        grab_date = datetime.datetime.strptime(context.partition_key, "%Y-%m-%d")

        df = get_snotel_data(
            client,
            site_codes=[code],
            sensor_codes=["TOBS", "SNWD", "WTEQ"],
            start_date=(grab_date - datetime.timedelta(days=1)).strftime(
                "%Y-%m-%d %H:00:00"
            ),
            end_date=grab_date.strftime("%Y-%m-%d %H:00:00"),
        ).reset_index()

        df["siteName"] = name
        df = df.reset_index()
        df = df.drop(columns="index")

        parquet_data = df.to_parquet(index=False)

        s3_client = s3.get_client()

        s3_client.put_object(
            Bucket="snow-data",
            Key=f"wx_data/{context.partition_key}.parquet",
            Body=parquet_data,
        )

    return _asset
