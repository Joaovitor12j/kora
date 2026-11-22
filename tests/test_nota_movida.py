"""Notas movidas de pasta (ex.: agrupar-por-mes.py) não quebram a fila nem a correção de categoria."""
import pytest

from kora import worker
from kora.config import Settings
from kora.correcao import corrigir_categoria
from kora.db import Queue
from kora.extractors.meta import Meta
from kora.vault import achar_nota, ler_nota, mover_categoria, write_note

URL = "https://x.com/a/status/1"


@pytest.fixture
def s(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault",
                    db_path=tmp_path / "q.sqlite", _env_file=None)


@pytest.fixture
def q(s):
    queue = Queue(s.db_path)
    yield queue
    queue.close()


def salva_e_agrupa_por_mes(s, q):
    """Salva a nota, registra na fila e move para <categoria>/<mês>/, como o script mensal faz."""
    item, _ = q.enqueue(URL, URL, "x", chat_id=1, message_id=5)
    meta = Meta(url=URL, plataforma="x", titulo="Motion", categoria="design", resumo="r", ia="a/m",
                criado="2026-10-05", descricao="d" * 250)
    antiga = write_note(s.saved_dir / "design", meta, item.id)
    q.done(item.id, "Motion", str(antiga))
    movida = antiga.parent / "2026-10" / antiga.name
    movida.parent.mkdir()
    antiga.rename(movida)
    return item, antiga, movida


def test_achar_nota_segue_a_nota_movida(s, q):
    item, antiga, movida = salva_e_agrupa_por_mes(s, q)
    assert achar_nota(s.saved_dir, URL, str(antiga)) == movida
    assert achar_nota(s.saved_dir, URL) == movida
    assert achar_nota(s.saved_dir, "https://x.com/outro") is None
    assert achar_nota(s.saved_dir, URL, str(movida)) == movida


def test_corrigir_categoria_acha_nota_movida_e_mantem_o_mes(s, q):
    item, _, movida = salva_e_agrupa_por_mes(s, q)
    q.set_resposta(item.id, 50)
    resp = corrigir_categoria(q, s, 1, 50, "IA")
    novo = s.saved_dir / "IA" / "2026-10" / movida.name
    assert resp.startswith("Movido para IA") and novo.exists() and not movida.exists()
    assert q.get(item.id).nota_path == str(novo)


def test_refazer_nota_movida_nao_duplica_e_mantem_a_data(s, q, monkeypatch):
    item, antiga, movida = salva_e_agrupa_por_mes(s, q)
    monkeypatch.setattr(worker, "fetch_meta", lambda url, plat: Meta(url=url, plataforma=plat, titulo="Motion", descricao="d" * 250))
    monkeypatch.setattr(worker, "send_message", lambda *a: 1)
    q.requeue_para_refazer(item.id) if hasattr(q, "requeue_para_refazer") else q._conn.execute(
        "UPDATE itens SET status = 'na_fila' WHERE id = ?", (item.id,))
    worker.run_once(q, s)
    notas = [n for n in s.saved_dir.rglob("*.md") if "tipo: link" in n.read_text(encoding="utf-8")[:300]]
    assert len(notas) == 1  # a nota antiga foi substituída, não duplicada
    assert ler_nota(notas[0])[0].criado == "2026-10-05"  # a data de criação foi preservada


def test_mover_categoria_fora_de_mes_continua_na_pasta_da_categoria(s):
    nota = write_note(s.saved_dir / "design", Meta(url=URL, plataforma="x", titulo="T", categoria="design"), 1)
    assert mover_categoria(s, nota, "IA").parent == s.saved_dir / "IA"
