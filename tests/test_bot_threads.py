import asyncio

from kora import status
from kora.agenda import Agenda
from kora.config import Settings
from kora.db import Queue


def test_status_works_from_another_thread(tmp_path, monkeypatch):
    """Regressão: o /status falhava com ProgrammingError ao usar a conexão do bot em to_thread."""
    monkeypatch.setattr(status, "consultar", lambda: Agenda())  # sem consultar o systemd real
    s = Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "v",
                 db_path=tmp_path / "q.sqlite", _env_file=None)
    Queue(s.db_path).enqueue("u", "c", "x")  # cria o banco na thread principal
    texto = asyncio.run(asyncio.to_thread(status.texto_status, s))
    assert "• Aguardando: 1" in texto and "Agendamento: não instalado" in texto
