# Kora: guia da marca

**Kora** = "salvar" em Akan. A marca nasce do avatar da Kora: o marcador de página luminoso da testa e os padrões geométricos de inspiração Akan do rosto.

**Adjetivos:** precisa, luminosa, curiosa, direta.

## 1. A ideia

**O k é um marcador.** A haste do "k" é o marcador de página (com o entalhe em V embaixo) e o braço e a perna formam um chevron, o mesmo traço dos padrões do rosto. Salvar, o nome e a origem num desenho só. O vão entre haste e chevron deixa as duas peças legíveis, e em tamanho pequeno ele aumenta.

O avatar (personagem) continua existindo como ilustração, na faixa da busca e em materiais de apresentação. Ele não é o logo.

## 2. Arquivos

| Arquivo | Uso |
|---|---|
| `palavra-cor.svg` | logo principal, sobre Noite (`#070A1C`) |
| `palavra-tinta.svg` | sobre fundo claro (Papel ou branco), uma cor |
| `palavra-branca.svg` | sobre foto ou fundo colorido escuro |
| `simbolo-cor.svg`, `simbolo-tinta.svg` | só o "k": avatar, selo, assinatura curta |
| `simbolo-pequeno-cor.svg` | de 16 a 32 px (haste e chevron mais grossos, vão maior) |
| `icone-app.svg`, `favicon.svg` | ícone de app e aba do navegador (símbolo sobre Noite) |
| `png/` | PNGs em 1024 px (símbolo, ícone) e 1200 px (palavras) |
| `web/` | `favicon.ico`, ícones 16 a 512 px e `site.webmanifest` |

A palavra "kora" é desenhada (paths), não é fonte. Não redigitar.

## 3. Cores

| Nome | HEX | Papel |
|---|---|---|
| Noite | `#070A1C` | fundo principal |
| Ciano | `#3DF0FF` | a haste (marcador), destaques, foco |
| Magenta | `#F046B4` | o chevron, segundo destaque |
| Névoa | `#E7ECFF` | texto da palavra sobre Noite |
| Tinta | `#15130F` | versão de uma cor sobre fundo claro |

O ciano e o magenta vêm da luz de contorno do avatar. A Kora na família Jovitor mantém o pingo âmbar `#F2B705` só como identificador do produto na página da marca-mãe, nunca neste logo.

## 4. Área de proteção e tamanho mínimo

- Folga em volta: a largura da haste do "k" em todos os lados.
- Palavra: mínimo 64 px de largura na tela, 18 mm impresso.
- Símbolo: abaixo de 32 px use `simbolo-pequeno-cor.svg` ou `favicon.svg`; mínimo 16 px.

## 5. Não fazer

Não trocar as cores entre haste e chevron; não fechar o vão; não girar, esticar ou inclinar; não pôr ciano e magenta sobre fundo claro (use a versão tinta); não adicionar brilho, sombra ou degradê ao logo (o brilho é do avatar e do fundo do app, não da marca); não usar o símbolo grande abaixo de 32 px; não substituir a palavra por texto em fonte.

## 6. A marca no app (decidido em 2026-11-05)

- **Brilho contido:** o logo é chapado, então o app também. Cor só em destaque (foco, item ativo, selo, alerta); sem glow em botões, campos, cartões ou ícones. Luz de contorno só no personagem. O fundo é noite limpo com o padrão geométrico do rosto bem discreto nas bordas.
- **Tipografia:** Bricolage Grotesque 700 nos títulos e Instrument Sans 400/500/600 no texto (a mesma dupla da marca Jovitor; licença OFL).
- **Sigilos das categorias:** traço chapado (3,6 em grade de 48), pontas retas, juntas em esquina e ângulos de 45°, o vocabulário do k: chevrons, losangos e hastes. "Sem categoria" é o marcador.
- **Avatar:** só na faixa da busca.
- **Cor com significado:** ciano = ativo, foco e ação principal; magenta = pendente, alerta, "sem categoria".

## 7. Regerar

```bash
cd marca
python3 gerar_marca.py                                              # SVGs
uv run --no-project --with cairosvg --with pillow python3 exportar_png.py   # PNGs, ico, manifest
```

Parâmetros (espessura, vão, espaçamento) ficam no topo de `gerar_marca.py`.

## 8. Limites

Não houve busca de anterioridade (INPI ou bases de marcas). Os padrões Akan são geometria própria, sem copiar símbolos Adinkra específicos. Os testes de tamanho pequeno e de uma cor foram visuais.
