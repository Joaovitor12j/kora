"""Notas de tema: uma por assunto (ou categoria sem assunto) com 3 ou mais salvos.

Cada nota junta os salvos do tema (mais novos primeiro, com a primeira frase do resumo) e as
ferramentas mais citadas neles. Só o bloco automático é reescrito; o resto da nota é livre.

Uso: uv run kora-temas [--apply]   (sem --apply só lista os temas)
"""
import argparse
import re
import time
from collections import Counter, defaultdict
from pathlib import Path

from .busca import normalizar
from .config import Settings, get_settings
from .extractors.meta import Meta
from .relacionadas import carregar

PASTA = "Temas"
MINIMO = 3  # salvos para virar tema
INICIO, FIM = "<!-- auto:tema -->", "<!-- /auto:tema -->"


def chave(meta: Meta) -> tuple[str, str]:
    return meta.categoria, meta.assunto


def nome_do_tema(categoria: str, assunto: str) -> str:
    return f"Tema - {categoria} {assunto}".strip()


def agrupar(acervo: list[tuple[Path, Meta]]) -> dict[tuple[str, str], list[tuple[Path, Meta]]]:
    grupos: dict[tuple[str, str], list[tuple[Path, Meta]]] = defaultdict(list)
    for nota, meta in acervo:
        if meta.categoria and meta.categoria != "outros":
            grupos[chave(meta)].append((nota, meta))
    return {k: sorted(v, key=lambda nm: nm[1].criado, reverse=True) for k, v in grupos.items() if len(v) >= MINIMO}


def primeira_frase(texto: str, limite: int = 120) -> str:
    frase = re.split(r"(?<=[.!?])\s", (texto.strip().splitlines() or [""])[0], maxsplit=1)[0]
    return frase if len(frase) <= limite else frase[:limite].rsplit(" ", 1)[0].rstrip(",;:") + "…"


def bloco(itens: list[tuple[Path, Meta]], max_ferramentas: int = 10) -> str:
    cont: Counter = Counter()
    nomes: dict[str, str] = {}
    urls: dict[str, str] = {}
    for _, m in itens:
        for f in m.ferramentas:
            k = normalizar(f["nome"])
            cont[k] += 1
            nomes.setdefault(k, f["nome"])
            if f["url"]:
                urls.setdefault(k, f["url"])
    linhas = [INICIO, f"{len(itens)} salvos, de {itens[-1][1].criado} a {itens[0][1].criado}.", ""]
    if cont:
        linhas += ["### Ferramentas citadas"]
        for k, n in sorted(cont.items(), key=lambda kv: (-kv[1], kv[0]))[:max_ferramentas]:
            link = f"[{nomes[k]}]({urls[k]})" if k in urls else nomes[k]
            linhas.append(f"- {link} ({n})")
        linhas.append("")
    linhas.append("### Salvos")
    for nota, m in itens:
        resumo = primeira_frase(m.resumo)
        linhas.append(f"- [[{nota.stem}]]" + (f" — {resumo}" if resumo else ""))
    linhas.append(FIM)
    return "\n".join(linhas)


def escrever(settings: Settings, hoje: str, aplicar: bool) -> list[tuple[str, int, bool]]:
    """Devolve (nome do tema, salvos, criada?) de cada tema."""
    saida = []
    pasta = settings.saved_dir / PASTA
    for (cat, assunto), itens in sorted(agrupar(carregar(settings.saved_dir)).items(), key=lambda kv: -len(kv[1])):
        nome = nome_do_tema(cat, assunto)
        caminho = pasta / f"{nome}.md"
        novo_bloco = bloco(itens)
        existe = caminho.exists() and INICIO in (atual := caminho.read_text(encoding="utf-8"))
        if existe:
            texto = re.sub(re.escape(INICIO) + r".*?" + re.escape(FIM), lambda _: novo_bloco, atual, flags=re.S)
        else:
            tags = ", ".join(t for t in ("moc", "tema", normalizar(cat), assunto) if t)
            texto = (f"---\ncriado: {hoje}\ntipo: moc\ntags: [{tags}]\n---\n\n# {nome}\n\n"
                     f"Salvos de {cat}{' / ' + assunto if assunto else ''}, agrupados pelo Kora "
                     f"(`kora-temas`). Escreva fora do bloco.\n\n{novo_bloco}\n")
        if aplicar:
            pasta.mkdir(parents=True, exist_ok=True)
            caminho.write_text(texto, encoding="utf-8")
        saida.append((nome, len(itens), not existe))
    return saida


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="grava as notas de tema")
    args = ap.parse_args()
    for nome, n, nova in escrever(get_settings(), time.strftime("%Y-%m-%d"), args.apply):
        print(f"{nome}: {n} salvos ({'nova' if nova else 'atualizada'})")


if __name__ == "__main__":
    main()
