# Roadmap

Nada abaixo está implementado ainda. A interface configurável e a galeria dos links salvos já saíram (veja [Interface web](../README.md#interface-web)).

## 1. Orquestrador de IA com fallback
Hoje cada provedor funciona sozinho e, se ele falhar, a nota fica pendente. O orquestrador tentaria vários em
ordem configurável (por exemplo Anthropic, depois DeepSeek, depois Ollama), passando ao próximo quando houver
erro, limite de uso ou JSON inválido, e registraria quem respondeu (o campo `ia` da nota já existe). A interface
`Provider.complete()` já foi pensada para isso: o orquestrador entra por cima, sem mexer nos provedores.
*Decisões em aberto:* ordem fixa ou por custo/latência; limite de gasto; rotear por tipo de conteúdo.

## 2. Bot no WhatsApp
Um segundo canal de entrada, com o mesmo fluxo e os mesmos comandos. Para isso, o que hoje está acoplado ao
Telegram (`bot.py`, `telegram_api.py`) viraria uma interface de "canal" (receber link, responder, tratar
comandos), com um adaptador por plataforma.
*Decisões em aberto:* a API oficial (WhatsApp Business Cloud API) exige conta Meta, webhook público e modelos de
mensagem; as bibliotecas não oficiais são mais simples, mas arriscam bloqueio do número.

## 3. Tradução para o idioma escolhido
Conteúdo em outros idiomas seria traduzido para o idioma que você selecionar (`pt-BR` por padrão). Hoje o
resumo e os pontos-chave já saem em português por instrução do prompt, mas o idioma é fixo e a transcrição, o
artigo e a legenda ficam no original. A ideia: idioma-alvo configurável, detectar o idioma de origem (o Whisper
já detecta o do áudio), traduzir título, resumo e pontos-chave e, opcionalmente, o conteúdo completo numa seção
"Tradução", sempre guardando o original.
*Decisões em aberto:* traduzir tudo ou só o resumo; qual provedor traduz (custo de textos longos).

## 4. Receita em vídeo vira nota de receita
Quando o link for um vídeo de receita (categoria `receitas`, ou detecção própria), o Kora deixaria de gerar o
resumo genérico e geraria uma **nota de receita** completa: ingredientes com quantidades, modo de preparo
passo a passo, tempo e rendimento, e anotações tiradas do vídeo (dicas, substituições, erros a evitar, tempos e
temperaturas ditos de passagem). É um fluxo à parte, com formato e prompt próprios.

Plano, em etapas pequenas:
1. **Detectar.** Depois da classificação, se a categoria for `receitas` (ou um classificador barato disser que é
   receita), a nota segue o fluxo de receita. Sem receita no conteúdo (só vídeo de "olha que prato lindo"), cai
   no fluxo normal.
2. **Extrair estruturado.** Novo prompt e schema em `llm/` (`prompt_receita`, `schema_receita`): `titulo`,
   `rendimento`, `tempo_preparo`, `ingredientes` (lista de `{item, quantidade, observacao}`, agrupados por
   parte da receita quando houver, como "massa" e "recheio"), `passos` (ordenados), `anotacoes` e
   `incerto` (o que o vídeo não deixou claro). Regra firme no prompt: não inventar quantidade; o que não foi
   dito vai para `incerto`.
3. **Fontes além da fala.** Muita receita mostra as medidas só na legenda ou na tela. Ordem de confiança: legenda
   do post (muitos criadores colam a receita aí), transcrição do áudio, e por último quadros do vídeo.
   Começar só com legenda + transcrição, que já existem no pipeline; ler texto na tela (OCR ou modelo com
   visão sobre quadros extraídos com `ffmpeg`) fica como etapa opcional depois.
4. **Renderizar.** `vault.render` ganha um ramo para `tipo: receita`, com frontmatter extra (`rendimento`,
   `tempo`, `ingredientes_principais`) e seções: Ingredientes (checklist `- [ ]`), Modo de preparo (lista
   numerada), Anotações, Incerto, e a transcrição recolhida no fim. `ler_nota` e a reclassificação precisam
   continuar entendendo o formato.
5. **Interface.** Cartão de receita na galeria e na página da nota (ingredientes e passos em destaque), busca
   por ingrediente, e no Telegram a resposta mostra título, tempo e quantidade de ingredientes.
6. **Testes.** Fixtures de transcrições reais de receita (com e sem medidas) validando o schema, a renderização
   e o caso "não é receita".

*Decisões em aberto:* modelo local pequeno costuma errar quantidades, então talvez exigir um provedor maior
para esse fluxo; o que fazer com receita sem medidas (anotar "a gosto" ou marcar como incompleta);
vídeo em outro idioma (cruza com o item 3, a tradução); lista de compras gerada a partir de várias receitas;
OCR de quadros vale o custo.

## Menores, sem prazo
- Cookies para o YouTube e outros sites que exigem login.
- Suporte ao carrossel `/photo/` do TikTok.
- Embeddings locais (`sqlite-vec`) e um servidor MCP com `buscar_salvos(pergunta)`, quando o volume passar de
  algumas centenas de notas.
