import json
import sqlite3

import pytest

from kora import worker
from kora.config import Settings
from kora.correcao import corrigir_categoria, pedido_de_categoria
from kora.db import Queue
from kora.extractors.meta import Meta
from kora.reclassificar import pendentes, reclassificar
from kora.vault import ler_nota, mover_categoria, render, write_note

from helpers import BOM, Fake


@pytest.fixture
def s(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault",
                    db_path=tmp_path / "q.sqlite", _env_file=None)


@pytest.fixture
def q(s):
    queue = Queue(s.db_path)
    yield queue
    queue.close()


def pendente(**kw):
    base = dict(url="https://x.com/a/status/1", plataforma="x", titulo="Título: com dois pontos",
                autor='Fulano "o Grande"', descricao="legenda\nem duas linhas", publicado="2026-10-01", criado="2026-10-10")
    return Meta(**{**base, **kw})


# --- banco ------------------------------------------------------------------

def test_migration_adds_resposta_id_to_old_database(tmp_path):
    path = tmp_path / "old.sqlite"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE itens (id INTEGER PRIMARY KEY, url TEXT NOT NULL, url_canonica TEXT NOT NULL UNIQUE, "
                "plataforma TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'na_fila', tentativas INTEGER NOT NULL DEFAULT 0, "
                "erro TEXT, titulo TEXT, nota_path TEXT, chat_id INTEGER, message_id INTEGER, "
                "proxima_em REAL NOT NULL DEFAULT 0, criado_em REAL NOT NULL, atualizado_em REAL NOT NULL)")
    old.execute("INSERT INTO itens (url, url_canonica, plataforma, criado_em, atualizado_em) VALUES ('u','u','x',0,0)")
    old.commit(); old.close()
    queue = Queue(path)
    assert queue.get(1).resposta_id is None
    queue.set_resposta(1, 77)
    assert queue.find_by_resposta(0, 77) is None and queue.get(1).resposta_id == 77


def test_lookups(q):
    a, _ = q.enqueue("u1", "c1", "x", chat_id=1, message_id=10)
    b, _ = q.enqueue("u2", "c2", "x", chat_id=1, message_id=10)
    q.set_resposta(a.id, 50); q.set_resposta(b.id, None)
    assert q.find_by_resposta(1, 50).id == a.id and q.find_by_resposta(2, 50) is None
    assert [i.id for i in q.find_by_message(1, 10)] == [a.id, b.id]
    assert q.by_canonica("c2").id == b.id and q.by_canonica("nada") is None
    q.set_nota(a.id, "T", "/p.md")
    assert (q.get(a.id).titulo, q.get(a.id).nota_path) == ("T", "/p.md")


def test_worker_stores_reply_id(s, q, monkeypatch):
    monkeypatch.setattr(worker, "send_message", lambda token, chat, text, reply: 99)
    monkeypatch.setattr(worker, "fetch_meta", lambda url, plat: Meta(url=url, plataforma=plat, titulo="t"))
    q.enqueue("https://x.com/a/status/1", "https://x.com/a/status/1", "x", chat_id=1, message_id=5)
    worker.run_once(q, s)
    assert q.get(1).resposta_id == 99


# --- ler_nota / mover_categoria --------------------------------------------

@pytest.mark.parametrize("extra", [
    {},
    {"conteudo": "linha um\nlinha dois", "conteudo_tipo": "transcricao"},
    {"conteudo": "legenda do vídeo", "conteudo_tipo": "legenda"},
    {"conteudo": "texto do artigo\n\noutro parágrafo", "conteudo_tipo": "artigo"},
    {"descricao": ""},
])
def test_ler_nota_round_trip(tmp_path, extra):
    meta = pendente(**extra)
    path = write_note(tmp_path, meta, 1)
    lida, status = ler_nota(path)
    assert status == "pendente"
    assert render(lida, lida.criado) == path.read_text(encoding="utf-8")
    assert lida.criado == "2026-10-10" and lida.autor == meta.autor


