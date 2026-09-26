"""Validação de comprovantes em três camadas (RNF07) — funções puras sobre bytes.

1. Extensão na allowlist (.pdf .jpg .jpeg .png)
2. Tipo real pelos "magic bytes" (libmagic) — o Content-Type do cliente é ignorado
3. Leitura real do conteúdo (pypdf / Pillow), recusando arquivos corrompidos,
   criptografados, com JavaScript/ações automáticas, "bombas" de descompressão etc.
"""

import io
import re
import warnings
from dataclasses import dataclass
from pathlib import PurePath

import magic
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import LimitReachedError

EXTENSOES: dict[str, str] = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}
FORMATO_PIL = {"image/jpeg": "JPEG", "image/png": "PNG"}

# Limite de pixels decodificados: bloqueia "bombas" (arquivo pequeno que expande
# para gigabytes na memória). 50 MP cobre com folga fotos de celular (~12–50 MP).
MAX_PIXELS = 50_000_000

# Marcadores de conteúdo ativo em PDF — comprovantes legítimos não precisam deles.
_PDF_ATIVO = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile|RichMedia|OpenAction|AA)\b")


class ArquivoInvalidoError(Exception):
    """Mensagem pensada para o usuário final."""


@dataclass(frozen=True)
class ArquivoValidado:
    mime_type: str
    total_paginas: int


def extensao(nome: str) -> str:
    return PurePath(nome).suffix.lower()


def validar_extensao(nome: str) -> str:
    ext = extensao(nome)
    if ext not in EXTENSOES:
        permitidas = ", ".join(sorted({e.lstrip(".").upper() for e in EXTENSOES}))
        raise ArquivoInvalidoError(
            f"Formato {ext.lstrip('.').upper() or 'desconhecido'} não suportado. "
            f"Envie {permitidas}."
        )
    return EXTENSOES[ext]


_ACOES_PERIGOSAS = {"/JavaScript", "/Launch", "/ImportData", "/SubmitForm", "/RichMediaExecute"}


def _acao_perigosa(acao: object) -> bool:
    obj = getattr(acao, "get_object", lambda: acao)()
    return isinstance(obj, dict) and obj.get("/S") in _ACOES_PERIGOSAS


def _pdf_tem_conteudo_ativo(reader: PdfReader) -> bool:
    """Inspeção estrutural: pega scripts mesmo dentro de object streams comprimidos,
    que a busca por bytes não enxerga."""
    catalogo = reader.trailer["/Root"].get_object()
    if not isinstance(catalogo, dict):
        return False
    if "/OpenAction" in catalogo or "/AA" in catalogo:
        return True
    nomes = catalogo.get("/Names")
    nomes = nomes.get_object() if nomes is not None else None
    if isinstance(nomes, dict) and ("/JavaScript" in nomes or "/EmbeddedFiles" in nomes):
        return True
    for page in reader.pages:
        if "/AA" in page:
            return True
        for anot in page.get("/Annots") or []:
            a = anot.get_object()
            if a.get("/Subtype") in ("/FileAttachment", "/RichMedia", "/Movie", "/Sound"):
                return True
            if _acao_perigosa(a.get("/A")):
                return True
    return False


def _validar_pdf(data: bytes, max_paginas: int) -> int:
    if _PDF_ATIVO.search(data):
        raise ArquivoInvalidoError("O PDF contém conteúdo ativo (scripts ou ações) e foi recusado.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = PdfReader(io.BytesIO(data), strict=False)
            if reader.is_encrypted:
                raise ArquivoInvalidoError("O PDF está protegido por senha. Envie sem proteção.")
            paginas = len(reader.pages)
            if paginas < 1:
                raise ArquivoInvalidoError("O PDF não tem páginas.")
            if paginas > max_paginas:
                raise ArquivoInvalidoError(
                    f"O PDF tem {paginas} páginas; o máximo é {max_paginas}."
                )
            # Força a leitura de cada página (detecta arquivos truncados/corrompidos).
            for page in reader.pages:
                _ = page.mediabox
                page.get_contents()
            if _pdf_tem_conteudo_ativo(reader):
                raise ArquivoInvalidoError(
                    "O PDF contém conteúdo ativo (scripts ou ações) e foi recusado."
                )
    except ArquivoInvalidoError:
        raise
    except LimitReachedError as exc:  # "bomba": stream que expande para centenas de MB
        raise ArquivoInvalidoError(
            "O PDF tem conteúdo compactado grande demais e foi recusado."
        ) from exc
    except Exception as exc:
        # Entrada hostil: qualquer falha do leitor (inclusive RecursionError de objetos
        # aninhados sem fim) recusa o arquivo — o comprovante nunca fica sem resposta.
        raise ArquivoInvalidoError("O arquivo não é um PDF válido ou está corrompido.") from exc
    return paginas


def _validar_imagem(data: bytes, mime: str) -> int:
    # Poliglota: imagem válida que também abre como PDF (possivelmente com scripts).
    # Uma foto de verdade não traz um cabeçalho de PDF dentro dela. Dados extras em
    # geral não são recusados: celulares anexam vídeo às fotos ("foto com movimento").
    if b"%PDF-" in data:
        raise ArquivoInvalidoError("A imagem contém outro arquivo embutido e foi recusada.")
    esperado = FORMATO_PIL[mime]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as img:
                if img.format != esperado:
                    raise ArquivoInvalidoError("O conteúdo da imagem não corresponde ao formato.")
                if img.width * img.height > MAX_PIXELS:
                    raise ArquivoInvalidoError("A imagem tem resolução grande demais.")
                img.verify()
            # verify() não decodifica os pixels; load() sim (pega truncamento).
            with Image.open(io.BytesIO(data)) as img:
                img.load()
    except ArquivoInvalidoError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise ArquivoInvalidoError("A imagem tem resolução grande demais.") from exc
    except Exception as exc:  # qualquer falha do decodificador recusa o arquivo (ver PDF)
        raise ArquivoInvalidoError("A imagem está corrompida ou incompleta.") from exc
    return 1


def validar(nome: str, data: bytes, *, max_bytes: int, max_paginas: int) -> ArquivoValidado:
    """Executa as três camadas. Levanta ArquivoInvalidoError com mensagem ao usuário."""
    esperado = validar_extensao(nome)  # camada 1

    if not data:
        raise ArquivoInvalidoError("O arquivo está vazio.")
    if len(data) > max_bytes:
        raise ArquivoInvalidoError(f"O arquivo passa do limite de {max_bytes // (1024 * 1024)} MB.")

    real = magic.from_buffer(data[:8192], mime=True)  # camada 2
    if real != esperado:
        raise ArquivoInvalidoError(
            f"O conteúdo do arquivo não é {extensao(nome).lstrip('.').upper()} "
            f"(a extensão não corresponde ao arquivo)."
        )

    if esperado == "application/pdf":  # camada 3
        paginas = _validar_pdf(data, max_paginas)
    else:
        paginas = _validar_imagem(data, esperado)
    return ArquivoValidado(mime_type=esperado, total_paginas=paginas)
