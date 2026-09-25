"""Status efetivo de um lançamento (ADR 0004).

A coluna `status` guarda só o que resulta de ação do usuário (pendente,
reagendado, pago, rejeitado). "atrasado" e "vence_hoje" são DERIVADOS da data
prevista comparada a hoje — a mesma regra da view `v_lancamentos` no banco.
"""

from datetime import date
from enum import StrEnum


class StatusArmazenado(StrEnum):
    PENDENTE = "pendente"
    REAGENDADO = "reagendado"
    PAGO = "pago"
    REJEITADO = "rejeitado"


class StatusEfetivo(StrEnum):
    PENDENTE = "pendente"
    REAGENDADO = "reagendado"
    VENCE_HOJE = "vence_hoje"
    ATRASADO = "atrasado"
    PAGO = "pago"
    REJEITADO = "rejeitado"


FINAIS = {StatusArmazenado.PAGO, StatusArmazenado.REJEITADO}


def status_efetivo(status: str, prevista: date | None, hoje: date) -> StatusEfetivo:
    s = StatusArmazenado(status)
    if s in FINAIS or prevista is None:
        return StatusEfetivo(s.value)
    if prevista < hoje:
        return StatusEfetivo.ATRASADO
    if prevista == hoje:
        return StatusEfetivo.VENCE_HOJE
    return StatusEfetivo(s.value)


def dias_para_vencimento(prevista: date | None, hoje: date) -> int | None:
    return None if prevista is None else (prevista - hoje).days
