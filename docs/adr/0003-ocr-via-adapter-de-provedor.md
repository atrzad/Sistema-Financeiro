# ADR 0003 — OCR atrás de um adapter de provedor

- **Status:** aceito
- **Data:** 2026-09-25

## Contexto
O plano lista vários provedores (Veryfi, Mindee, Taggun) e alternativas locais (Tesseract, PaddleOCR). A acurácia real em papel térmico difere dos benchmarks (RNF05), então a escolha final do provedor depende de medição com dados próprios, que só acontece com o sistema funcionando.

## Decisão
Definir uma interface única no backend:

```python
class OcrProvider(Protocol):
    name: str
    async def extract(self, file: bytes, mime_type: str) -> OcrResult: ...

@dataclass
class OcrField(Generic[T]):
    value: T | None
    confidence: float            # 0.0 – 1.0, normalizado entre provedores

@dataclass
class OcrResult:
    nome_fantasia: OcrField[str]
    razao_social: OcrField[str]
    cnpj: OcrField[str]
    data_emissao: OcrField[date]
    data_vencimento: OcrField[date]
    valor_total: OcrField[Decimal]
    forma_pagamento: OcrField[str]
    linha_digitavel: OcrField[str]
    itens: list[OcrItem]
    total_paginas: int
    raw: dict                    # payload original, gravado em ocr_raw_payload
```

- Implementações: `TesseractProvider` (dev/CI), `VeryfiProvider` e/ou `MindeeProvider` (produção). Seleção por variável `OCR_PROVIDER`.
- Pós-processamento comum a todos: validação de CNPJ por dígito verificador, parse de linha digitável de boleto (FEBRABAN) para extrair valor e vencimento — quando válido, **eleva a confiança** desses campos.
- `FakeOcrProvider` determinístico para testes.

## Consequências
- (+) Troca de provedor sem tocar em regra de negócio.
- (+) Benchmark A/B de provedores na Sprint 11 usando o mesmo dataset.
- (−) Normalizar escala de confiança entre provedores é heurístico e precisa de calibração.
