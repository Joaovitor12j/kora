FALLBACK = "outros"

# categoria -> o que entra nela (vai no prompt). A pasta no vault tem o mesmo nome.
CATEGORIAS: dict[str, str] = {
    "programação": "código, arquitetura, DevOps, repositórios e ferramentas de desenvolvimento",
    "IA": "modelos, agentes, técnicas e novidades de inteligência artificial em si",
    "design": "UI/UX, motion, inspiração visual, identidade visual",
    "negócios": "marketing, vendas, produto, freelas, carreira",
    "finanças": "investimentos, economia pessoal, impostos",
    "saúde": "exercício, alimentação, sono, saúde mental",
    "casa": "plantas, decoração, organização, manutenção",
    "receitas": "culinária",
    "humor": "memes e vídeos engraçados",
    FALLBACK: "nada acima se encaixa",
}

# Desempate: a categoria é o assunto principal do que o conteúdo ensina; a ferramenta vira tag.
REGRA_DESEMPATE = (
    'A categoria é o assunto principal do que o conteúdo ensina; a ferramenta usada vira tag. '
    'Ex.: "Claude faz motion graphics" -> design, com a tag ia. '
    '"Os 10 repositórios do GitHub para agentes" -> IA, com a tag github.'
)


def normalizar_categoria(valor: str) -> str:
    achada = {c.lower(): c for c in CATEGORIAS}.get(valor.strip().lower())
    return achada or FALLBACK
