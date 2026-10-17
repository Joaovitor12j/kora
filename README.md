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

## Como serviço (systemd --user)

O **bot fica sempre ligado** (recebe os links na hora, responde `/buscar`, `/status` e correções). O **worker
roda em lotes**: um timer dispara um lote 1 h depois de ligar o computador e, depois, 8 h após o fim de cada
lote (`deploy/kora-worker.timer`; só conta o tempo com a máquina ligada). Cada lote esvazia a fila e termina.
O aviso "salvo em …" de cada link chega quando o lote o processa, então pode demorar até 8 h.

Pare o bot e o worker que estiverem em terminais (dois bots com o mesmo token disputam as mensagens) e rode:

```bash
deploy/install.sh
```

Isso instala o bot, o timer dos lotes e o timer diário que atualiza o `yt-dlp`. Reinício automático do bot em
falha. Quem já tinha o worker contínuo instalado é migrado sozinho.

```bash
systemctl --user list-timers 'kora-*'          # próximas execuções
journalctl --user -u kora-worker -f            # logs dos lotes
journalctl --user -u kora-bot -f               # logs do bot
deploy/install.sh uninstall                    # remove
loginctl enable-linger "$USER"                 # opcional: sobe no boot, sem login
```

Para mudar o ritmo, edite `OnBootSec` e `OnUnitInactiveSec` em `~/.config/systemd/user/kora-worker.timer`
(ou `systemctl --user edit kora-worker.timer`).

No Telegram:
- `/processar` dispara um lote agora, sem esperar o timer.
- `/status` mostra a última execução (quando, quantos salvos e falhas), a próxima, a fila, notas pendentes de
  IA, o provedor de IA, a versão do `yt-dlp`, o último salvo e as falhas recentes.

`uv run kora-worker --once` roda um lote à mão; sem `--once` o worker fica em loop (modo contínuo, útil em
desenvolvimento). O nível de log vem de `LOG_LEVEL` (padrão `INFO`); os logs de HTTP ficam silenciados porque a
URL da API do Telegram carrega o token do bot.

Limite conhecido: o Telegram guarda mensagens não lidas por 24 h. Se o bot ficar parado por mais tempo, links
enviados nesse intervalo se perdem. A fila local não tem esse limite: o bot a alimenta na hora.
