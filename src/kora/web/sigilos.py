"""Cada categoria tem um sigilo desenhado (em templates/_sigilo.html). Aqui só se escolhe qual."""

SIGILOS = ("cruz", "orbita", "espiral", "degraus", "moeda", "pulso", "telhado", "chama", "sorriso", "ponto")

# Categorias de fábrica; as criadas no painel caem num sigilo estável pelo nome.
CONHECIDOS = {
    "programação": "cruz", "ia": "orbita", "design": "espiral", "negócios": "degraus", "finanças": "moeda",
    "saúde": "pulso", "casa": "telhado", "receitas": "chama", "humor": "sorriso", "outros": "ponto",
}


def chave_do_sigilo(categoria: str) -> str:
    nome = (categoria or "").strip().lower()
    if not nome:
        return "marca"  # sem categoria: o marcador da Kora
    return CONHECIDOS.get(nome) or SIGILOS[sum(ord(c) for c in nome) % len(SIGILOS)]
