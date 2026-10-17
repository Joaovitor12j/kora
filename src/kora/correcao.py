import re
from pathlib import Path

from .config import Settings
from .db import Item, Queue
from .taxonomia import CATEGORIAS
from .vault import mover_categoria

PADRAO = re.compile(r"^\s*categoria\s*:\s*(.+?)\s*$", re.IGNORECASE)


def pedido_de_categoria(texto: str) -> str | None:
    m = PADRAO.match(texto or "")
    return m.group(1) if m else None


def _item(queue: Queue, chat_id: int, respondida: int) -> Item | str:
    item = queue.find_by_resposta(chat_id, respondida)
    if item:
        return item
    candidatos = queue.find_by_message(chat_id, respondida)  # respondeu ao próprio link
    if len(candidatos) == 1:
        return candidatos[0]
    if candidatos:
        return "Essa mensagem tinha vários links; responda à resposta do bot do link que quer corrigir."
    return "Não sei a qual link isso se refere. Responda à mensagem em que o bot avisou \"salvo…\"."


def corrigir_categoria(queue: Queue, settings: Settings, chat_id: int, respondida: int, pedido: str) -> str:
    """Move a nota para a categoria pedida. Devolve o texto de resposta ao usuário."""
    categoria = {c.lower(): c for c in CATEGORIAS}.get(pedido.strip().lower())
    if not categoria:
        return f"Categoria desconhecida: {pedido}. Use uma destas: {', '.join(CATEGORIAS)}."
    item = _item(queue, chat_id, respondida)
    if isinstance(item, str):
        return item
    if not item.nota_path or not Path(item.nota_path).exists():
        return "Não achei a nota desse link (foi movida ou apagada?)."
    atual = Path(item.nota_path)
    novo = mover_categoria(settings, atual, categoria)
    queue.set_nota(item.id, item.titulo or atual.stem, str(novo))
    return f"Movido para {categoria}: {item.titulo or atual.stem}"
