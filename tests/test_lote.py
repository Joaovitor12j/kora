import asyncio
import json
import subprocess
from types import SimpleNamespace

import pytest

from kora import agenda, bot, status, worker
from kora.agenda import Agenda, iniciar_lote, ler_execucao, parse_proxima, registrar_execucao
from kora.config import Settings
from kora.db import CONCLUIDO, FALHOU, NA_FILA, Queue
from kora.extractors.meta import Meta
from kora.status import linhas_worker


@pytest.fixture
def s(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault",
                    db_path=tmp_path / "data" / "q.sqlite", _env_file=None)


@pytest.fixture
def q(s):
    queue = Queue(s.db_path)
    yield queue
    queue.close()


@pytest.fixture(autouse=True)
def sem_telegram(monkeypatch):
    monkeypatch.setattr(worker, "send_message", lambda *a, **k: 1)


def enfileirar(q, n):
    for i in range(n):
        q.enqueue(f"https://x.com/a/status/{i}", f"https://x.com/a/status/{i}", "x", chat_id=1, message_id=i)


# --- executar_lote ----------------------------------------------------------

def test_lote_drains_queue_and_records_run(s, q, monkeypatch):
    enfileirar(q, 3)
    monkeypatch.setattr(worker, "fetch_meta", lambda url, plat: Meta(url=url, plataforma=plat, titulo=f"t{url[-1]}"))
    resumo = worker.executar_lote(q, s, None)
    assert resumo == {"tentativas": 3, "salvos": 3, "falhas": 0}
    assert q.counts() == {CONCLUIDO: 3}
    gravado = ler_execucao(s.execucao_path)
    assert gravado["salvos"] == 3 and gravado["fim"] >= gravado["inicio"]


def test_lote_counts_only_new_results(s, q, monkeypatch):
    enfileirar(q, 2)
    monkeypatch.setattr("kora.db.BACKOFF_BASE", 0)

    def fetch(url, plat):
        if url.endswith("/0"):
            raise RuntimeError("bloqueado")
        return Meta(url=url, plataforma=plat, titulo="ok")

    monkeypatch.setattr(worker, "fetch_meta", fetch)
    resumo = worker.executar_lote(q, s, None)
    assert resumo == {"tentativas": 4, "salvos": 1, "falhas": 1}  # 1 ok + 3 tentativas do que falhou
    assert q.counts() == {CONCLUIDO: 1, FALHOU: 1}
    # um segundo lote não recontabiliza o passado
    assert worker.executar_lote(q, s, None) == {"tentativas": 0, "salvos": 0, "falhas": 0}


def test_lote_waits_for_short_backoff_and_retries(s, q, monkeypatch):
    enfileirar(q, 1)
    chamadas = []

    def fetch(url, plat):
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("instável")
        return Meta(url=url, plataforma=plat, titulo="ok")

    monkeypatch.setattr(worker, "fetch_meta", fetch)
    monkeypatch.setattr("kora.db.BACKOFF_BASE", 0.3)
    resumo = worker.executar_lote(q, s, None)
    assert resumo["salvos"] == 1 and len(chamadas) == 2


