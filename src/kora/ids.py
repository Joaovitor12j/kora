"""Dá `id:` (e `aliases:`) às notas já salvas que ainda não têm. O id vem da URL (ver Meta.id).

Uso: uv run kora-ids [--apply]   (sem --apply só conta)
"""
import argparse
import re

from .config import get_settings
from .vault import ler_nota

_URL = re.compile(r"^(url:.*)$", re.M)


def com_id(texto: str, id_: str) -> str:
    """Insere `id:` depois de `url:`; sem `aliases:` própria, cria `aliases: [id]` (o que o usuário pôs fica)."""
    cab = texto.split("\n---", 1)[0]
    if re.search(r"^id:", cab, re.M) or not _URL.search(cab):
        return texto
    extra = f"\nid: {id_}" + ("" if re.search(r"^aliases:", cab, re.M) else f"\naliases: [{id_}]")
    return _URL.sub(lambda m: m.group(1) + extra, texto, count=1)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="grava o id nas notas")
    args = ap.parse_args()
    n = 0
    for nota in sorted(get_settings().saved_dir.rglob("*.md")):
        try:
            texto = nota.read_text(encoding="utf-8")
            if "tipo: link" not in texto[:2000]:
                continue
            meta, _ = ler_nota(nota)
        except OSError:
            continue
        novo = com_id(texto, meta.id)
        if novo != texto:
            n += 1
            if args.apply:
                nota.write_text(novo, encoding="utf-8")
    print(f"{n} nota(s) {'alterada(s)' if args.apply else 'seriam alteradas'}")


if __name__ == "__main__":
    main()
