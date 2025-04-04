import psycopg
import pandas as pd
import io
import uuid

from dagster import (
    AssetsDefinition,
    asset,
    AssetExecutionContext,
    DailyPartitionsDefinition,
    ConfigurableResource,
)
from dagster_aws.s3 import S3Resource

from ..config import S3_BUCKET

def snotel_to_postgres(code: str, dep: AssetsDefinition) -> AssetsDefinition:
    friendly_name = f"{code.replace(':', '_')}"
    
    @asset(
        partitions_def=DailyPartitionsDefinition(
            start_date="2024-11-01", timezone="America/Denver"
        ),
        name=f"snotel_{friendly_name}-postgres",
        deps=[dep],
    )
    def _asset(context: AssetExecutionContext, s3: S3Resource, postgres: ConfigurableResource):
        # read file from s3
        s3_prefix = f"snotel_data/{friendly_name}/"
        s3_filename = f"{s3_prefix}{context.partition_key}.parquet"
        s3_client = s3.get_client()

        obj = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_filename)
        sdf = pd.read_parquet(io.BytesIO(obj['Body'].read()))

        ## munge file to postgres format
        # rename columns
        sdf = sdf.rename(columns = {
            "siteCode": "site_code",
            "dateTime": "date_time",
            "TOBS": "air_temp",
            "SNWD": "snow_depth",
            "WTEQ": "swe",
            "siteName": "site_name"
        })

        # add timezone to date_time
        sdf["date_time"] = sdf["date_time"].dt.tz_localize("America/Denver")

        # convert farenheit to celsius
        sdf["air_temp"] = sdf["air_temp"].apply(lambda x: (x - 32) * 5/9)

        conn_string = f"postgresql://{postgres.user}:{postgres.password}@{postgres.host}:{postgres.port}/{postgres.db}"
        
        temp_table_name = f'snotel_temp_{str(uuid.uuid4())[:8]}'
        # write to temp table
        sdf.to_sql(
            name=temp_table_name, 
            con=conn_string, 
            index=False, 
            if_exists='replace'
        )

        conn = psycopg.connect(conn_string)

        with conn.cursor() as cur:
            cur.execute(f"ALTER TABLE {temp_table_name} SET TEMPORARY")

            cur.execute(
                f"""
                INSERT INTO snotel SELECT * FROM {temp_table_name}
                ON CONFLICT DO NOTHING;
                """
            )
            conn.commit()

        conn.close()

    return _asset