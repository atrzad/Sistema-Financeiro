"""Configuração da aplicação, carregada de variáveis de ambiente.

A validação acontece na inicialização: se faltar uma variável obrigatória,
o processo falha imediatamente com uma mensagem clara (fail fast).
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Environment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_ROOT_ENV, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = Environment.LOCAL
    log_level: str = "INFO"

    # Conexão da API/workers (role app_api, sujeita a RLS)
    database_url: PostgresDsn
    # Conexão das migrações (role app_owner). Nunca usada pela API.
    database_url_owner: PostgresDsn | None = None

    redis_url: RedisDsn

    s3_endpoint_url: str | None = None  # None = AWS S3
    s3_access_key: str
    s3_secret_key: str
    s3_region: str = "us-east-1"
    s3_bucket_comprovantes: str = "comprovantes"
    s3_bucket_exports: str = "exports"

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    health_check_timeout_s: float = 2.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @property
    def is_local(self) -> bool:
        return self.environment in (Environment.LOCAL, Environment.TEST)


@lru_cache
def get_settings() -> Settings:
    return Settings()
