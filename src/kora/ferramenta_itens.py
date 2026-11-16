"""Itens de ferramenta (nome + URL): limpeza do que a IA devolve e leitura/escrita da seção da nota.

Sem dependência do vault, para o vault e o schema da IA poderem importar sem ciclo.
"""
import re
import unicodedata

from .extractors.meta import Meta
from .urls import extract_urls


def normalizar(texto: str) -> str:
    """Minúsculas e sem acento (igual ao busca.normalizar, copiado para não criar ciclo com o vault)."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()


MAX_FERRAMENTAS = 8
# Categorias em que "ferramenta" não faz sentido (ingredientes, perfis e lojas viravam ferramenta).
SEM_FERRAMENTAS = {"receitas", "casa", "saúde", "finanças", "humor"}
# Redes onde o post foi publicado não contam como ferramenta do conteúdo.
PLATAFORMAS = {"instagram", "tiktok", "x", "twitter", "youtube"}
# Grafias erradas frequentes (a transcrição do áudio ouve "Claude" como "Cloud").
CANONICAS = {"cloud code": "Claude Code", "claudecode": "Claude Code", "claude-code": "Claude Code"}
_URL = re.compile(r"^https?://\S+$", re.I)

SCHEMA_ITEM = {
    "type": "object",
    "properties": {"nome": {"type": "string"}, "url": {"type": "string"}},
    "required": ["nome", "url"],
    "additionalProperties": False,
}
SCHEMA_CAMPO = {"type": "array", "items": SCHEMA_ITEM}


def _alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", normalizar(s))


HOSPEDEIROS = {"github.com", "gitlab.com", "huggingface.co", "npmjs.com", "pypi.org"}


def url_combina(nome: str, url: str) -> bool:
    """O link tem que ser da própria ferramenta: o nome (sem símbolos) aparece na URL.

    Em hospedeiros de repositório (GitHub etc.) o nome tem que estar no caminho, não só no domínio:
    evita pôr o repositório de outra ferramenta (Remotion -> github.com/x/video-shotcraft) e o link
    de um repo qualquer em "GitHub".
    """
    sem_esquema = url.split("//", 1)[-1]
    host, _, caminho = sem_esquema.partition("/")
    host = host.removeprefix("www.").lower()
    n = _alnum(nome)
    return bool(n) and n in _alnum(caminho if host in HOSPEDEIROS else sem_esquema)


def limpar(itens: list, texto: str = "") -> list[dict[str, str]]:
    """Normaliza o que a IA devolveu. A URL só fica se aparecer no texto do post (a IA não inventa link)."""
    conhecidas = {u.lower().rstrip("/") for u in extract_urls(texto)}
    vistos: dict[str, dict[str, str]] = {}
    for item in itens or []:
        nome, url = (item, "") if isinstance(item, str) else (item.get("nome", ""), item.get("url", ""))
        nome = re.sub(r"[\[\],\n]+", " ", str(nome)).strip()
        url = str(url).strip()
        if not nome or len(nome) > 60:
            continue
        nome = CANONICAS.get(normalizar(nome), nome)
        if normalizar(nome) in PLATAFORMAS:
            continue
        if not (_URL.match(url) and url.lower().rstrip("/") in conhecidas and url_combina(nome, url)):
            url = ""
        chave = normalizar(nome)
        if chave not in vistos or (url and not vistos[chave]["url"]):
            vistos[chave] = {"nome": nome, "url": url}
    return list(vistos.values())[:MAX_FERRAMENTAS]


def texto_do_post(meta: Meta) -> str:
    return f"{meta.descricao}\n{meta.conteudo}"


def linhas_secao(itens: list[dict[str, str]]) -> list[str]:
    return [f"- [{f['nome']}]({f['url']})" if f["url"] else f"- {f['nome']}" for f in itens]


_LINK = re.compile(r"^- \[(.+?)\]\((\S+?)\)\s*$")


def ler_secao(corpo: str) -> list[dict[str, str]]:
    saida = []
    for l in corpo.splitlines():
        if m := _LINK.match(l):
            saida.append({"nome": m.group(1), "url": m.group(2)})
        elif l.startswith("- "):
            saida.append({"nome": l[2:].strip(), "url": ""})
    return saida


