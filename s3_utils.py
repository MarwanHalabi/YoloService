import os
import boto3
from botocore.exceptions import ClientError

# Bucket and region configuration
AWS_S3_BUCKET = os.getenv("S3_BUCKET") or os.getenv("AWS_S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")

def _s3_client():
    # Use default credential chain (IAM role, env, shared config)
    session = boto3.session.Session(region_name=AWS_REGION)
    return session.client("s3")

def download_file(bucket: str, key: str, dest_path: str):
    s3 = _s3_client()
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    s3.download_file(bucket, key, dest_path)

def upload_file(bucket: str, key: str, src_path: str):
    s3 = _s3_client()
    s3.upload_file(src_path, bucket, key)

def copy_object(bucket: str, source_key: str, dest_key: str):
    s3 = _s3_client()
    copy_source = {"Bucket": bucket, "Key": source_key}
    s3.copy(copy_source, bucket, dest_key)

def s3_key_exists(bucket: str, key: str) -> bool:
    s3 = _s3_client()
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey", "NotFound"):
            return False
        raise

