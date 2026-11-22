"""Normalização de tags: uma forma só por assunto (sem acento, sem variantes, sem ruído).

Uso para limpar as notas já salvas:
    uv run kora-tags            # mostra o que mudaria
    uv run kora-tags --apply    # grava
"""
import argparse
import re
import unicodedata
from collections import Counter
from pathlib import Path

from .config import get_settings

PLATAFORMAS = {"instagram", "tiktok", "x", "twitter", "youtube", "web", "reels", "reelsinstagram"}

# Variante -> forma canônica. Chaves já em forma normalizada (minúsculas, sem acento).
SINONIMOS = {
    "motiongraphics": "motion-graphics",
    "motion-graphic": "motion-graphics",
    "animation": "animacao",
    "ai": "ia",
    "inteligencia-artificial": "ia",
    "productivdade": "produtividade",
    "agents": "agent",
    "agente": "agent",
    "agentes": "agent",
    "uiux": "ui-ux",
    "ux-ui": "ui-ux",
    "open-source": "opensource",
    "videos": "video",
}


def normalizar_tag(raw: str) -> str:
    t = unicodedata.normalize("NFKD", raw.strip().lstrip("#").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^\w-]", "", re.sub(r"\s+", "-", t)).strip("-_")
    return SINONIMOS.get(t, t)


def normalizar_tags(tags: list[str], categoria: str = "", plataforma: str = "", maximo: int | None = None) -> list[str]:
    """Normaliza, tira duplicadas e as que só repetem plataforma ou categoria (já estão nos campos próprios)."""
    ruido = PLATAFORMAS | {normalizar_tag(categoria), normalizar_tag(plataforma)} - {""}
    saida = list(dict.fromkeys(t for t in map(normalizar_tag, tags) if t and t not in ruido))
    return saida[:maximo]


_LINHA = re.compile(r"^tags:[ \t]*\[(.*?)\][ \t]*$", re.M)


def limpar_nota(texto: str) -> str:
    """Reescreve a linha `tags:` do frontmatter. Notas sem ela ou que não são links ficam como estão."""
    if not texto.startswith("---\n"):
        return texto
    fim = texto.find("\n---", 4)
    if fim == -1:
        return texto
    cab = texto[4:fim]
    if "tipo: link" not in cab:
        return texto
    m = _LINHA.search(cab)
    if not m:
        return texto
    cat = re.search(r"^categoria:[ \t]*(.*?)[ \t]*$", cab, re.M)
    plat = re.search(r"^plataforma:[ \t]*(.*?)[ \t]*$", cab, re.M)
    velhas = [t.strip() for t in m.group(1).split(",") if t.strip()]
    novas = normalizar_tags(velhas, cat.group(1) if cat else "", plat.group(1) if plat else "")
    cab = cab[:m.start()] + f"tags: [{', '.join(novas)}]" + cab[m.end():]
    return f"---\n{cab}{texto[fim:]}"


def limpar_acervo(raiz: Path, aplicar: bool = False) -> tuple[int, Counter, Counter]:
    """Devolve (notas alteradas, tags antes, tags depois)."""
    antes: Counter = Counter()
    depois: Counter = Counter()
    alteradas = 0
    for nota in sorted(raiz.rglob("*.md")):
        try:
            texto = nota.read_text(encoding="utf-8")
        except OSError:
            continue
        novo = limpar_nota(texto)
        for contagem, t in ((antes, texto), (depois, novo)):
            m = _LINHA.search(t.split("\n---", 1)[0]) if t.startswith("---\n") else None
            contagem.update(x.strip() for x in (m.group(1).split(",") if m else []) if x.strip())
        if novo != texto:
            alteradas += 1
            if aplicar:
                nota.write_text(novo, encoding="utf-8")
    return alteradas, antes, depois


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="grava as mudanças (sem isso só mostra o resumo)")
    args = ap.parse_args()
    raiz = get_settings().saved_dir
    alteradas, antes, depois = limpar_acervo(raiz, args.apply)
    print(f"{alteradas} nota(s) {'alterada(s)' if args.apply else 'seriam alteradas'}; "
          f"tags únicas {len(antes)} -> {len(depois)}")
    if not args.apply:
        print("Use --apply para gravar.")


if __name__ == "__main__":
    main()
