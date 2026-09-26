import io

import magic
import pytest
from PIL import Image

from app.domain.upload_validation import ArquivoInvalidoError, validar
from tests import arquivos as A

LIMITE = 10 * 1024 * 1024


def _validar(nome: str, data: bytes) -> object:
    return validar(nome, data, max_bytes=LIMITE, max_paginas=50)


@pytest.mark.parametrize(
    ("nome", "data", "mime", "paginas"),
    [
        ("boleto.pdf", A.pdf(), "application/pdf", 1),
        ("carne.PDF", A.pdf(3), "application/pdf", 3),
        ("nota.png", A.imagem("PNG"), "image/png", 1),
        ("recibo.jpg", A.imagem("JPEG"), "image/jpeg", 1),
        ("recibo.jpeg", A.imagem("JPEG", exif=True), "image/jpeg", 1),
    ],
)
def test_aceita_arquivos_validos(nome: str, data: bytes, mime: str, paginas: int) -> None:
    r = _validar(nome, data)
    assert (r.mime_type, r.total_paginas) == (mime, paginas)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("nome", "data", "trecho"),
    [
        # Camada 1 — extensão
        ("foto.heic", A.imagem("PNG"), "não suportado"),
        ("programa.exe", A.EXECUTAVEL, "não suportado"),
        ("sem_extensao", A.pdf(), "não suportado"),
        ("pagina.html", A.HTML, "não suportado"),
        # Camada 2 — tipo real diferente da extensão
        ("disfarcado.pdf", A.EXECUTAVEL, "não é PDF"),
        ("imagem.pdf", A.imagem("PNG"), "não é PDF"),
        ("documento.png", A.pdf(), "não é PNG"),
        ("compactado.pdf", A.zip_bytes(), "não é PDF"),
        ("script.png", A.SVG, "não é PNG"),
        ("pagina.jpg", A.HTML, "não é JPG"),
        ("jpeg_como.png", A.imagem("JPEG"), "não é PNG"),
        ("vazio.pdf", b"", "vazio"),
        # Camada 3 — conteúdo
        ("truncado.pdf", A.pdf(2)[:300], "corrompido"),
        ("com_script.pdf", A.pdf_com_javascript(), "conteúdo ativo"),
        ("abre_programa.pdf", A.pdf_com_open_action(), "conteúdo ativo"),
        ("protegido.pdf", A.pdf_criptografado(), "senha"),
        ("carne_enorme.pdf", A.pdf(51), "máximo é 50"),
        ("truncada.jpg", A.imagem("JPEG", size=(1200, 900))[:2000], "corrompida"),
        ("bomba.png", A.bomba_png(), "resolução grande demais"),
        ("bomba.pdf", A.bomba_pdf(), "compactado grande demais"),
        # Poliglotas: um arquivo que é duas coisas ao mesmo tempo
        ("poliglota.jpg", A.poliglota_jpeg_pdf(), "outro arquivo embutido"),
        ("poliglota.pdf", A.poliglota_jpeg_pdf(), "não é PDF"),
        ("recibo.png", A.png_com_pdf_no_fim(), "outro arquivo embutido"),
    ],
)
def test_recusa_arquivos_invalidos_ou_maliciosos(nome: str, data: bytes, trecho: str) -> None:
    with pytest.raises(ArquivoInvalidoError, match=trecho):
        _validar(nome, data)


def test_recusa_acima_do_limite_de_tamanho() -> None:
    with pytest.raises(ArquivoInvalidoError, match="limite de 10 MB"):
        validar("grande.pdf", A.pdf() + b"0" * LIMITE, max_bytes=LIMITE, max_paginas=50)


def test_poliglota_passaria_como_jpeg_sem_a_checagem() -> None:
    """A fixture é perigosa de verdade: libmagic e Pillow a veem como um JPEG
    legítimo, e o cabeçalho do PDF está onde os leitores de PDF o procuram."""
    data = A.poliglota_jpeg_pdf()
    assert magic.from_buffer(data[:8192], mime=True) == "image/jpeg"
    with Image.open(io.BytesIO(data)) as img:
        img.load()
    assert b"%PDF-" in data[:1024]
