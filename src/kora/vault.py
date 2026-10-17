import json
import re
import time
from pathlib import Path

from .extractors.meta import Meta

INVALID = re.compile(r'[\\/:*?"<>|#^\[\]\n\r\t]+')


def slug(text: str, limit: int = 60) -> str:
    cleaned = re.sub(r"\s+", " ", INVALID.sub(" ", text)).strip(" .")
    return cleaned[:limit].rstrip(" .") or "sem titulo"


def _q(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)  # JSON é YAML válido


def _resumo(meta: Meta) -> list[str]:
    if not meta.resumo:
        return []
    pontos = [f"- {p}" for p in meta.pontos_chave]
    return ["## Resumo", meta.resumo, "", *(["## Pontos-chave", *pontos, ""] if pontos else [])]


def _conteudo(meta: Meta) -> list[str]:
    if not meta.conteudo:
        return []
    if meta.conteudo_tipo == "artigo":
        return ["## Conteúdo", meta.conteudo, ""]
    corpo = [f"> {linha}" for linha in meta.conteudo.splitlines() if linha.strip()]
    titulo = "Transcrição completa" if meta.conteudo_tipo == "transcricao" else "Legenda do vídeo"
    return ["## Transcrição", f"> [!note]- {titulo}", *corpo, ""]


def render(meta: Meta, criado: str) -> str:
    lines = [
        "---",
        f"criado: {criado}",
        "tipo: link",
        f"plataforma: {meta.plataforma}",
        f"url: {_q(meta.url)}",
        f"autor: {_q(meta.autor)}",
    ]
    if meta.publicado:
        lines.append(f"publicado: {meta.publicado}")
    if meta.categoria:
        lines.append(f"categoria: {meta.categoria}")
    lines += [
        f"tags: [{', '.join(meta.tags)}]",
        f"status: {'processado' if meta.categoria else 'pendente'}",
    ]
    if meta.ia:
        lines.append(f"ia: {_q(meta.ia)}")
    lines += [
        "---",
        "",
        f"# {meta.titulo}",
        "",
        *_resumo(meta),
        "## Legenda original",
        meta.descricao or "_(sem legenda)_",
        "",
    ]
    lines += _conteudo(meta)
    return "\n".join(lines)


def note_path(directory: Path, meta: Meta, criado: str, item_id: int) -> Path:
    base = f"{criado} {meta.plataforma} - {slug(meta.titulo)}"
    path = directory / f"{base}.md"
    if path.exists() and f"url: {_q(meta.url)}" not in path.read_text(encoding="utf-8"):
        path = directory / f"{base} ({item_id}).md"  # outro link com mesmo título
    return path


def write_note(directory: Path, meta: Meta, item_id: int, now: float | None = None) -> Path:
    """Reprocessar o mesmo link sobrescreve a mesma nota (idempotente)."""
    criado = meta.criado or time.strftime("%Y-%m-%d", time.localtime(now))
    directory.mkdir(parents=True, exist_ok=True)
    path = note_path(directory, meta, criado, item_id)
    path.write_text(render(meta, criado), encoding="utf-8")
    return path


def destino(settings, meta: Meta) -> Path:
    """Pasta da categoria; sem categoria (IA indisponível) a nota espera em _inbox."""
    return settings.saved_dir / meta.categoria if meta.categoria else settings.inbox_dir


def tags_existentes(raiz: Path, limite: int = 80) -> list[str]:
    """Tags já usadas nas notas salvas, da mais frequente para a menos, para a IA reaproveitar."""
    contagem: dict[str, int] = {}
    for nota in raiz.rglob("*.md"):
        try:
            cabecalho = nota.read_text(encoding="utf-8").split("---", 2)[1]
        except (OSError, IndexError):
            continue
        m = re.search(r"^tags:\s*\[(.*?)\]\s*$", cabecalho, re.M)
        for tag in (t.strip() for t in (m.group(1).split(",") if m else [])):
            if tag:
                contagem[tag] = contagem.get(tag, 0) + 1
    return sorted(contagem, key=lambda t: (-contagem[t], t))[:limite]


