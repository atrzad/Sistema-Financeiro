"""Fábrica de arquivos de teste: válidos, corrompidos e maliciosos (gerados em memória)."""

import io
import zipfile

from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    NameObject,
    StreamObject,
    TextStringObject,
)


def pdf(paginas: int = 1) -> bytes:
    w = PdfWriter()
    for _ in range(paginas):
        w.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def pdf_com_javascript() -> bytes:
    """Script no catálogo de nomes (/Names /JavaScript), executado ao abrir o PDF."""
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    script = DictionaryObject(
        {
            NameObject("/S"): NameObject("/JavaScript"),
            NameObject("/JS"): TextStringObject("app.alert('oi');"),
        }
    )
    arvore = DictionaryObject(
        {NameObject("/Names"): ArrayObject([TextStringObject("js0"), w._add_object(script)])}
    )
    w._root_object[NameObject("/Names")] = DictionaryObject(
        {NameObject("/JavaScript"): w._add_object(arvore)}
    )
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def pdf_com_open_action() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    acao = DictionaryObject(
        {
            NameObject("/S"): NameObject("/Launch"),
            NameObject("/F"): TextStringObject("calc.exe"),
        }
    )
    w._root_object[NameObject("/OpenAction")] = w._add_object(acao)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def bomba_pdf(expandido: int = 100 * 1024 * 1024) -> bytes:
    """Página cujo conteúdo, comprimido em ~100 KB, expande para 100 MB."""
    w = PdfWriter()
    pagina = w.add_blank_page(width=595, height=842)
    conteudo = StreamObject()
    conteudo.set_data(b" " * expandido)
    conteudo = conteudo.flate_encode(level=9)
    pagina[NameObject("/Contents")] = w._add_object(conteudo)
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def pdf_criptografado() -> bytes:
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    w.encrypt(user_password="senha", owner_password="dono", algorithm="RC4-128")
    buf = io.BytesIO()
    w.write(buf)
    return buf.getvalue()


def imagem(fmt: str = "PNG", size: tuple[int, int] = (640, 480), exif: bool = False) -> bytes:
    img = Image.new("RGB", size, (200, 180, 90))
    buf = io.BytesIO()
    if exif:
        dados = Image.Exif()
        dados[0x010F] = "CameraFalsa"  # Make
        gps = dados.get_ifd(0x8825)  # GPSInfo: localização de onde a foto foi tirada
        gps[1] = "S"
        gps[2] = (23.0, 33.0, 0.0)
        img.save(buf, fmt, exif=dados)
    else:
        img.save(buf, fmt)
    return buf.getvalue()


def poliglota_jpeg_pdf() -> bytes:
    """JPEG válido que também abre como PDF (com script): o PDF vai num segmento de
    comentário (COM) logo no início — leitores de PDF aceitam o cabeçalho em qualquer
    ponto dos primeiros 1024 bytes."""
    jpeg = imagem("JPEG")
    doc = pdf_com_javascript()
    comentario = b"\xff\xfe" + (len(doc) + 2).to_bytes(2, "big") + doc
    return jpeg[:2] + comentario + jpeg[2:]


def png_com_pdf_no_fim() -> bytes:
    """PNG com um PDF colado depois do fim da imagem (visualizadores ignoram o resto)."""
    return imagem("PNG") + pdf()


def bomba_png(lado: int = 8000) -> bytes:
    """64 MP comprimidos em poucos KB — expande na memória se decodificado."""
    img = Image.new("1", (lado, lado), 0)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("leia.txt", "oi")
    return buf.getvalue()


EXECUTAVEL = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff" + b"\x00" * 200
HTML = b"<!DOCTYPE html><html><body><script>alert(1)</script></body></html>"
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
