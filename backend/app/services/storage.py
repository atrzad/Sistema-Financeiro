"""Acesso ao storage S3-compatible (RustFS em dev, AWS S3 em produção)."""

from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config

from app.core.config import get_settings

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


@lru_cache
def get_s3_client() -> "S3Client":
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=2,
            read_timeout=5,
            retries={"max_attempts": 1},
        ),
    )
