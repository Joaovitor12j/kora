import logging
import os
import re
import subprocess
import tomllib
from pathlib import Path

import pytest

from kora import logs, status, worker
from kora.config import Settings
from kora.db import Queue
from kora.status import estado_ia, estado_worker, idade, montar_status

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture
def s(tmp_path):
    return Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "vault",
                    db_path=tmp_path / "data" / "q.sqlite", _env_file=None)


@pytest.fixture
def q(s):
    queue = Queue(s.db_path)
    yield queue
    queue.close()


@pytest.mark.parametrize("seg, texto", [(4, "4 s"), (89, "89 s"), (120, "2 min"), (3 * 3600, "3 h"), (3 * 86400, "3 d"), (-5, "0 s")])
def test_idade(seg, texto):
    assert idade(seg) == texto


def test_estado_worker(s):
    assert "nunca iniciou" in estado_worker(s, 1000.0)
    s.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    s.heartbeat_path.touch()
    os.utime(s.heartbeat_path, (1000.0, 1000.0))
    assert estado_worker(s, 1004.0) == "ativo (batimento há 4 s)"
    assert estado_worker(s, 1000.0 + 3 * 3600) == "PARADO (último batimento há 3 h)"


def test_estado_ia(s):
    assert estado_ia(s) == "desligada"
    assert estado_ia(s.model_copy(update={"llm_provider": "ollama"})) == "ollama/gemma4"
    assert "ANTHROPIC_API_KEY" in estado_ia(s.model_copy(update={"llm_provider": "anthropic"}))


def test_montar_status(s, q):
    ok, _ = q.enqueue("u1", "https://x.com/a/1", "x")
    q.claim_next(); q.done(ok.id, "Salvo bem", "/n.md", now=900.0)
    ruim, _ = q.enqueue("u2", "https://x.com/b/2", "x")
    for _ in range(3):
        q.claim_next(now=10**9); q.fail(ruim.id, "yt-dlp: ERROR: bloqueado", now=950.0)
    q.enqueue("u3", "https://x.com/c/3", "x")
    texto = montar_status(q, s, agora=1000.0)
    assert "worker: nunca iniciou" in texto
    assert "fila: 1 aguardando · 0 processando · 1 salvos · 1 falharam" in texto
    assert "IA: desligada" in texto and "yt-dlp: 20" in texto
    assert "último salvo: há 2 min — Salvo bem" in texto
    assert "falhas recentes:\n- https://x.com/b/2\n  yt-dlp: ERROR: bloqueado" in texto


def test_status_without_data(s, q):
    texto = montar_status(q, s, agora=1.0)
    assert "último salvo" not in texto and "falhas recentes" not in texto


def test_falhas_recentes_order_and_limit(q):
    for i in range(3):
        item, _ = q.enqueue(f"u{i}", f"c{i}", "x")
        for _ in range(3):
            q.claim_next(now=10**9); q.fail(item.id, f"erro {i}", now=100.0 + i)
    assert [f.erro for f in q.falhas_recentes(2)] == ["erro 2", "erro 1"]


def test_logging_silences_http_libraries(capsys):
    root = logging.getLogger()
    antigos = (root.handlers[:], root.level)
    root.handlers.clear()
    try:
        logs.configurar("INFO")
        logging.getLogger("httpx").info("POST https://api.telegram.org/botSEGREDO/sendMessage")
        logging.getLogger("httpx2").info("POST https://api.telegram.org/botSEGREDO/getUpdates")
        logging.getLogger("kora.teste").info("mensagem do app")
        saida = capsys.readouterr().err
        assert "SEGREDO" not in saida and "mensagem do app" in saida
    finally:
        root.handlers[:], _ = antigos[0], None
        root.setLevel(antigos[1])
        for nome in logs.RUIDOSAS:
            logging.getLogger(nome).setLevel(logging.NOTSET)


def test_batimento_touches_file(s, monkeypatch):
    class Fim(Exception):
        pass

    def dorme(_):
        raise Fim

    monkeypatch.setattr(worker.time, "sleep", dorme)
    with pytest.raises(Fim):
        worker.batimento(s.heartbeat_path)
    assert s.heartbeat_path.exists()


# --- deploy -----------------------------------------------------------------

def test_service_units_run_real_entrypoints_and_use_placeholder():
    scripts = tomllib.loads((RAIZ / "pyproject.toml").read_text())["project"]["scripts"]
    for unit in ("kora-bot.service", "kora-worker.service"):
        texto = (RAIZ / "deploy" / unit).read_text()
        exec_start = re.search(r"^ExecStart=@REPO@/\.venv/bin/(\S+)$", texto, re.M)
        assert exec_start and exec_start.group(1) in scripts, unit
        assert "WorkingDirectory=@REPO@" in texto and "Restart=on-failure" in texto
    timer = (RAIZ / "deploy" / "kora-ytdlp-update.timer").read_text()
    assert "Persistent=true" in timer and "OnCalendar=daily" in timer
    assert "update-ytdlp.sh" in (RAIZ / "deploy" / "kora-ytdlp-update.service").read_text()


@pytest.mark.parametrize("script", ["install.sh", "update-ytdlp.sh"])
def test_shell_scripts_are_valid_and_executable(script):
    caminho = RAIZ / "deploy" / script
    assert os.access(caminho, os.X_OK)
    assert subprocess.run(["bash", "-n", str(caminho)], capture_output=True).returncode == 0


def test_install_refuses_without_env_or_venv(tmp_path):
    # roda uma cópia fora do repo: sem .venv nem .env, deve falhar antes de tocar no systemd
    (tmp_path / "deploy").mkdir()
    copia = tmp_path / "deploy" / "install.sh"
    copia.write_text((RAIZ / "deploy" / "install.sh").read_text()); copia.chmod(0o755)
    r = subprocess.run([str(copia)], capture_output=True, text=True, env={**os.environ, "HOME": str(tmp_path)})
    assert r.returncode == 1 and "uv sync" in r.stderr
    assert not (tmp_path / ".config").exists()
