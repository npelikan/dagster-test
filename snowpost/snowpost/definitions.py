from dagster import (
    Definitions,
    ConfigurableResource,
    EnvVar,
)
from dagster_aws.s3 import S3Resource

from . import postgresql  # noqa: TID252


class PostgreSQL(ConfigurableResource):
    user: str
    password: str
    host: str
    db: str


defs = Definitions(
    assets=[postgresql.snow_postgres_write],
    resources={
        "s3": S3Resource(
            region_name="us-west-2",
            endpoint_url="http://minio.minio.svc.cluster.local:9000",
            aws_access_key_id=EnvVar("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=EnvVar("AWS_SECRET_ACCESS_KEY"),
        ),
        "postgres": PostgreSQL(
            user=EnvVar("POSTGRES_USER"),
            password=EnvVar("POSTGRES_PASS"),
            host=EnvVar("POSTGRES_HOST"),
            db=EnvVar("POSTGRES_DB"),
        ),
    },
    sensors=[postgresql.snow_postgres_sensor],
)
