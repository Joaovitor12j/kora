"""Leitura do vault para a interface: lista, filtros e facetas. O vault continua sendo a fonte da verdade."""
import time
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from ..busca import normalizar, pontuar
from ..config import Settings
from ..extractors.meta import Meta
from ..vault import ler_nota

LOTE = 60
PENDENTE = "pendente"


@dataclass
class Entrada:
    rel: str  # caminho dentro de VAULT_SAVED_DIR, com "/"
    meta: Meta
    status: str
    mtime: float
    pontos: int = 0

    @property
    def pendente(self) -> bool:
        return self.status == PENDENTE

    @property
    def data(self) -> str:
        return self.meta.criado or time.strftime("%Y-%m-%d", time.localtime(self.mtime))

    @property
    def pagina(self) -> str:
        """Primeira frase do resumo, para a linha da lista."""
        return self.meta.resumo.split("\n")[0].strip()


_cache: dict[Path, tuple[int, Entrada | None]] = {}


def listar(settings: Settings) -> list[Entrada]:
    """Todas as notas do Kora, da mais recente para a mais antiga. Relê só o que mudou no disco."""
    raiz = settings.saved_dir
    vistas, entradas = set(), []
    for nota in raiz.rglob("*.md"):
        try:
            mtime = nota.stat().st_mtime_ns
            guardada = _cache.get(nota)
            if guardada and guardada[0] == mtime:
                entrada = guardada[1]
            else:
                entrada = _ler(raiz, nota, mtime)
                _cache[nota] = (mtime, entrada)
        except OSError:
            continue
        vistas.add(nota)
        if entrada:
            entradas.append(entrada)
    for velha in set(_cache) - vistas:
        del _cache[velha]
    entradas.sort(key=lambda e: (e.data, e.mtime), reverse=True)
    return entradas


def _ler(raiz: Path, nota: Path, mtime_ns: int) -> Entrada | None:
    try:
        if "tipo: link" not in nota.read_text(encoding="utf-8")[:2000]:
            return None  # o índice Salvos.md e notas que não são do Kora
        meta, status = ler_nota(nota)
    except (OSError, UnicodeDecodeError):
        return None
    return Entrada(nota.relative_to(raiz).as_posix(), meta, status, mtime_ns / 1e9)


def resolver(settings: Settings, rel: str) -> Path | None:
    """Caminho absoluto da nota, só se estiver dentro da pasta de salvos."""
    raiz = settings.saved_dir.resolve()
    try:
        path = (raiz / rel).resolve()
    except (OSError, ValueError):
        return None
    if path.suffix != ".md" or not path.is_file() or not path.is_relative_to(raiz):
        return None
    return path


@dataclass
class Filtro:
    q: str = ""
    categoria: str = ""
    plataforma: str = ""
    tag: str = ""
    dias: int = 0
    pendentes: bool = False
    limite: int = LOTE

    def ativo(self) -> bool:
        return bool(self.q or self.categoria or self.plataforma or self.tag or self.dias or self.pendentes)


def filtrar(entradas: list[Entrada], f: Filtro, hoje: date | None = None) -> list[Entrada]:
    achadas = entradas
    if f.pendentes:
        achadas = [e for e in achadas if e.pendente]
    if f.categoria:
        achadas = [e for e in achadas if e.meta.categoria == f.categoria]
    if f.plataforma:
        achadas = [e for e in achadas if e.meta.plataforma == f.plataforma]
    if f.tag:
        achadas = [e for e in achadas if f.tag in e.meta.tags]
    if f.dias:
        corte = ((hoje or date.today()) - timedelta(days=f.dias)).isoformat()
        achadas = [e for e in achadas if e.data >= corte]
    termos = normalizar(f.q).split()
    if termos:
        pontuadas = []
        for e in achadas:
            if pontos := pontuar(e.meta, termos):
                e.pontos = pontos
                pontuadas.append(e)
        achadas = sorted(pontuadas, key=lambda e: e.pontos, reverse=True)  # empate: mantém a ordem por data
    return achadas


@dataclass
class Facetas:
    categorias: list[tuple[str, int]]
    plataformas: list[tuple[str, int]]
    tags: list[tuple[str, int]]
    pendentes: int
    total: int


def facetas(entradas: list[Entrada], categorias_configuradas: list[str], max_tags: int = 14) -> Facetas:
    cats = Counter(e.meta.categoria for e in entradas if e.meta.categoria)
    plats = Counter(e.meta.plataforma for e in entradas if e.meta.plataforma)
    tags = Counter(t for e in entradas for t in e.meta.tags)
    # A ordem do painel vale; categorias antigas (já removidas da configuração) vêm depois.
    conhecidas = [(c, cats.pop(c, 0)) for c in categorias_configuradas]
    extras = sorted(cats.items(), key=lambda kv: -kv[1])
    return Facetas(
        categorias=[(c, n) for c, n in conhecidas + extras if n],
        plataformas=plats.most_common(),
        tags=sorted(tags.items(), key=lambda kv: (-kv[1], kv[0]))[:max_tags],
        pendentes=sum(e.pendente for e in entradas),
        total=len(entradas),
    )


def data_br(iso: str) -> str:
    """'2026-10-17' -> '17-10-2026'. Texto que não é data volta como veio."""
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return d.strftime("%d-%m-%Y")


def rotulo_dia(iso: str, hoje: date | None = None) -> str:
    """'hoje', 'ontem' ou 'dd-mm-aaaa'."""
    hoje = hoje or date.today()
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return "sem data"
    if d == hoje:
        return "hoje"
    if d == hoje - timedelta(days=1):
        return "ontem"
    return data_br(iso)


def agrupar_por_dia(entradas: list[Entrada], hoje: date | None = None) -> list[tuple[str, list[Entrada]]]:
    """Mantém a ordem recebida; só abre um grupo novo quando o dia muda."""
    grupos: list[tuple[str, list[Entrada]]] = []
    ultimo = None
    for e in entradas:
        if e.data != ultimo:
            grupos.append((rotulo_dia(e.data, hoje), []))
            ultimo = e.data
        grupos[-1][1].append(e)
    return grupos
