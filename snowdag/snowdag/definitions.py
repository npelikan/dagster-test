from dagster import Definitions, load_assets_from_modules
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

defs = Definitions(
    assets=[
        snotel.build_snotel_station(code, name) for code, name in snotel_sites.items()
    ]
    + [wx.build_wx_station(code, name) for code, name in wx_stations.items()],
    resources={
        "s3": S3Resource(
            region_name="us-west-2",
            endpoint_url="minio.minio.svc.cluster.local:9000",
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    },
)
