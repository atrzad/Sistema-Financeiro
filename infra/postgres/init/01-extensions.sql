-- Executado uma única vez, na criação do volume, como superusuário.
CREATE EXTENSION IF NOT EXISTS pgcrypto;    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pg_trgm;     -- fuzzy match de fornecedor
CREATE EXTENSION IF NOT EXISTS btree_gist;  -- exclusão de faixas sobrepostas
CREATE EXTENSION IF NOT EXISTS unaccent;    -- normalização de nomes
