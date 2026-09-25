#!/usr/bin/env bash
# Banco separado para a suíte de testes (<POSTGRES_DB>_test), com a mesma
# configuração do banco principal. Os testes limpam tabelas livremente aqui,
# sem tocar nos dados de desenvolvimento.
set -euo pipefail

TEST_DB="${POSTGRES_DB}_test"

if psql -U "${POSTGRES_USER}" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '${TEST_DB}'" | grep -q 1; then
  echo "banco ${TEST_DB} já existe"
  exit 0
fi

psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d postgres -c "CREATE DATABASE \"${TEST_DB}\" OWNER app_owner"

psql -v ON_ERROR_STOP=1 -U "${POSTGRES_USER}" -d "${TEST_DB}" <<'SQL'
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS unaccent;

ALTER SCHEMA public OWNER TO app_owner;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO app_user;
SQL
echo "banco ${TEST_DB} criado"
