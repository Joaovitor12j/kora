import json
from pathlib import Path

FALLBACK = "outros"
# Editável pelo painel (kora-web). Sem o arquivo, valem as categorias abaixo.
ARQUIVO = Path("data/categorias.json")

# categoria -> o que entra nela (vai no prompt). A pasta no vault tem o mesmo nome.
PADRAO: dict[str, str] = {
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


def carregar(arquivo: Path | None = None) -> dict[str, str]:
    """Categorias do arquivo do painel; arquivo ausente ou inválido volta ao padrão.

    O fallback fica sempre por último, mesmo que o arquivo o tenha esquecido.
    """
    try:
        lidas = json.loads((arquivo or ARQUIVO).read_text(encoding="utf-8"))
        cats = {str(n).strip(): str(d).strip() for n, d in lidas.items() if str(n).strip()}
    except (OSError, ValueError, AttributeError):
        return dict(PADRAO)
    if not cats:
        return dict(PADRAO)
    fallback = cats.pop(FALLBACK, PADRAO[FALLBACK])
    return {**cats, FALLBACK: fallback}


def salvar(categorias: dict[str, str], arquivo: Path | None = None) -> None:
    destino = arquivo or ARQUIVO
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(categorias, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(destino)


CATEGORIAS: dict[str, str] = carregar()

# Desempate: a categoria é o assunto principal do que o conteúdo ensina; a ferramenta vira tag.
REGRA_DESEMPATE = (
    'A categoria é o assunto principal do que o conteúdo ensina; a ferramenta usada vira tag. '
    'Ex.: "Claude faz motion graphics" -> design, com a tag ia. '
    '"Os 10 repositórios do GitHub para agentes" -> IA, com a tag github.'
)


def normalizar_categoria(valor: str) -> str:
    achada = {c.lower(): c for c in CATEGORIAS}.get(valor.strip().lower())
    return achada or FALLBACK
