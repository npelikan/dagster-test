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

def wx_to_postgres(code: str, dep: AssetsDefinition) -> AssetsDefinition:
    
    @asset(
        partitions_def=DailyPartitionsDefinition(
            start_date="2024-11-01"
        ),
        name=f"wx_{code}-postgres",
        deps=[dep],
    )
    def _asset(context: AssetExecutionContext, s3: S3Resource, postgres: ConfigurableResource):
        # read file from s3
        s3_prefix = f"wx_data/{code}/"
        s3_filename = f"{s3_prefix}{context.partition_key}.parquet"
        s3_client = s3.get_client()

        obj = s3_client.get_object(Bucket=S3_BUCKET, Key=s3_filename)
        wdf = pd.read_parquet(io.BytesIO(obj['Body'].read()))

        ## munge file to postgres format
        # rename and select columns
        rename_dict = {
            "station_id": "site_code",
            "date_time": "date_time",
            "air_temp_set_1": "air_temp",
            "relative_humidity_set_1": "relative_humidity",
            "wind_speed_set_1": "wind_speed",
            "wind_direction_set_1": "wind_direction",
            "wind_gust_set_1": "wind_gust"
        }

        wdf = wdf[list(rename_dict.keys())].rename(columns=rename_dict)
        wdf

        conn_string = f"postgresql://{postgres.user}:{postgres.password}@{postgres.host}:{postgres.port}/{postgres.db}"
        
        temp_table_name = f'wx_temp_{str(uuid.uuid4())[:8]}'
        # write to temp table
        wdf.to_sql(
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
                INSERT INTO wx SELECT * FROM {temp_table_name}
                ON CONFLICT DO NOTHING;
                """
            )
            conn.commit()

        conn.close()

    return _asset