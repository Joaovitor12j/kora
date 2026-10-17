import asyncio

from kora.config import Settings
from kora.db import Queue
from kora.status import texto_status


def test_status_works_from_another_thread(tmp_path):
    """Regressão: o /status falhava com ProgrammingError ao usar a conexão do bot em to_thread."""
    s = Settings(telegram_bot_token="t", telegram_allowed_chat_id=1, vault_path=tmp_path / "v",
                 db_path=tmp_path / "q.sqlite", _env_file=None)
    Queue(s.db_path).enqueue("u", "c", "x")  # cria o banco na thread principal
    texto = asyncio.run(asyncio.to_thread(texto_status, s))
    assert "fila: 1 aguardando" in texto
