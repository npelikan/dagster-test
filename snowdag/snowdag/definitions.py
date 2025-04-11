from dagster import (
    Definitions,
    define_asset_job,
    build_schedule_from_partitioned_job,
    DefaultScheduleStatus,
    ConfigurableResource,
    EnvVar,
)
from dagster_aws.s3 import S3Resource

from . import minio  # noqa: TID252
from . import postgres

snotel_sites = {
    "366:UT:SNTL": "Brighton, UT",
    "628:UT:SNTL": "Mill D, UT",
    "766:UT:SNTL": "Snowbird, UT",
    "1308:UT:SNTL": "Atwater Plot, UT",
    "814:UT:SNTL": "Thaynes Canyon, UT",
    "572:UT:SNTL": "La Sal Mountain, UT",
    "1304:UT:SNTL": "Gold Basin, UT",
    "1269:UT:SNTL": "Mt Pennell, UT",
    "396:UT:SNTL": "Chepeta Lake, UT",
    "383:UT:SNTL": "Camp Jackson, UT",
}
wx_stations = {
    "C99": "Canyons - 9990",
    "REY": "Reynolds Peak",
    "UTCDF": "Cardiff Trailhead",
    "PC056": "Brighton",
    "IFF": "Cardiff Peak",
    "PC064": "Albion Basin",
    "AMB": "Alta - Baldy",
    # "HP": "Hidden Peak",
    "CDYBK": "Canyons - Daybreak",
    "LSL": "La Sal",
    "GOLDB": "Gold Basin",
    "NLPU1": "North Long Point (Abajos)",
    "SOLHP": "Solitude - Honeycomb Peak",
    "SOLSM": "Solitude - Summit",
    "BRC": "Brighton - Crest",
    
}


def create_snotel_assets(code, name):
    minio_asset = minio.build_snotel_station(code, name)
    postgres_asset = postgres.snotel_to_postgres(code, minio_asset)
    return minio_asset, postgres_asset

snotel_assets = [
    x for code, name in snotel_sites.items() for x in create_snotel_assets(code, name)
]

def create_wx_assets(code, name):
    minio_asset = minio.build_wx_station(code, name)
    postgres_asset = postgres.wx_to_postgres(code, minio_asset)
    return minio_asset, postgres_asset

wx_assets = [
    x for code, name in wx_stations.items() for x in create_wx_assets(code, name)
]

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


class PostgreSQL(ConfigurableResource):
    user: str
    password: str
    host: str
    port: str
    db: str


defs = Definitions(
    assets=snotel_assets + wx_assets,
    resources={
        "s3": S3Resource(
            region_name="us-west-2",
            endpoint_url="http://minio.minio.svc.cluster.local:9000",
            aws_access_key_id=EnvVar("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=EnvVar("AWS_SECRET_ACCESS_KEY"),
        ),
        "synoptic": SynopticAPI(api_key=EnvVar("WX_API_KEY")),
        "postgres": PostgreSQL(
            user=EnvVar("POSTGRES_USER"),
            password=EnvVar("POSTGRES_PASS"),
            host="datawarehouse-postgresql.datawarehouse.svc.cluster.local",
            port="5432",
            db="snow_data"
        )
    },
    schedules=(snotel_schedule, wx_schedule),
)
