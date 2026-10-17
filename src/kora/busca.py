import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .config import Settings
from .extractors.meta import Meta
from .vault import ler_nota

LIMITE_PADRAO = 5


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento, para 'programacao' achar 'programação'."""
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


@dataclass
class Resultado:
    nota: Path
    meta: Meta
    pontos: int


def _campos(meta: Meta) -> list[tuple[int, str]]:
    """(peso, texto) por campo: título e tags valem mais que o corpo."""
    return [
        (5, meta.titulo),
        (4, " ".join([meta.categoria, *meta.tags])),
        (2, " ".join([meta.autor, meta.resumo, *meta.pontos_chave])),
        (1, " ".join([meta.descricao, meta.conteudo, meta.plataforma])),
    ]


def pontuar(meta: Meta, termos: list[str]) -> int:
    """0 se algum termo não aparece em lugar nenhum (busca E); senão soma o maior peso de cada termo."""
    campos = [(peso, normalizar(texto)) for peso, texto in _campos(meta)]
    total = 0
    for termo in termos:
        pesos = [peso for peso, texto in campos if termo in texto]
        if not pesos:
            return 0
        total += max(pesos)
    return total


def buscar(settings: Settings, consulta: str, limite: int = LIMITE_PADRAO) -> list[Resultado]:
    termos = normalizar(consulta).split()
    if not termos:
        return []
    achados = []
    for nota in settings.saved_dir.rglob("*.md"):
        try:
            if "tipo: link" not in nota.read_text(encoding="utf-8")[:2000]:
                continue  # ignora o índice Salvos.md e notas que não são do Kora
            meta, _ = ler_nota(nota)
        except OSError:
            continue
        if pontos := pontuar(meta, termos):
            achados.append(Resultado(nota, meta, pontos))
    # Mais pontos primeiro; no empate, a mais recente (sort estável, então ordena por data antes).
    achados.sort(key=lambda r: r.meta.criado, reverse=True)
    achados.sort(key=lambda r: r.pontos, reverse=True)
    return achados[:limite]


def _frase(texto: str, limite: int = 140) -> str:
    primeira = texto.strip().splitlines()[0] if texto.strip() else ""
    return primeira if len(primeira) <= limite else primeira[:limite].rsplit(" ", 1)[0] + "…"


def formatar(resultados: list[Resultado], consulta: str) -> str:
    if not resultados:
        return f'Nada encontrado para "{consulta}".'
    linhas = [f'{len(resultados)} resultado(s) para "{consulta}":']
    for i, r in enumerate(resultados, 1):
        m = r.meta
        onde = " · ".join(p for p in (m.categoria or "sem categoria", m.plataforma, m.criado) if p)
        linhas.append(f"\n{i}. {m.titulo}\n   {onde}")
        if resumo := _frase(m.resumo or m.descricao):
            linhas.append(f"   {resumo}")
        linhas.append(f"   {m.url}")
    return "\n".join(linhas)