def test_lote_does_not_wait_for_long_backoff(s, q, monkeypatch):
    enfileirar(q, 1)
    monkeypatch.setattr(worker, "fetch_meta", lambda u, p: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(worker, "ESPERA_RETENTATIVA_MAX", 1.0)  # o backoff real (60 s) passa disso
    esperas = []
    resumo = worker.executar_lote(q, s, None, dormir=esperas.append)
    assert not esperas and resumo == {"tentativas": 1, "salvos": 0, "falhas": 0}
    assert q.counts() == {NA_FILA: 1}  # fica para o próximo lote


# --- registro e agenda ------------------------------------------------------

def test_registro_roundtrip_and_bad_files(tmp_path):
    p = tmp_path / "x" / "ult.json"
    registrar_execucao(p, 1.0, 2.0, 5, 4, 1)
    assert ler_execucao(p) == {"inicio": 1.0, "fim": 2.0, "tentativas": 5, "salvos": 4, "falhas": 1}
    assert ler_execucao(tmp_path / "nao-existe.json") is None
    p.write_text("{quebrado", encoding="utf-8")
    assert ler_execucao(p) is None


def test_parse_proxima():
    saida = json.dumps([{"next": 1792292623809523, "unit": "kora-ytdlp-update.timer"},
                        {"next": 1792300000000000, "unit": "kora-worker.timer"}])
    assert parse_proxima(saida) == 1792300000.0
    assert parse_proxima(json.dumps([{"next": 0, "unit": "kora-worker.timer"}])) is None
    assert parse_proxima("lixo") is None and parse_proxima("[]") is None


def fake_systemctl(estados, timers="[]", start_rc=0):
    chamadas = []

    def run(*args):
        chamadas.append(args)
        if args[0] == "is-active":
            return subprocess.CompletedProcess(args, 0, estados.get(args[1], "inactive") + "\n", "")
        if args[0] == "list-timers":
            return subprocess.CompletedProcess(args, 0, timers, "")
        return subprocess.CompletedProcess(args, start_rc, "", "")

    return run, chamadas


def test_consultar_and_iniciar_lote(monkeypatch):
    run, chamadas = fake_systemctl({"kora-worker.timer": "active"},
                                   json.dumps([{"next": 5_000_000, "unit": "kora-worker.timer"}]))
    monkeypatch.setattr(agenda, "_systemctl", run)
    assert agenda.consultar() == Agenda(instalada=True, rodando=False, proxima=5.0)
    assert iniciar_lote() == "iniciado" and ("start", "--no-block", "kora-worker.service") in chamadas

    run, chamadas = fake_systemctl({"kora-worker.service": "activating"})
    monkeypatch.setattr(agenda, "_systemctl", run)
    assert iniciar_lote() == "andamento" and not any(c[0] == "start" for c in chamadas)
    assert agenda.consultar().rodando is True

    run, _ = fake_systemctl({}, start_rc=5)
    monkeypatch.setattr(agenda, "_systemctl", run)
    assert iniciar_lote() == "indisponivel"
    monkeypatch.setattr(agenda, "_systemctl", lambda *a: None)  # systemctl ausente
    assert iniciar_lote() == "indisponivel" and agenda.consultar() == Agenda()


def test_linhas_worker_batches(s):
    agora = 100_000.0
    assert linhas_worker(s, agora, Agenda(rodando=True)) == ["• Lote rodando agora", "• Última execução: nenhuma registrada"]
    assert linhas_worker(s, agora, Agenda())[-1] == "• Agendamento: não instalado (deploy/install.sh)"
    registrar_execucao(s.execucao_path, agora - 7300, agora - 7200, 4, 3, 1)
    assert linhas_worker(s, agora, Agenda(instalada=True, proxima=agora + 6 * 3600)) == [
        "• Última execução: há 2 h (3 salvos, 1 falha)", "• Próxima: em 6 h"]
    assert linhas_worker(s, agora, Agenda(instalada=True, proxima=agora - 5))[-1] == "• Próxima: vencida, aguardando disparo"
    assert linhas_worker(s, agora, Agenda(instalada=True))[-1] == "• Próxima: indisponível"


# --- bot: /processar --------------------------------------------------------

def chamar_processar(q, resultado, monkeypatch):
    respostas = []

    async def reply(texto, **kw):
        respostas.append(texto)

    monkeypatch.setattr(bot, "iniciar_lote", lambda: resultado)
    update = SimpleNamespace(effective_message=SimpleNamespace(reply_text=reply))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"queue": q}))
    asyncio.run(bot.on_processar(update, context))
    return respostas[0]


def test_processar_replies(q, monkeypatch):
    assert "vazia" in chamar_processar(q, "iniciado", monkeypatch)
    enfileirar(q, 2)
    assert "Lote iniciado: 2 na fila" in chamar_processar(q, "iniciado", monkeypatch)
    assert "já tem um lote" in chamar_processar(q, "andamento", monkeypatch).lower()
    assert "install.sh" in chamar_processar(q, "indisponivel", monkeypatch)


def test_worker_cli_has_once_flag():
    r = subprocess.run(["uv", "run", "-q", "kora-worker", "--help"], capture_output=True, text=True)
    assert r.returncode == 0 and "--once" in r.stdout
