"""Backend checkpoint trên object storage S3-compatible (task 10.3).

Dùng cho Backblaze B2 (Thuận chọn ngày 7/11/2026 thay R2 trong spec dòng
215): endpoint là URL S3 của B2 (`https://s3.<region>.backblazeb2.com`),
khóa là application key của B2 (keyID + applicationKey, KHÔNG dùng master
key). Bucket phải tạo trước trong console B2 — store không tự tạo bucket.
"""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


class S3CheckpointStore:
    """CheckpointStore qua API S3 (boto3).

    `endpoint_url=None` thì dùng endpoint AWS mặc định — chỉ dùng trong
    test với mock S3; B2 thật bắt buộc phải có endpoint_url. `region_name`
    là region boto3 dùng để ký request (boto3 bắt buộc phải có region kể
    cả với endpoint tùy chỉnh); B2 chấp nhận `us-east-1` để ký. Khóa chỉ
    đi qua tham số khởi tạo (người gọi lấy từ Settings/env), không bao giờ
    đọc từ biến môi trường hay file ở đây (cổng `check_env_access`).
    """

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        access_key_id: str,
        secret_access_key: str,
        region_name: str = "us-east-1",
    ) -> None:
        """Mở client S3 cho `bucket`; chưa chạm mạng lúc khởi tạo."""
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region_name,
        )

    def put(self, key: str, data: bytes) -> None:
        """Ghi `data` vào `key` (ghi đè nếu khóa đã có)."""
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get(self, key: str) -> bytes | None:
        """Đọc bytes tại `key`; khóa chưa có thì `None`."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchKey":
                return None
            raise
        # Stub kiểu của botocore khai `StreamingBody.read()` trả `Any`;
        # ép về `bytes` cho rõ (đọc từ S3 luôn là bytes).
        return bytes(response["Body"].read())

    def list_keys(self, prefix: str) -> list[str]:
        """Mọi khóa bắt đầu bằng `prefix`, sắp xếp tăng dần."""
        keys: list[str] = []
        token: str | None = None
        while True:
            if token is None:
                page = self._client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
            else:
                page = self._client.list_objects_v2(
                    Bucket=self._bucket, Prefix=prefix, ContinuationToken=token
                )
            keys.extend(obj["Key"] for obj in page.get("Contents", ()))
            if not page.get("IsTruncated"):
                break
            token = page.get("NextContinuationToken")
            if token is None:
                break
        return sorted(keys)
