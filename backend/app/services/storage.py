"""Acesso ao storage S3-compatible (RustFS em dev, AWS S3 em produção).

O arquivo do usuário NUNCA passa pela API: o navegador envia direto ao storage
com uma URL pré-assinada que fixa tipo e tamanho (qualquer divergência → 403 do
próprio storage). A API só lê o objeto no worker de validação.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import TYPE_CHECKING

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

log = get_logger("storage")


def _client(settings: Settings, endpoint: str | None) -> "S3Client":
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            connect_timeout=2,
            read_timeout=10,
            retries={"max_attempts": 2},
        ),
    )


@lru_cache
def get_s3_client() -> "S3Client":
    settings = get_settings()
    return _client(settings, settings.s3_endpoint_url)


@lru_cache
def _public_client() -> "S3Client":
    """Cliente usado só para ASSINAR URLs com o host que o navegador enxerga."""
    settings = get_settings()
    return _client(settings, settings.s3_public_endpoint_url or settings.s3_endpoint_url)


class ObjectTooLargeError(Exception):
    pass


@dataclass(frozen=True)
class ObjectInfo:
    size: int
    content_type: str | None


class ObjectStorage:
    def __init__(self, bucket: str) -> None:
        self.bucket = bucket
        self.s3 = get_s3_client()
        self.signer = _public_client()

    def presign_put(self, key: str, content_type: str, content_length: int, ttl_s: int) -> str:
        url: str = self.signer.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ContentType": content_type,
                "ContentLength": content_length,
            },
            ExpiresIn=ttl_s,
        )
        return url

    def presign_get(
        self, key: str, ttl_s: int, *, filename: str | None = None, inline: bool = False
    ) -> str:
        disposition = "inline" if inline else "attachment"
        if filename:
            safe = filename.replace('"', "").replace("\\", "")
            disposition += f'; filename="{safe}"'
        url: str = self.signer.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key, "ResponseContentDisposition": disposition},
            ExpiresIn=ttl_s,
        )
        return url

    def head(self, key: str) -> ObjectInfo | None:
        try:
            r = self.s3.head_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise
        return ObjectInfo(size=r["ContentLength"], content_type=r.get("ContentType"))

    def read(self, key: str, max_bytes: int) -> bytes:
        """Lê o objeto inteiro, recusando se passar do limite (defesa extra além da URL)."""
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        if obj["ContentLength"] > max_bytes:
            raise ObjectTooLargeError(key)
        data: bytes = obj["Body"].read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ObjectTooLargeError(key)
        return data

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def lock(self, key: str, meses: int) -> bool:
        """Retenção (Object Lock) no original: ninguém apaga/sobrescreve até a data (RNF02)."""
        ate = datetime.now(UTC) + timedelta(days=30 * meses)
        try:
            self.s3.put_object_retention(
                Bucket=self.bucket,
                Key=key,
                Retention={"Mode": "GOVERNANCE", "RetainUntilDate": ate},
            )
        except ClientError as exc:
            log.warning("object_lock_indisponivel", key=key, error=str(exc))
            return False
        return True

    def quarantine(self, key: str) -> str:
        """Move um arquivo reprovado para quarentena/ (fora do caminho normal)."""
        destino = f"quarentena/{key}"
        self.s3.copy_object(
            Bucket=self.bucket, Key=destino, CopySource={"Bucket": self.bucket, "Key": key}
        )
        self.s3.delete_object(Bucket=self.bucket, Key=key)
        return destino


def comprovantes_storage() -> ObjectStorage:
    return ObjectStorage(get_settings().s3_bucket_comprovantes)
