"""Configuração da aplicação, carregada de variáveis de ambiente.

A validação acontece na inicialização: se faltar uma variável obrigatória,
o processo falha imediatamente com uma mensagem clara (fail fast).
"""

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator
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
    # Endereço do storage visto pelo NAVEGADOR (URLs pré-assinadas). Em Docker, a API
    # fala com "storage:9000", mas o navegador precisa de "localhost:9000".
    s3_public_endpoint_url: str | None = None
    s3_access_key: str
    s3_secret_key: str
    s3_region: str = "us-east-1"
    s3_bucket_comprovantes: str = "comprovantes"
    s3_bucket_exports: str = "exports"

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    health_check_timeout_s: float = 2.0

    # --- Autenticação (Sprint 01) ---
    jwt_secret: SecretStr = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    cookie_secure: bool = True
    login_max_failures: int = 5
    login_failure_window_s: int = 15 * 60

    # --- Upload de comprovantes (Sprint 03, RNF07/RNF08) ---
    upload_max_arquivos: int = 10
    upload_max_bytes_arquivo: int = 10 * 1024 * 1024
    upload_max_bytes_lote: int = 60 * 1024 * 1024
    upload_max_paginas_pdf: int = 50
    upload_url_ttl_s: int = 15 * 60
    download_url_ttl_s: int = 5 * 60

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
