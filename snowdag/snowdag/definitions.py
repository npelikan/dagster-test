from dagster import (
    Definitions,
    define_asset_job,
    build_schedule_from_partitioned_job,
    DefaultScheduleStatus,
    ConfigurableResource,
    EnvVar
)
from dagster_aws.s3 import S3Resource
import os

from . import snotel, wx  # noqa: TID252

snotel_sites = {
    "366:UT:SNTL": "Brighton, UT",
    "628:UT:SNTL": "Mill D, UT",
    "766:UT:SNTL": "Snowbird, UT",
    "1308:UT:SNTL": "Atwater Plot, UT",
    "814:UT:SNTL": "Thaynes Canyon, UT",
}
wx_stations = {
    "C99": "Canyons - 9990",
    "REY": "Reynolds Peak",
    "UTCDF": "Cardiff Trailhead",
    "PC056": "Brighton",
    "IFF": "Cardiff Peak",
    "PC064": "Albion Basin",
    "AMB": "Alta - Baldy",
    "HP": "Hidden Peak",
    "CDYBK": "Canyons - Daybreak",
}

snotel_assets = [
    snotel.build_snotel_station(code, name) for code, name in snotel_sites.items()
]

wx_assets = [wx.build_wx_station(code, name) for code, name in wx_stations.items()]

snotel_schedule = build_schedule_from_partitioned_job(
    define_asset_job("snotel_download", selection=snotel_assets),
    default_status=DefaultScheduleStatus.RUNNING,
)

wx_schedule = build_schedule_from_partitioned_job(
    define_asset_job("wx_station_download", selection=wx_assets),
    hour_of_day=1,
    minute_of_hour=30,
    default_status=DefaultScheduleStatus.RUNNING,
)


class SynopticAPI(ConfigurableResource):
    api_key: str


defs = Definitions(
    assets=snotel_assets + wx_assets,
    resources={
        "s3": S3Resource(
            region_name="us-west-2",
            endpoint_url="http://minio.minio.svc.cluster.local:9000",
            aws_access_key_id=EnvVar("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=EnvVar("AWS_SECRET_ACCESS_KEY"),
        ),
        "synoptic": SynopticAPI(api_key=EnvVar("WX_API_KEY"))
    },
    schedules=(snotel_schedule, wx_schedule),
)
