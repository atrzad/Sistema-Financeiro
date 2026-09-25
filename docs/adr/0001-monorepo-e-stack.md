# ADR 0001 — Monorepo e stack tecnológica

- **Status:** aceito
- **Data:** 2026-09-25

## Contexto
Projeto desenvolvido por uma pessoa, com backend, web e mobile compartilhando o mesmo contrato de API. É preciso minimizar atrito de versionamento entre as partes e manter a stack definida no plano original (FastAPI, PostgreSQL, Celery/Redis, S3, React, React Native).

## Decisão
- **Monorepo** único com `backend/`, `web/`, `mobile/`, `infra/`, `docs/`.
- Backend: Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic; gerenciador `uv`.
- Frontend: React + TypeScript + Vite; `pnpm` com workspace englobando `web/` e `mobile/` e um pacote `packages/api-client` gerado do OpenAPI.
- Mobile: React Native via **Expo (dev build)**, para reaproveitar TypeScript e o cliente de API, com módulo nativo do ML Kit Document Scanner.
- CI no GitHub Actions com jobs condicionados por caminho alterado.

## Consequências
- (+) Uma mudança de contrato atualiza API, web e mobile num único PR.
- (+) Tipos gerados do OpenAPI eliminam divergência manual.
- (−) CI precisa de filtros por caminho para não ficar lento.
- (−) Expo dev build exige EAS ou build local para o módulo nativo do scanner.
