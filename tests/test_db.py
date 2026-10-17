import pytest

from kora.db import BACKOFF_BASE, CONCLUIDO, FALHOU, MAX_TENTATIVAS, NA_FILA, PROCESSANDO, Queue


@pytest.fixture
def q(tmp_path):
    queue = Queue(tmp_path / "q.sqlite")
    yield queue
    queue.close()


def add(q, n=1, **kw):
    return q.enqueue(f"https://x.com/a/status/{n}", f"https://x.com/a/status/{n}", "x", **kw)


def test_enqueue_dedupes_by_canonical(q):
    a, created_a = add(q)
    b, created_b = q.enqueue("https://twitter.com/a/status/1?s=20", "https://x.com/a/status/1", "x")
    assert created_a and not created_b
    assert a.id == b.id
    assert q.counts() == {NA_FILA: 1}


def test_claim_is_fifo_and_marks_processing(q):
    add(q, 1); add(q, 2)
    first = q.claim_next()
    assert first.url.endswith("/1")
    assert q.get(first.id).status == PROCESSANDO
    assert q.claim_next().url.endswith("/2")
    assert q.claim_next() is None


def test_done(q):
    item, _ = add(q)
    q.claim_next()
    q.done(item.id, "Título", "/vault/n.md")
    got = q.get(item.id)
    assert (got.status, got.titulo, got.nota_path) == (CONCLUIDO, "Título", "/vault/n.md")


def test_fail_backoff_then_final(q):
    item, _ = add(q)
    t = 1000.0
    for n in range(1, MAX_TENTATIVAS):
        q.claim_next(now=t + 10_000 * n)
        got = q.fail(item.id, "boom", now=t)
        assert got.status == NA_FILA and got.tentativas == n
        assert q.claim_next(now=t + BACKOFF_BASE * 2 ** (n - 1) - 1) is None  # ainda em backoff
    q.claim_next(now=t + 10**6)
    got = q.fail(item.id, "boom", now=t)
    assert got.status == FALHOU and got.erro == "boom"
    assert q.claim_next(now=t + 10**9) is None


def test_requeue_stuck(q):
    add(q)
    q.claim_next()
    assert q.requeue_stuck() == 1
    assert q.claim_next() is not None


def test_retry_resets_failed_item(q):
    item, _ = add(q)
    for _ in range(MAX_TENTATIVAS):
        q.claim_next(now=10**9)
        q.fail(item.id, "boom", now=0)
    assert q.get(item.id).status == FALHOU
    q.retry(item.id)
    got = q.get(item.id)
    assert (got.status, got.tentativas) == (NA_FILA, 0)
    assert q.claim_next() is not None
