# Kora

> *Kora* = "salvar" em Akan.

Bot do Telegram que recebe links (Instagram, TikTok, X, YouTube, artigos), extrai o conteúdo, categoriza com IA e salva como nota no vault do Obsidian.

## Fluxo

1. Bot (long polling, restrito ao meu `chat_id`) grava o link numa fila SQLite.
2. Worker extrai metadados e conteúdo (`yt-dlp`, `faster-whisper`, `trafilatura`).
3. LLM resume e categoriza; a nota vai para `Referencias/Salvos/<categoria>/` no vault.

## Configuração

```bash
cp .env.example .env   # preencher TELEGRAM_BOT_TOKEN e TELEGRAM_ALLOWED_CHAT_ID
uv sync
```

## IA (categorização)

`LLM_PROVIDER` escolhe **um** provedor: `anthropic`, `deepseek` ou `ollama` (vazio = sem IA). Cada um
funciona sozinho, com seu modelo no `.env` (`ANTHROPIC_MODEL`, `DEEPSEEK_MODEL`, `OLLAMA_MODEL`). Se a
chave faltar ou o nome estiver errado, o worker nem inicia. Se a chamada falhar, a nota fica em
`Referencias/Salvos/_inbox/` com `status: pendente`.

## Corrigir e reprocessar

- **Categoria errada:** responda à mensagem "salvo em …" do bot com `categoria: design` (aceita as 10 categorias, sem diferenciar maiúsculas). A nota muda de pasta e o frontmatter é atualizado. Para links anteriores a essa função, responda à sua mensagem com o link.
- **Notas pendentes** (IA fora do ar ou desligada): `uv run kora-reclassify [--limit N]` reprocessa as notas com `status: pendente`, mantém a data de criação e respeita categoria posta à mão.

## Buscar

No Telegram, `/buscar motion claude` lista até 5 notas com todos os termos (sem diferenciar acento ou
maiúsculas; título e tags pesam mais). No Obsidian, o índice `Referencias/Salvos/Salvos.md` (criado pelo
worker, uma vez) mostra recentes, categorias, plataformas, tags e pendentes via Dataview. O `CLAUDE.md` do
vault ensina os assistentes a procurar em `Referencias/Salvos/`.

## Rodar

```bash
uv run kora-bot      # recebe links e grava na fila
uv run kora-worker   # processa a fila e escreve as notas
uv run kora-reclassify  # reprocessa notas pendentes
uv run pytest        # testes
```

Plano completo e fases: [docs/PLANO.md](docs/PLANO.md).
