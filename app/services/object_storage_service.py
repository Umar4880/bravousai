from __future__ import annotations

from typing import BinaryIO

try:
    import boto3
    from botocore.exceptions import ClientError
except ModuleNotFoundError:  # pragma: no cover - exercised only when dependency is missing.
    boto3 = None

    class ClientError(Exception):
        pass

from app.core.config import setting


class ObjectStorageService:
    def __init__(self, client=None) -> None:
        if client is not None:
            self.client = client
            return

        if boto3 is None:
            raise RuntimeError("boto3 is required for object storage. Install boto3 to enable MinIO/S3 uploads.")

        self.client = boto3.client(
            "s3",
            endpoint_url=setting.OBJECT_STORAGE_ENDPOINT,
            aws_access_key_id=setting.OBJECT_STORAGE_ACCESS_KEY,
            aws_secret_access_key=setting.OBJECT_STORAGE_SECRET_KEY,
            region_name=setting.OBJECT_STORAGE_REGION,
        )

    def ensure_bucket_exists(self, bucket: str) -> None:
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError:
            self.client.create_bucket(Bucket=bucket)

    def upload_fileobj(self, fileobj: BinaryIO, bucket: str, key: str, content_type: str) -> None:
        self.ensure_bucket_exists(bucket)
        self.client.upload_fileobj(
            fileobj,
            bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )

    def get_object(self, bucket: str, key: str) -> bytes:
        response = self.client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            return body.read()
        finally:
            close = getattr(body, "close", None)
            if callable(close):
                close()

    def delete_object(self, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False