def _frontmatter(texto: str) -> tuple[str, str]:
    """(cabeçalho sem os ---, resto). Nota sem frontmatter devolve ('', texto)."""
    if not texto.startswith("---\n"):
        return "", texto
    fim = texto.find("\n---", 4)
    return (texto[4:fim], texto[fim + 4:]) if fim != -1 else ("", texto)


def _campo(cabecalho: str, nome: str) -> str:
    m = re.search(rf"^{nome}:\s*(.*?)\s*$", cabecalho, re.M)
    return m.group(1) if m else ""


def _json_ou_texto(valor: str) -> str:
    try:
        lido = json.loads(valor)
        return lido if isinstance(lido, str) else valor
    except ValueError:
        return valor


def ler_nota(path: Path) -> tuple[Meta, str]:
    """Reconstrói o Meta de uma nota gerada pelo Kora. Devolve (meta, status)."""
    texto = path.read_text(encoding="utf-8")
    cab, corpo = _frontmatter(texto)
    tags = _campo(cab, "tags").strip("[]")
    meta = Meta(
        url=_json_ou_texto(_campo(cab, "url")),
        plataforma=_campo(cab, "plataforma"),
        titulo=(re.search(r"^# (.+)$", corpo, re.M) or [None, path.stem])[1].strip(),
        autor=_json_ou_texto(_campo(cab, "autor")),
        publicado=_campo(cab, "publicado"),
        categoria=_campo(cab, "categoria"),
        tags=[t.strip() for t in tags.split(",") if t.strip()],
        criado=_campo(cab, "criado"),
        ia=_json_ou_texto(_campo(cab, "ia")),
    )
    secoes = {nome.strip(): corpo_secao.strip("\n") for nome, corpo_secao in
              re.findall(r"^## (.+?)\n(.*?)(?=^## |\Z)", corpo, re.M | re.S)}
    meta.resumo = secoes.get("Resumo", "")
    meta.pontos_chave = [l[2:].strip() for l in secoes.get("Pontos-chave", "").splitlines() if l.startswith("- ")]
    legenda = secoes.get("Legenda original", "")
    meta.descricao = "" if legenda == "_(sem legenda)_" else legenda
    if "Conteúdo" in secoes:
        meta.conteudo, meta.conteudo_tipo = secoes["Conteúdo"], "artigo"
    elif "Transcrição" in secoes:
        linhas = secoes["Transcrição"].splitlines()
        meta.conteudo_tipo = "transcricao" if "Transcrição completa" in linhas[0] else "legenda"
        meta.conteudo = "\n".join(l[2:] if l.startswith("> ") else l for l in linhas[1:] if l.strip())
    return meta, _campo(cab, "status")


def mover_categoria(settings, nota: Path, categoria: str) -> Path:
    """Troca `categoria:` no frontmatter e move a nota para a pasta da categoria."""
    texto = nota.read_text(encoding="utf-8")
    cab, resto = _frontmatter(texto)
    if not cab:
        raise ValueError(f"{nota.name} não tem frontmatter")
    linha = f"categoria: {categoria}"
    if re.search(r"^categoria:.*$", cab, re.M):
        cab = re.sub(r"^categoria:.*$", linha, cab, count=1, flags=re.M)
    else:  # nota pendente: entra antes de `tags:`
        cab = re.sub(r"^(tags:)", rf"{linha}\n\1", cab, count=1, flags=re.M)
    pasta = settings.saved_dir / categoria
    pasta.mkdir(parents=True, exist_ok=True)
    novo = pasta / nota.name
    n = 2
    while novo.exists() and novo != nota:
        novo = pasta / f"{nota.stem} ({n}){nota.suffix}"
        n += 1
    novo.write_text(f"---\n{cab}\n---{resto}", encoding="utf-8")
    if novo != nota:
        nota.unlink()
    return novo
