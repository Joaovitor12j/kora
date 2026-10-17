# Kora — Plano de implementação

> *Kora* = "salvar" em Akan. Bot que salva links e os transforma em notas no Obsidian.

Origem: nota `Bot de links para o Obsidian` no vault (ideia de 2026-10-17).

## Arquitetura

```
Telegram ──(long polling)──> bot ──> fila (SQLite)
                                        │
                                        ▼
                     worker: yt-dlp → faster-whisper → LLM
                                        │
                                        ▼
                     vault: Referencias/Salvos/<categoria>/<nota>.md
                                        │
                                        ▼
               assistentes leem o vault (arquivos ou MCP)
```

- **Código fora do vault**: repositório próprio (`~/GitProjects/kora`). O vault só recebe as notas; o Obsidian Git já commita.
- **Stack**: Python 3.12, `python-telegram-bot`, `yt-dlp` (como biblioteca), `faster-whisper`, `trafilatura` (artigos), SQLite.
- **LLM**: Claude API (Haiku, barato e bom em JSON) ou Ollama local. Começar com Claude; trocar depois se quiser 100% local.

## Estrutura do repositório

```
kora/
├── pyproject.toml          # pacote `kora`, deps, entrypoints
├── src/kora/
│   ├── config.py           # lê .env (pydantic-settings)
│   ├── db.py               # SQLite: schema, fila, transições de status
│   ├── urls.py             # extração e canonicalização de URLs
│   ├── bot.py              # Telegram (long polling), só o chat_id permitido
│   ├── worker.py           # loop da fila, retentativa com backoff
│   ├── extractors/         # ytdlp.py, article.py, fxtwitter.py
│   ├── transcribe.py       # faster-whisper
│   ├── llm.py              # prompt, validação do JSON, taxonomia
│   └── vault.py            # renderiza e grava a nota
├── tests/                  # urls, db, vault, llm (com fixtures)
├── deploy/                 # units systemd --user
└── docs/
```

Entrypoints: `kora-bot`, `kora-worker`. Units: `kora-bot.service`, `kora-worker.service`.

Princípios: cada etapa do worker é função pura sobre o item da fila (testável sem rede); a fila é a fonte da verdade e o worker é idempotente (reprocessar o mesmo item sobrescreve a mesma nota).

## Formato da nota

```markdown
---
criado: 2026-10-17
tipo: link
plataforma: tiktok
url: https://...
autor: "@fulano"
categoria: programação
tags: [laravel, filas]
status: processado   # pendente | processado | falhou
---

# <título gerado>

## Resumo
3 a 5 linhas.

## Pontos-chave
- ...

## Legenda original
...

## Transcrição
> [!note]- Transcrição completa
> ...
```

Taxonomia fixa e pequena (definir antes do MVP), ex.: programação, IA, design, negócios, finanças, saúde, receitas, humor, outros. Tags livres, mas o prompt recebe a lista de tags já existentes para reaproveitar.


## Fase 0 — Validação técnica (1 noite)
- [ ] Testar `yt-dlp --dump-json` e download de áudio com 10 links reais (TikTok, Reels, post de foto do IG, tweet de texto, tweet com vídeo).
- [ ] Testar Instagram com `--cookies-from-browser firefox` (muitos Reels exigem login).
- [ ] Medir `faster-whisper` (modelo `small` e `medium`, idioma pt) num vídeo de 1 min: tempo na CPU/GPU da máquina.
- [ ] Decidir onde o bot roda (ver riscos: retenção de 24h do Telegram).

Critério: ≥ 80% dos links de teste geram metadados + áudio utilizável.

### Resultados da Fase 0 (2026-10-17, yt-dlp 2026.10.10, 9 links)
- **Sem cookies**: X (2/2, vídeo+áudio), Reels (3/3), Instagram foto (0/1), TikTok (0/3). yt-dlp puro: 5/9 (56%).
- **Cookies (Firefox snap e Chrome) não mudaram nada** em TikTok nem em post de foto do IG; Reels funcionam sem login. YouTube, porém, exige cookies a partir desta rede.
- **TikTok (resolvido)**: o erro era o desafio anti-bot do site. `pip install curl_cffi` + `yt-dlp --impersonate chrome` resolve: metadados e áudio OK em 2/2 vídeos (transcrição `small`: 7 s para 60 s de áudio). Sem cookies, sem proxy. O worker deve sempre passar `impersonate` ao yt-dlp.
- **TikTok `/photo/`** (carrossel): extractor do yt-dlp não suporta, oEmbed devolve 400 e o HTML não traz `desc` no JSON de rehydration. Tratar como nota só com URL (`status: falhou`) até haver necessidade.
- **Instagram foto**: yt-dlp não suporta; fallback via `og:title`/`og:description` (UA `facebookexternalhit`) devolve legenda e autor.
- Com `--impersonate` + fallback og:tags do IG: 7/9 com conteúdo (áudio/legenda), 78%; os 2 restantes são posts de foto (IG com og:tags dá legenda → 8/9, 89%, critério de 80% atingido).
- **faster-whisper (pt, vídeo de 71 s)**: CPU `small` int8 = 11,6 s (1704 chars, boa qualidade); `medium` = 30,1 s (sem ganho claro). **Decisão: `small` na CPU.** GPU (RTX 2050) falha por falta de `libcublas.so.12`; não necessário.
- Dependência: `faster-whisper` 1.2.1 exige `av<16` (PyAV 19 quebra com `metadata_errors`).
- Pendente: onde o bot roda (retenção de 24 h do Telegram).

