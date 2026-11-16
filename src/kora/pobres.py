"""Marca com `conteudo: pobre` as notas já salvas que quase não tinham texto para resumir.

Uso: uv run kora-pobres [--apply]   (sem --apply só lista)
"""
import argparse
import re

from .config import get_settings
from .vault import ler_nota


def marcar(texto: str) -> str:
    """Insere `conteudo: pobre` antes de `tags:`, como nas notas novas; nota que já tem a marca não muda."""
    if re.search(r"^conteudo:", texto.split("\n---", 1)[0], re.M):
        return texto
    return re.sub(r"^(tags:)", r"conteudo: pobre\n\1", texto, count=1, flags=re.M)


def pobres(raiz):
    for nota in sorted(raiz.rglob("*.md")):
        try:
            meta, _ = ler_nota(nota)
            texto = nota.read_text(encoding="utf-8")
        except OSError:
            continue
        if "tipo: link" in texto[:600] and meta.pobre and marcar(texto) != texto:
            yield nota, texto


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="grava a marca nas notas")
    args = ap.parse_args()
    n = 0
    for nota, texto in pobres(get_settings().saved_dir):
        print(nota.name)
        n += 1
        if args.apply:
            nota.write_text(marcar(texto), encoding="utf-8")
    print(f"{n} nota(s) {'marcada(s)' if args.apply else 'seriam marcadas'}")


if __name__ == "__main__":
    main()