def test_mover_categoria_pending_inserts_and_processed_replaces(s, tmp_path):
    nota = write_note(s.inbox_dir, pendente(), 1)
    novo = mover_categoria(s, nota, "IA")
    assert novo.parent == s.saved_dir / "IA" and not nota.exists()
    texto = novo.read_text(encoding="utf-8")
    assert "categoria: IA\ntags: []" in texto and "status: pendente" in texto
    outro = mover_categoria(s, novo, "design")
    assert outro.parent == s.saved_dir / "design" and "categoria: design" in outro.read_text(encoding="utf-8")
    assert outro.read_text(encoding="utf-8").count("categoria:") == 1
    assert mover_categoria(s, outro, "design") == outro  # já estava lá


def test_mover_categoria_name_collision(s):
    a = write_note(s.inbox_dir, pendente(), 1)
    b = write_note(s.inbox_dir, pendente(url="https://x.com/b/status/2"), 2)
    destino_a = mover_categoria(s, a, "IA")
    destino_b = mover_categoria(s, b, "IA")
    assert destino_a != destino_b and destino_b.name.endswith("(2).md") and destino_a.exists() and destino_b.exists()


# --- correção por resposta --------------------------------------------------

def test_pedido_de_categoria():
    assert pedido_de_categoria("categoria: design") == "design"
    assert pedido_de_categoria("  Categoria :   IA  ") == "IA"
    assert pedido_de_categoria("olha https://x.com categoria: ia") is None
    assert pedido_de_categoria(None) is None


def com_nota(s, q, **kw):
    nota = write_note(s.inbox_dir, pendente(), 1)
    item, _ = q.enqueue("u", "https://x.com/a/status/1", "x", chat_id=1, message_id=10)
    q.done(item.id, "Título", str(nota))
    q.set_resposta(item.id, 50)
    return item, nota


def test_corrigir_by_reply_to_bot_message(s, q):
    item, nota = com_nota(s, q)
    assert corrigir_categoria(q, s, 1, 50, "DESIGN").startswith("Movido para design")
    novo = q.get(item.id).nota_path
    assert novo.startswith(str(s.saved_dir / "design")) and not nota.exists()


def test_corrigir_by_reply_to_original_message(s, q):
    com_nota(s, q)
    assert corrigir_categoria(q, s, 1, 10, "ia").startswith("Movido para IA")


def test_corrigir_errors(s, q):
    assert "desconhecida" in corrigir_categoria(q, s, 1, 50, "astrologia")
    assert "Não sei" in corrigir_categoria(q, s, 1, 999, "ia")
    item, nota = com_nota(s, q)
    q.enqueue("u2", "c2", "x", chat_id=1, message_id=10)
    assert "vários links" in corrigir_categoria(q, s, 1, 10, "ia")
    nota.unlink()
    assert "Não achei a nota" in corrigir_categoria(q, s, 1, 50, "ia")


# --- reclassificar ----------------------------------------------------------

def test_reclassify_moves_pending_notes_and_keeps_creation_date(s, q):
    nota = write_note(s.inbox_dir, pendente(), 1)
    item, _ = q.enqueue("u", "https://x.com/a/status/1", "x")
    q.done(item.id, "antigo", str(nota))
    assert pendentes(s) == [nota]
    assert reclassificar(s, q, Fake("a", json.dumps(BOM))) == (1, 0)
    novo = q.get(item.id).nota_path
    texto = open(novo, encoding="utf-8").read()
    assert novo.startswith(str(s.saved_dir / "design")) and not nota.exists()
    assert "criado: 2026-10-10" in texto and "status: processado" in texto and "## Resumo" in texto
    assert "legenda\nem duas linhas" in texto
    assert pendentes(s) == []


def test_reclassify_keeps_manual_category(s, q):
    mover_categoria(s, write_note(s.inbox_dir, pendente(), 1), "humor")
    assert reclassificar(s, q, Fake("a", json.dumps(BOM))) == (1, 0)  # IA diria "design"
    assert [p.parent.name for p in s.saved_dir.rglob("*.md")] == ["humor"]


def test_reclassify_stops_after_repeated_failures(s, q):
    for i in range(5):
        write_note(s.inbox_dir, pendente(url=f"https://x.com/a/status/{i}", titulo=f"nota {i}"), i)
    fora = Fake("a", erro=RuntimeError("fora do ar"))
    assert reclassificar(s, q, fora) == (0, 3)
    assert fora.chamadas == 3 and len(pendentes(s)) == 5
