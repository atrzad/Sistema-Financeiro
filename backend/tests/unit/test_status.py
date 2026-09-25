from datetime import date

import pytest

from app.domain.status import dias_para_vencimento, status_efetivo

HOJE = date(2026, 9, 25)


@pytest.mark.parametrize(
    ("armazenado", "prevista", "esperado"),
    [
        ("pendente", date(2026, 9, 24), "atrasado"),
        ("pendente", HOJE, "vence_hoje"),
        ("pendente", date(2026, 9, 26), "pendente"),
        ("pendente", None, "pendente"),
        ("reagendado", date(2026, 9, 1), "atrasado"),
        ("reagendado", HOJE, "vence_hoje"),
        ("reagendado", date(2026, 10, 5), "reagendado"),
        ("pago", date(2026, 9, 1), "pago"),
        ("rejeitado", date(2026, 9, 1), "rejeitado"),
    ],
)
def test_tabela_da_adr_0004(armazenado: str, prevista: date | None, esperado: str) -> None:
    assert status_efetivo(armazenado, prevista, HOJE) == esperado


def test_dias_para_vencimento() -> None:
    assert dias_para_vencimento(date(2026, 9, 28), HOJE) == 3
    assert dias_para_vencimento(date(2026, 9, 20), HOJE) == -5
    assert dias_para_vencimento(None, HOJE) is None
