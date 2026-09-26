"""Miniaturas WebP (320px) para listas e revisão.

Geradas a partir do arquivo validado. Nenhum metadado é copiado: o EXIF das fotos
(que pode conter a localização GPS de onde foi tirada) não vai para a miniatura.
"""

import io

import pypdfium2 as pdfium
from PIL import Image, ImageOps

LARGURA = 320


def _pdf_primeira_pagina(data: bytes) -> Image.Image:
    doc = pdfium.PdfDocument(data)
    try:
        page = doc[0]
        largura_pt = page.get_width() or 595
        bitmap = page.render(scale=(LARGURA * 2) / largura_pt)
        img: Image.Image = bitmap.to_pil().copy()
        return img
    finally:
        doc.close()


def gerar_miniatura(data: bytes, mime_type: str) -> bytes:
    if mime_type == "application/pdf":
        img = _pdf_primeira_pagina(data)
    else:
        with Image.open(io.BytesIO(data)) as original:
            img = ImageOps.exif_transpose(original)  # corrige rotação da câmera
            img.load()
    img = img.convert("RGB")
    img.thumbnail((LARGURA, int(LARGURA * 1.6)))
    out = io.BytesIO()
    img.save(out, "WEBP", quality=80, method=4)  # sem exif=: metadados descartados
    return out.getvalue()
