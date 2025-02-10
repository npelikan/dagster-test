def get_s3_objects(s3_client, s3_bucket: str, s3_prefix: str) -> list[str]:
    _truncated = True
    keys = []
    continuation_token = ""

    while _truncated:
        objects = s3_client.list_objects_v2(
            Bucket=s3_bucket,
            MaxKeys=1000,
            Prefix=s3_prefix,
            ContinuationToken=continuation_token,
        )
        keys = keys + objects["Contents"]
        _truncated = objects["IsTruncated"]
        continuation_token = objects["NextContinuationToken"]

    return keys
