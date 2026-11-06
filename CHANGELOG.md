# Changelog

Todas as mudanças relevantes do projeto ficam aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e as versões seguem o
[Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não lançado]

### Corrigido

- O intervalo gravado pela interface deixava o timer dos lotes sem agendamento: o drop-in tinha dois
  resets (`OnActiveSec=` e `OnUnitInactiveSec=`) e cada um zera todos os `On*Sec` do timer, então o
  `OnActiveSec` sumia e a fila parava. Agora há um único reset antes dos valores.

### Adicionado

- Conferência do agendamento: ao salvar o intervalo, a interface confere no systemd se os dois gatilhos
  existem e acusa o defeito; o `/status` do bot avisa "Agendamento quebrado" em vez de só "indisponível".

## [0.2.0] - 2026-10-20

Interface web local, com acesso de fora pelo Tailscale, e correção do timer dos lotes.

### Adicionado

- **Interface web local** (`kora-web`, em `http://127.0.0.1:8765`, serviço `kora-web.service`):
  - **Salvos:** galeria com busca ao digitar, filtros (categoria, plataforma, período, tag), painel de detalhes
    e troca de categoria.
  - **Fila:** em andamento, aguardando, falhas e notas sem IA, com "Processar agora".
  - **Ajustes:** provedor e modelo de IA com teste de conexão, chaves de API (só gravação), intervalo dos lotes,
    transcrição, limites e categorias. Salvar reescreve o `.env`, o drop-in do timer e reinicia o bot.
- **Acesso de fora pelo Tailscale** (`WEB_HOSTS` e `WEB_ALLOWED_USERS`): a interface web aceita hosts da lista, só
  de usuários autorizados (login do `tailscale serve`). Aviso no topo para quem entra de fora; a lista de quem pode
  entrar só se muda no computador da Kora. Configurável na seção "Acesso de fora" dos Ajustes.
- Categorias configuráveis: passam a ser lidas de `data/categorias.json` (as de fábrica continuam como padrão).

### Corrigido

- **Fila parada por dias:** `kora-worker.timer` usava `OnBootSec`; se o timer reiniciasse com o computador ligado há
  mais de 1 h, o gatilho já tinha passado e o `OnUnitInactiveSec` nunca começava, então nenhum lote rodava. Agora usa
  `OnActiveSec` (o primeiro lote sai 1 h depois de o timer iniciar). Quem já instalou deve rodar `deploy/install.sh`
  de novo.

### Documentação

- Tailscale Serve passa a usar `--https=10000` no exemplo, porque a 443 e a 8443 costumam estar ocupadas.

## [0.1.0] - 2026-10-17

Primeira versão: o fluxo completo funciona, do link no Telegram até a nota no Obsidian.

### Adicionado

- **Bot do Telegram** (long polling), restrito a um único chat. Os links entram numa fila SQLite, sem
  repetição (URL canônica, com links encurtados resolvidos e parâmetros de rastreio removidos).
- **Extração de conteúdo**
  - `yt-dlp` com impersonação de navegador (Instagram Reels, TikTok, X, YouTube).
  - Texto completo de tweets longos pela API pública do FixTweet.
  - Posts de foto do Instagram pelas tags públicas da página.
  - Artigos e páginas comuns com `trafilatura`.
- **Transcrição local** com `faster-whisper` (modelo `small`, CPU): usa a legenda do próprio site quando
  existe, baixa só o áudio quando não existe e apaga o arquivo em seguida. Vídeos acima de
  `MAX_AUDIO_MINUTES` ficam só com a legenda.
- **Categorização com IA** com provedores `anthropic`, `deepseek` e `ollama` (um ativo por vez, via
  `LLM_PROVIDER`). A IA devolve título, resumo, pontos-chave, categoria e tags em JSON validado, com 10
  categorias fixas e uma regra de desempate.
- **Notas no Obsidian** em `Referencias/Salvos/<categoria>/`, com frontmatter, resumo, pontos-chave,
  legenda original e transcrição em bloco recolhido. Sem IA disponível, a nota fica em `_inbox/` com
  `status: pendente`.
- **Comandos do bot:** `/buscar` (todos os termos, sem acento), `/status` e `/processar`; correção de
  categoria respondendo `categoria: X` ao aviso do bot.
- **`kora-reclassify`:** reprocessa as notas pendentes, preservando a data de criação e categorias
  definidas à mão.
- **Índice `Salvos.md`** com consultas Dataview, criado uma única vez no vault.
- **Execução automática** no `systemd --user`: bot sempre ligado; worker em lotes (`kora-worker --once`)
  disparados por timer, 1 hora depois de ligar o computador e 8 horas após o fim de cada lote; timer diário
  que atualiza o `yt-dlp`; `deploy/install.sh` para instalar e remover.
- **Retentativas:** 3 tentativas com espera crescente; depois disso o item fica como `falhou` e o bot avisa.
- **Logs** sem o token do bot (as bibliotecas de HTTP ficam silenciadas) e batimento do worker contínuo.
- **README** completo, com imagens e os próximos passos.

### Limitações conhecidas

- Os avisos "salvo em …" chegam quando o lote roda (até 8 horas); `/processar` roda um lote na hora.
- O Telegram guarda mensagens não lidas por 24 horas: com o bot parado por mais tempo, links se perdem.
- Carrossel `/photo/` do TikTok não é suportado; o YouTube pode exigir login (anti-bot).
- Só o Ollama foi validado de ponta a ponta com um provedor real; Anthropic e DeepSeek estão cobertos por
  testes com respostas simuladas.
- Um provedor de IA por vez, sem fallback automático.

[0.1.0]: https://github.com/Joaovitor12j/kora/releases/tag/v0.1.0
