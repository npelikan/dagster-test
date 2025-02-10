def get_s3_objects(s3_client, s3_bucket: str, s3_prefix: str) -> list[str]:

    keys = []

    objects = s3_client.list_objects_v2(
        Bucket=s3_bucket,
        MaxKeys=1000,
        Prefix=s3_prefix,
    )
    keys = keys + objects["Contents"]
    _truncated = objects["IsTruncated"]
    if _truncated:
        continuation_token = objects["NextContinuationToken"]
    else:
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
        if _truncated:
            continuation_token = objects["NextContinuationToken"]
        else:
            continuation_token = ""

    return keys
