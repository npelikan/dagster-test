# Upsert function for pandas to_sql with postgres
# https://stackoverflow.com/questions/1109061/insert-on-duplicate-update-in-postgresql/8702291#8702291
# https://www.postgresql.org/docs/devel/sql-insert.html#SQL-ON-CONFLICT
import pandas as pd
import sqlalchemy
import uuid
import io

from dagster import (
    AssetExecutionContext,
    SensorEvaluationContext,
    Config,
    DefaultSensorStatus,
    RunConfig,
    RunRequest,
    SkipReason,
    asset,
    sensor,
    define_asset_job,
    ConfigurableResource,
)
from dagster_aws.s3 import S3Resource
from dagster_aws.s3.sensor import get_s3_keys

from .config import S3_BUCKET


class ObjectConfig(Config):
    key: str


def upsert_df(df: pd.DataFrame, table_name: str, engine: sqlalchemy.engine.Engine):
    """Implements the equivalent of pd.DataFrame.to_sql(..., if_exists='update')
    (which does not exist). Creates or updates the db records based on the
    dataframe records.
    Conflicts to determine update are based on the dataframes index.
    This will set primary keys on the table equal to the index names
    1. Create a temp table from the dataframe
    2. Insert/update from temp table into table_name
    Returns: True if successful
    """

    # If the table does not exist, we should just use to_sql to create it
    with engine.connect() as connection:
        if not connection.execute(
            f"""SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE  table_schema = 'public'
                AND    table_name   = '{table_name}');
                """
        ).first()[0]:
            df.to_sql(table_name, engine)
            return True

    # If it already exists...
    temp_table_name = f"temp_{uuid.uuid4().hex[:6]}"
    df.to_sql(temp_table_name, engine, index=True)

    index = list(df.index.names)
    index_sql_txt = ", ".join([f'"{i}"' for i in index])
    columns = list(df.columns)
    headers = index + columns
    headers_sql_txt = ", ".join(
        [f'"{i}"' for i in headers]
    )  # index1, index2, ..., column 1, col2, ...

    # col1 = exluded.col1, col2=excluded.col2
    update_column_stmt = ", ".join([f'"{col}" = EXCLUDED."{col}"' for col in columns])

    # For the ON CONFLICT clause, postgres requires that the columns have unique constraint
    query_pk = f"""
    ALTER TABLE "{table_name}" ADD CONSTRAINT {table_name}_unique_constraint_for_upsert UNIQUE ({index_sql_txt});
    """
    try:
        with engine.connect() as connection:
            connection.execute(query_pk)
            connection.commit()
    except Exception as e:
        # relation "unique_constraint_for_upsert" already exists
        if not 'unique_constraint_for_upsert" already exists' in e.args[0]:
            raise e

    # Compose and execute upsert query
    query_upsert = f"""
    INSERT INTO "{table_name}" ({headers_sql_txt}) 
    SELECT {headers_sql_txt} FROM "{temp_table_name}"
    ON CONFLICT ({index_sql_txt}) DO UPDATE 
    SET {update_column_stmt};
    """
    with engine.connect() as connection:
        connection.execute(query_upsert)
        connection.execute(f'DROP TABLE "{temp_table_name}"')
        connection.commit()

    return True


@asset(op_tags={"dagster/concurrency_key": "database"})
def snow_postgres_write(
    context: AssetExecutionContext,
    config: ObjectConfig,
    s3: S3Resource,
    postgres: ConfigurableResource,
):
    s3 = context.resources.s3
    context.log.info(f"Reading {config.key}")
    table_name, station_id, _ = config.key.split("/")
    response = s3.get_object(Bucket=S3_BUCKET, Key=config.key)  # process object here
    parquet_content = response["Body"].read()

    postgres = context.resources.postgres
    df = pd.read_parquet(io.BytesIO(parquet_content))
    df["station_id"] = station_id
    engine = sqlalchemy.create_engine(
        f"postgresql+psycopg2://{postgres.user}:{postgres.password}@{postgres.host}/{postgres.db}"
    )
    upsert_df(df, table_name=table_name, engine=engine)


@sensor(
    target=snow_postgres_write,
    minimum_interval_seconds=5,
    default_status=DefaultSensorStatus.RUNNING,
)
def snow_postgres_sensor(context: SensorEvaluationContext, s3: S3Resource):
    latest_key = context.cursor or None
    unprocessed_object_keys = get_s3_keys(
        bucket=S3_BUCKET, since_key=latest_key, s3_session=s3.get_client()
    )

    for key in unprocessed_object_keys:
        yield RunRequest(
            run_key=key,
            run_config=RunConfig(ops={"snow_postgres_write": ObjectConfig(key=key)}),
        )

    if not unprocessed_object_keys:
        return SkipReason(f"No new s3 files found for bucket {S3_BUCKET}")

    last_key = unprocessed_object_keys[-1]
    context.update_cursor(last_key)
