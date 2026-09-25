"""Relógio de negócio: "hoje" no fuso da empresa (ADR 0004), injetável nos testes."""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

FUSO_NEGOCIO = ZoneInfo("America/Sao_Paulo")

Clock = Callable[[], date]


def hoje_negocio() -> date:
    return datetime.now(FUSO_NEGOCIO).date()


def get_clock() -> Clock:
    return hoje_negocio
