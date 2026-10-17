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
    criado = time.strftime("%Y-%m-%d", time.localtime(now))
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
