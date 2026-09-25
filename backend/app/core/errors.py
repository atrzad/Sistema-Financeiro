"""Erros no formato RFC 9457 (Problem Details) — ver docs/convencoes.md."""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"

_TITLES = {
    400: "Requisição inválida",
    401: "Não autenticado",
    403: "Acesso negado",
    404: "Não encontrado",
    409: "Conflito",
    412: "Pré-condição falhou",
    422: "Dados inválidos",
    429: "Muitas tentativas",
}


class ProblemError(Exception):
    """Erro de negócio com status HTTP e mensagem para o usuário."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        title: str | None = None,
        type_: str = "about:blank",
        headers: dict[str, str] | None = None,
        **extra: Any,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.title = title or _TITLES.get(status_code, "Erro")
        self.type = type_
        self.headers = headers
        self.extra = extra


def problem_response(
    request: Request,
    status_code: int,
    detail: str | None,
    *,
    title: str | None = None,
    type_: str = "about:blank",
    headers: dict[str, str] | None = None,
    **extra: Any,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": type_,
        "title": title or _TITLES.get(status_code, "Erro"),
        "status": status_code,
        "instance": request.url.path,
    }
    if detail:
        body["detail"] = detail
    body.update(extra)
    return JSONResponse(
        jsonable_encoder(body), status_code=status_code, headers=headers, media_type=PROBLEM_JSON
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(
            request,
            exc.status_code,
            exc.detail,
            title=exc.title,
            type_=exc.type,
            headers=exc.headers,
            **exc.extra,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return problem_response(
            request, exc.status_code, detail, headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"campo": ".".join(str(p) for p in e["loc"] if p != "body"), "erro": e["msg"]}
            for e in exc.errors()
        ]
        return problem_response(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Um ou mais campos são inválidos.",
            errors=errors,
        )