## Fase 1 — MVP sem IA
- [ ] Criar bot no @BotFather; token em `.env` fora do vault.
- [x] Bot aceita só o meu `chat_id`; extrai URLs da mensagem; grava na fila (`url`, `url_canonica`, `status`, `tentativas`, `erro`).
- [x] Deduplicar pela URL canônica (resolver `vt.tiktok.com/...` e remover parâmetros de rastreio).
- [x] Worker lê a fila, roda `yt-dlp` só para metadados (título, autor, descrição, data) e escreve a nota com `status: pendente` de IA.
- [x] Bot responde "salvo: <título>".

Entrega: mando link, nota aparece no vault com legenda e metadados.

## Fase 2 — Conteúdo real
- [ ] Vídeo: baixar só áudio → `faster-whisper` → transcrição na nota. Apagar o áudio depois.
- [ ] Usar legenda do próprio site quando existir (mais rápido que transcrever).
- [ ] Artigo/página comum: `trafilatura` para extrair o texto.
- [ ] X sem vídeo: tentar `api.fxtwitter.com`; se falhar, nota só com a URL e `status: falhou`.
- [ ] Post de imagem (carrossel do IG): guardar legenda; OCR/visão fica para depois.

## Fase 3 — Categorização com IA
- [ ] Prompt com taxonomia fixa + tags existentes; saída em JSON (título, resumo, pontos-chave, categoria, tags).
- [ ] Validar o JSON; se a categoria não for da lista, usar `outros`.
- [ ] Mover a nota para `Referencias/Salvos/<categoria>/`.
- [ ] Bot responde com categoria e resumo de uma linha; permitir corrigir respondendo "categoria: X".

## Fase 4 — Busca pelos assistentes
- [ ] Nota índice `Referencias/Salvos/Salvos.md` com Dataview (por categoria, plataforma, data).
- [ ] Instrução no `CLAUDE.md` do vault: "para coisas salvas, procurar em `Referencias/Salvos/` por frontmatter e texto".
- [ ] Se o volume passar de algumas centenas: embeddings locais (`sqlite-vec`) + servidor MCP com uma ferramenta `buscar_salvos(pergunta)`.
- [ ] Opcional: comando `/buscar <termo>` no próprio bot.

## Fase 5 — Robustez
- [ ] Rodar bot e worker como serviço `systemd --user` (sobe com a máquina).
- [ ] Retentativa com backoff; após 3 falhas, `status: falhou` e aviso no Telegram.
- [ ] Atualizar `yt-dlp` automaticamente (quebra com frequência quando os sites mudam).
- [ ] Log simples e comando `/status` no bot (fila pendente, últimas falhas).

## Riscos / dúvidas
- **Retenção do Telegram**: `getUpdates` guarda mensagens por **24 horas**. Máquina desligada mais que isso perde links. Opções: rodar só o bot (leve) num Raspberry/VPS e o worker pesado local; ou aceitar o risco.
- **Instagram/TikTok mudam e bloqueiam**: `yt-dlp` quebra de tempos em tempos; cookies de login podem expirar ou levar a conta a ser sinalizada. Usar cookies de uma conta secundária, se possível.
- **X**: API oficial paga; alternativas são frágeis. Tweet de texto pode ficar sem conteúdo.
- **Custo da IA**: com Haiku, centavos por centena de links. Transcrição local não custa nada além de CPU.
- **Privacidade**: token, cookies e `.env` nunca no vault (o repositório vai para o GitHub).
- Taxonomia: quais categorias realmente uso? Definir olhando os últimos ~30 links salvos.

## Ordem de execução

1. Fase 0 (bloqueia o resto: define viabilidade e onde o bot roda).
2. Esqueleto do repo (`pyproject`, `config`, `db`, `urls` + testes) — base da Fase 1.
3. Fases 1 → 2 → 3, cada uma terminando com algo usável no vault.
4. Fase 5 (systemd) antes da Fase 4, para o uso diário começar cedo e gerar volume real.
5. Fase 4 por último; embeddings só se o volume pedir.

## Como validar
- [ ] Fase 0 concluída com o critério de 80%.
- [ ] Usar o MVP por 2 semanas e ver se continuo mandando links.
- [ ] Pedir a um assistente algo salvo há mais de uma semana e ele achar na primeira tentativa.

