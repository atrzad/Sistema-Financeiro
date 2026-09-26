import os
from typing import NoReturn

import pytest


def servico_indisponivel(motivo: str) -> NoReturn:
    """Sem Postgres/storage os testes de integração são pulados — exceto com
    REQUIRE_SERVICES=1 (CI), onde um pulo esconderia a falta de cobertura."""
    if os.environ.get("REQUIRE_SERVICES") == "1":
        pytest.fail(motivo, pytrace=False)
    pytest.skip(motivo)
