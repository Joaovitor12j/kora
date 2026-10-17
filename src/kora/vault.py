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
    lines += [
        "tags: []",
        "status: pendente",
        "---",
        "",
        f"# {meta.titulo}",
        "",
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
