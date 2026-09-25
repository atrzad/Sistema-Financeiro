import pytest

from app.domain import cnpj


@pytest.mark.parametrize(
    "valor",
    [
        "11.222.333/0001-81",
        "11222333000181",
        "  11 222 333 0001 81 ",
        "45.723.174/0001-10",
        # Alfanumérico (exemplo oficial da Receita Federal)
        "12.ABC.345/01DE-35",
        "12abc34501de35",
    ],
)
def test_cnpjs_validos(valor: str) -> None:
    assert cnpj.valido(valor)


@pytest.mark.parametrize(
    "valor",
    [
        "11.222.333/0001-82",  # DV errado
        "00000000000000",
        "11111111111111",
        "1122233300018",  # 13 dígitos
        "112223330001811",  # 15 dígitos
        "12.ABC.345/01DE-36",  # DV alfanumérico errado
        "12.ABC.345/01DE-3A",  # DV não pode ter letra
        "",
    ],
)
def test_cnpjs_invalidos(valor: str) -> None:
    assert not cnpj.valido(valor)


def test_normalizar_e_formatar() -> None:
    assert cnpj.normalizar("12.abc.345/01de-35") == "12ABC34501DE35"
    assert cnpj.formatar("11222333000181") == "11.222.333/0001-81"
    assert cnpj.formatar("12ABC34501DE35") == "12.ABC.345/01DE-35"
