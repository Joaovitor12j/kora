import pytest

from kora import worker
from kora.config import Settings
from kora.db import CONCLUIDO, FALHOU, Queue
from kora.extractors.meta import Meta


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault",
                        db_path=tmp_path / "q.sqlite", _env_file=None)
    sent = []
    monkeypatch.setattr(worker, "send_message", lambda token, chat, text, reply: sent.append(text))
    queue = Queue(settings.db_path)
    yield queue, settings, sent
    queue.close()


def enqueue(queue):
    return queue.enqueue("https://x.com/a/status/1", "https://x.com/a/status/1", "x", chat_id=1, message_id=5)[0]


def test_success_writes_note_and_notifies(env, monkeypatch):
    queue, settings, sent = env
    item = enqueue(queue)
    monkeypatch.setattr(worker, "fetch_meta", lambda url, plat: Meta(url=url, plataforma=plat, titulo="Olá", descricao="d"))
    assert worker.run_once(queue, settings) is True
    got = queue.get(item.id)
    assert got.status == CONCLUIDO
    assert (settings.inbox_dir / got.nota_path.split("/")[-1]).exists()
    assert sent == ["salvo (sem IA): Olá"]


def test_failure_retries_then_notifies_once(env, monkeypatch):
    queue, settings, sent = env
    item = enqueue(queue)

    def boom(url, plat):
        raise RuntimeError("quebrou")

    monkeypatch.setattr(worker, "fetch_meta", boom)
    monkeypatch.setattr("kora.db.BACKOFF_BASE", 0)
    for _ in range(3):
        assert worker.run_once(queue, settings) is True
    assert queue.get(item.id).status == FALHOU
    assert len(sent) == 1 and "não consegui salvar" in sent[0]
    assert worker.run_once(queue, settings) is False


def test_empty_queue(env):
    queue, settings, _ = env
    assert worker.run_once(queue, settings) is False
