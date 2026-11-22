"""Notas parecidas: similaridade por texto (TF-IDF + cosseno), local e sem chamada de IA.

Uso para o acervo já salvo:
    uv run kora-relacionadas            # mostra o que escreveria
    uv run kora-relacionadas --apply    # acrescenta `## Relacionado` nas notas que ainda não têm
"""
import argparse
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .busca import normalizar
from .config import Settings, get_settings
from .extractors.meta import Meta
from .vault import ler_nota

MINIMO = 0.15  # cosseno mínimo para valer como "parecida" (calibrado no acervo real: abaixo disso vira ruído)
MAXIMO = 3  # parecidas por nota
PALAVRA = re.compile(r"[a-z0-9]{4,}")
# Palavras que aparecem em quase todo post salvo e não dizem de que ele trata.
GENERICAS = {
    "para", "como", "com", "uma", "que", "mais", "seu", "sua", "seus", "suas", "isso", "esse", "essa", "este",
    "esta", "pelo", "pela", "sobre", "entre", "ainda", "tambem", "cada", "muito", "voce", "post", "link",
    "autor", "video", "videos", "conteudo", "dicas", "usar", "usando", "criar", "criacao", "forma", "formas",
    "melhor", "melhores", "essencial", "essenciais", "profissional", "ferramenta", "ferramentas",
}


def tokens(meta: Meta) -> Counter:
    """Título, tags e assunto pesam mais que o resumo (repetidos para contar mais)."""
    texto = " ".join([
        *([meta.titulo] * 3), *([" ".join(meta.tags)] * 3), meta.assunto, meta.categoria,
        meta.resumo, " ".join(meta.pontos_chave),
    ])
    return Counter(p for p in PALAVRA.findall(normalizar(texto)) if p not in GENERICAS)


@dataclass
class Parecida:
    nota: Path
    meta: Meta
    score: float


def _vetores(docs: list[Counter]) -> list[dict[str, float]]:
    n = len(docs)
    df = Counter(t for d in docs for t in d)
    vetores = []
    for d in docs:
        v = {t: (1 + math.log(c)) * math.log(1 + n / df[t]) for t, c in d.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vetores.append({t: x / norma for t, x in v.items()})
    return vetores


def _cosseno(a: dict[str, float], b: dict[str, float]) -> float:
    if len(a) > len(b):
        a, b = b, a
    return sum(x * b.get(t, 0.0) for t, x in a.items())


def carregar(raiz: Path) -> list[tuple[Path, Meta]]:
    notas = []
    for nota in sorted(raiz.rglob("*.md")):
        try:
            if "tipo: link" not in nota.read_text(encoding="utf-8")[:2000]:
                continue
            meta, status = ler_nota(nota)
        except OSError:
            continue
        if status == "processado":
            notas.append((nota, meta))
    return notas


def parecidas(acervo: list[tuple[Path, Meta]], meta: Meta, minimo: float = MINIMO, maximo: int = MAXIMO) -> list[Parecida]:
    """As notas do acervo mais parecidas com `meta` (que pode ainda não estar nele)."""
    outras = [(n, m) for n, m in acervo if m.url != meta.url]
    if not outras:
        return []
    *vet, alvo = _vetores([tokens(m) for _, m in outras] + [tokens(meta)])
    pontuadas = [Parecida(n, m, _cosseno(alvo, v)) for (n, m), v in zip(outras, vet)]
    return sorted((p for p in pontuadas if p.score >= minimo), key=lambda p: -p.score)[:maximo]


def linha(p: Parecida) -> str:
    return f"- [[{p.nota.stem}]]"


def para_acervo(acervo: list[tuple[Path, Meta]], minimo: float = MINIMO, maximo: int = MAXIMO) -> dict[Path, list[Parecida]]:
    """Parecidas de cada nota do acervo, com uma só passada de TF-IDF."""
    vet = _vetores([tokens(m) for _, m in acervo])
    saida = {}
    for i, (nota, meta) in enumerate(acervo):
        ps = [Parecida(n, m, _cosseno(vet[i], vet[j])) for j, (n, m) in enumerate(acervo) if j != i and m.url != meta.url]
        saida[nota] = sorted((p for p in ps if p.score >= minimo), key=lambda p: -p.score)[:maximo]
    return saida


def _tem_secao(texto: str) -> bool:
    return re.search(r"^## Relacionado\s*$", texto, re.M) is not None


def acrescentar(texto: str, itens: list[Parecida]) -> str:
    """Põe `## Relacionado` no fim da nota; se ela já tem a seção (feita à mão), não mexe."""
    if not itens or _tem_secao(texto):
        return texto
    return texto.rstrip("\n") + "\n\n## Relacionado\n" + "\n".join(linha(p) for p in itens) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="grava a seção nas notas")
    args = ap.parse_args()
    acervo = carregar(get_settings().saved_dir)
    n = 0
    for nota, itens in para_acervo(acervo).items():
        texto = nota.read_text(encoding="utf-8")
        novo = acrescentar(texto, itens)
        if novo == texto:
            continue
        n += 1
        print(f"{nota.stem[:60]} -> " + " | ".join(f"{p.nota.stem[11:50]} ({p.score:.2f})" for p in itens))
        if args.apply:
            nota.write_text(novo, encoding="utf-8")
    print(f"{n} nota(s) {'alterada(s)' if args.apply else 'seriam alteradas'}")


if __name__ == "__main__":
    main()
