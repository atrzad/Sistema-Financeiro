"""CNPJ: normalização, validação de dígitos verificadores e formatação.

Suporta o CNPJ alfanumérico (IN RFB nº 2.229/2024, emitido a partir de jul/2026):
as 12 primeiras posições podem conter letras A–Z; os 2 dígitos verificadores
continuam numéricos. O cálculo usa o valor ASCII − 48 de cada caractere, o que
mantém compatibilidade total com o CNPJ numérico.
"""

import re

_PESOS_1 = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_PESOS_2 = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_FORMATO = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")


def normalizar(valor: str) -> str:
    """Remove pontuação e espaços; letras em maiúsculas."""
    return re.sub(r"[^0-9A-Za-z]", "", valor).upper()


def _dv(base: str, pesos: tuple[int, ...]) -> int:
    soma = sum((ord(c) - 48) * p for c, p in zip(base, pesos, strict=True))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def valido(valor: str) -> bool:
    cnpj = normalizar(valor)
    if not _FORMATO.match(cnpj):
        return False
    if len(set(cnpj)) == 1:  # 00000000000000, 11111111111111...
        return False
    d1 = _dv(cnpj[:12], _PESOS_1)
    d2 = _dv(cnpj[:12] + str(d1), _PESOS_2)
    return cnpj[12:] == f"{d1}{d2}"


def formatar(valor: str) -> str:
    c = normalizar(valor)
    if len(c) != 14:
        return valor
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
