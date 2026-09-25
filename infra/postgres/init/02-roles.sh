#!/usr/bin/env bash
# Cria as roles do sistema (ADR 0002):
#   app_owner  -> dono do schema; usado somente pelas migrações (Alembic)
#   app_user   -> grupo sem login que recebe os privilégios de DML
#   app_api    -> login da API/workers, membro de app_user, sujeito a RLS
set -euo pipefail

: "${APP_OWNER_PASSWORD:?defina APP_OWNER_PASSWORD}"
: "${APP_API_PASSWORD:?defina APP_API_PASSWORD}"

psql -v ON_ERROR_STOP=1 \
  --username "${POSTGRES_USER}" --dbname "${POSTGRES_DB}" \
  -v owner_pw="${APP_OWNER_PASSWORD}" -v api_pw="${APP_API_PASSWORD}" \
  -v db="${POSTGRES_DB}" <<'SQL'
CREATE ROLE app_owner LOGIN PASSWORD :'owner_pw' NOSUPERUSER NOBYPASSRLS;
CREATE ROLE app_user  NOLOGIN NOSUPERUSER NOBYPASSRLS;
CREATE ROLE app_api   LOGIN PASSWORD :'api_pw' NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE IN ROLE app_user;

ALTER DATABASE :"db" OWNER TO app_owner;
ALTER SCHEMA public OWNER TO app_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_user;

-- Tudo o que o app_owner criar fica acessível (apenas DML) ao app_user.
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app_user;
SQL
