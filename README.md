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

## Rodar

```bash
uv run kora-bot      # recebe links e grava na fila
uv run kora-worker   # processa a fila e escreve as notas
uv run pytest        # testes
```

Plano completo e fases: [docs/PLANO.md](docs/PLANO.md).
