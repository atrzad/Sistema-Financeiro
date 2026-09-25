# Sprint 10 — App mobile com scanner

[← Sprint 09](sprint-09.md) · [Índice](README.md) · [Sprint 11 →](sprint-11.md)

| | |
|---|---|
| **Período** | 08/03 – 19/03/2027 |
| **Pontos** | 21 |
| **Fase do MVP** | Mobile |

## 1. Objetivo
O colaborador escaneia comprovantes com o celular (detecção de bordas, correção de perspectiva, várias páginas), envia até 10 por vez usando a mesma API de lote e acompanha o processamento e os boletos a pagar — com envio resiliente a conexão ruim.

## 2. Requisitos cobertos
RF01 (scanner embutido) · RF11 · RNF01 · Telas 1, 2, 4 e 5 em versão mobile

> Dependência real: apenas Sprints 03 e 04 (API de upload e OCR). Pode ser antecipada se o scanner for prioridade.

## 3. Histórias de usuário

### H10.1 — Projeto React Native `3 pts`
- **Então** `mobile/` criado com Expo (SDK atual) em modo **dev build** (necessário para módulo nativo), TypeScript strict, Expo Router.
- **Então** reutiliza `packages/api-client` gerado do OpenAPI e as regras de formatação (`Intl`) compartilhadas num pacote `packages/shared`.
- **Então** builds Android e iOS via EAS (perfis `development`, `preview`, `production`); CI roda lint, typecheck e testes (Jest + React Native Testing Library).

### H10.2 — Login e sessão segura `2 pts`
- **Então** login com empresa, e-mail e senha usando a mesma API.
- **Então** refresh token guardado em `expo-secure-store` (Keychain/Keystore) — nunca em AsyncStorage.
- **Então** o backend aceita refresh via corpo JSON para clientes mobile (`POST /auth/refresh` com `client=mobile`), mantendo o cookie para web.
- **Então** desbloqueio opcional por biometria (`expo-local-authentication`).

### H10.3 — Scanner de documentos `5 pts`
**Como** colaborador, **quero** fotografar o recibo com recorte automático **para** que o OCR leia melhor.
- **Então** Android usa **ML Kit Document Scanner** (detecção de bordas, correção de perspectiva, remoção de sombras, múltiplas páginas); iOS usa **VisionKit `VNDocumentCameraViewController`** — via módulo Expo nativo (`react-native-document-scanner-plugin` ou módulo próprio).
- **Então** cada documento escaneado com várias páginas vira **um PDF** (carnê/nota com verso); documento de uma página vira JPEG com qualidade 85 e lado maior ≤ 2.400 px (mantém legibilidade e fica bem abaixo de 10 MB).
- **Então** permite também escolher da galeria ou de arquivos (PDF recebido por e-mail/WhatsApp) — inclusive via **compartilhar para o app** (share intent).
- **Então** o usuário revisa miniaturas, reordena, remove e pode "escanear mais" até 10 itens.

### H10.4 — Fila de upload resiliente `5 pts`
- **Então** a fila local (persistida em SQLite/MMKV) reaproveita o fluxo `POST /uploads/batch` → PUT presigned → `/complete`, com 3 envios simultâneos e barra de progresso por item.
- **Então** sem conexão, os itens ficam em "aguardando conexão" e são enviados automaticamente quando a rede volta (`@react-native-community/netinfo`); presigned URLs expiradas são renovadas via `/retry-url`.
- **Então** o envio continua com o app em segundo plano (Android: foreground service com notificação; iOS: `URLSession` background upload).
- **Então** `upload_batches.origem = 'mobile'` para métricas.
- **Então** arquivos locais são apagados após confirmação de `concluido` no servidor.

### H10.5 — Progresso e lista de boletos `3 pts`
- **Então** tela de processamento do lote (versão mobile da Tela 2) com status por item via polling.
- **Então** tela "Meus boletos" (versão mobile da Tela 4) com abas de filtro, badges de urgência e pull-to-refresh.
- **Então** modal de pagamento (Tela 5) com "Paguei hoje", "Selecionar outro dia" e botão para copiar a linha digitável.
- **Então** a revisão detalhada do OCR (Tela 3) no MVP abre uma versão simplificada: campos 🔴 editáveis; revisão completa continua na web.

### H10.6 — Notificações push `3 pts`
- **Então** registro do token de push (`expo-notifications`) em `POST /me/dispositivos`.
- **Então** push quando o lote termina o OCR ("5 documentos prontos para revisão") e nos lembretes de vencimento (Sprint 07), respeitando a preferência do usuário.
- **Então** tocar na notificação abre a tela correspondente (deep link).

## 4. Tarefas técnicas

**Backend**
- [ ] Refresh token via corpo para `client=mobile`
- [ ] Tabela `dispositivos (tenant_id, user_id, push_token, plataforma, ativo)` com RLS
- [ ] `services/push.py` (Expo Push API) integrado aos eventos de lote e à task de lembretes

**Mobile**
- [ ] `mobile/app/` (Expo Router): `(auth)/login`, `(tabs)/escanear`, `(tabs)/boletos`, `(tabs)/perfil`, `lote/[id]`
- [ ] `features/scanner/` — wrapper do scanner nativo, geração de PDF multi-página (`expo-print` ou lib nativa)
- [ ] `features/upload/` — fila persistente, retomada, upload em background
- [ ] Monorepo pnpm + Metro configurado para pacotes compartilhados

## 5. Contrato de API

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/v1/auth/refresh` | Aceita `{refresh_token}` no corpo para `client=mobile` |
| POST | `/api/v1/me/dispositivos` | Registra token de push |
| DELETE | `/api/v1/me/dispositivos/{id}` | Remove no logout |

Demais endpoints reutilizados sem alteração (upload, lançamentos, pagamento).

## 6. Estratégia de testes
- Unidade: fila de upload (retomada, expiração de URL, cancelamento) com mocks de rede.
- Dispositivo real: matriz mínima — Android 10 e 14 (câmera básica e boa), iPhone com iOS atual.
- Campo: 20 comprovantes reais (cupom térmico amassado, boleto dobrado, luz baixa) → comparar confiança média do OCR mobile vs. foto comum na web.
- Rede: modo avião no meio do lote → reconectar → todos os itens concluem sem duplicar.

## 7. Definition of Done específica
- [ ] Build `preview` instalável distribuída (APK interno / TestFlight)
- [ ] Lote enviado com rede intermitente conclui sem duplicidade
- [ ] Scanner melhora a confiança média do OCR em relação à foto sem tratamento (registrar números)

## 8. Riscos e mitigação

| Risco | Mitigação |
|-------|-----------|
| Módulo nativo do scanner incompatível com a versão do Expo | Spike no dia 1; alternativa: módulo Expo próprio chamando ML Kit/VisionKit |
| Upload em background no iOS é limitado | Usar `URLSession` background via lib nativa; se inviável no prazo, manter app em primeiro plano com aviso |
| Publicação nas lojas demora | Fora do escopo desta sprint; distribuição interna primeiro, lojas na Sprint 11 |

## 9. Entregável / demo
Escanear um recibo, um boleto e um carnê de 3 páginas no celular, ativar modo avião no meio do envio, reconectar, receber push de "prontos para revisão" e marcar um boleto como pago pelo app.

## 10. Retrospectiva
_Preencher ao final da sprint._
