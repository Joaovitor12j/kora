import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

NA_FILA, PROCESSANDO, CONCLUIDO, FALHOU = "na_fila", "processando", "concluido", "falhou"
MAX_TENTATIVAS = 3
BACKOFF_BASE = 60  # segundos; dobra a cada tentativa

SCHEMA = """
CREATE TABLE IF NOT EXISTS itens (
    id            INTEGER PRIMARY KEY,
    url           TEXT NOT NULL,
    url_canonica  TEXT NOT NULL UNIQUE,
    plataforma    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'na_fila',
    tentativas    INTEGER NOT NULL DEFAULT 0,
    erro          TEXT,
    titulo        TEXT,
    nota_path     TEXT,
    chat_id       INTEGER,
    message_id    INTEGER,
    resposta_id   INTEGER,
    proxima_em    REAL NOT NULL DEFAULT 0,
    criado_em     REAL NOT NULL,
    atualizado_em REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_itens_fila ON itens (status, proxima_em);
"""


@dataclass(frozen=True)
class Item:
    id: int
    url: str
    url_canonica: str
    plataforma: str
    status: str
    tentativas: int
    erro: str | None
    titulo: str | None
    nota_path: str | None
    chat_id: int | None
    message_id: int | None
    resposta_id: int | None


class Queue:
    def __init__(self, path: Path | str):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(path), isolation_level=None, timeout=30)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._migrar()

    def _migrar(self) -> None:
        """Bancos criados antes de uma coluna existir ganham a coluna na abertura."""
        colunas = {r["name"] for r in self._conn.execute("PRAGMA table_info(itens)")}
        if "resposta_id" not in colunas:
            self._conn.execute("ALTER TABLE itens ADD COLUMN resposta_id INTEGER")

    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def _tx(self):
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            yield self._conn
        except BaseException:
            self._conn.execute("ROLLBACK")
            raise
        else:
            self._conn.execute("COMMIT")

    @staticmethod
    def _item(row: sqlite3.Row) -> Item:
        return Item(**{k: row[k] for k in Item.__dataclass_fields__})

    def enqueue(self, url: str, url_canonica: str, plataforma: str,
                chat_id: int | None = None, message_id: int | None = None,
                now: float | None = None) -> tuple[Item, bool]:
        """Insere o link. Retorna (item, criado); criado=False se já existia."""
        now = time.time() if now is None else now
        with self._tx() as c:
            row = c.execute("SELECT * FROM itens WHERE url_canonica = ?", (url_canonica,)).fetchone()
            if row:
                return self._item(row), False
            cur = c.execute(
                "INSERT INTO itens (url, url_canonica, plataforma, chat_id, message_id, criado_em, atualizado_em) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (url, url_canonica, plataforma, chat_id, message_id, now, now),
            )
            row = c.execute("SELECT * FROM itens WHERE id = ?", (cur.lastrowid,)).fetchone()
        return self._item(row), True

    def claim_next(self, now: float | None = None) -> Item | None:
        now = time.time() if now is None else now
        with self._tx() as c:
            row = c.execute(
                "SELECT * FROM itens WHERE status = ? AND proxima_em <= ? ORDER BY id LIMIT 1",
                (NA_FILA, now),
            ).fetchone()
            if not row:
                return None
            c.execute("UPDATE itens SET status = ?, atualizado_em = ? WHERE id = ?",
                      (PROCESSANDO, now, row["id"]))
            row = c.execute("SELECT * FROM itens WHERE id = ?", (row["id"],)).fetchone()
        return self._item(row)

    def done(self, item_id: int, titulo: str, nota_path: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._conn.execute(
            "UPDATE itens SET status = ?, titulo = ?, nota_path = ?, erro = NULL, atualizado_em = ? WHERE id = ?",
            (CONCLUIDO, titulo, nota_path, now, item_id),
        )

    def fail(self, item_id: int, erro: str, now: float | None = None) -> Item:
        """Conta a tentativa; volta para a fila com backoff ou marca como falhou."""
        now = time.time() if now is None else now
        with self._tx() as c:
            tentativas = c.execute("SELECT tentativas FROM itens WHERE id = ?", (item_id,)).fetchone()[0] + 1
            if tentativas >= MAX_TENTATIVAS:
                status, proxima = FALHOU, 0.0
            else:
                status, proxima = NA_FILA, now + BACKOFF_BASE * 2 ** (tentativas - 1)
            c.execute(
                "UPDATE itens SET status = ?, tentativas = ?, erro = ?, proxima_em = ?, atualizado_em = ? WHERE id = ?",
                (status, tentativas, erro[:500], proxima, now, item_id),
            )
            row = c.execute("SELECT * FROM itens WHERE id = ?", (item_id,)).fetchone()
        return self._item(row)

    def retry(self, item_id: int, now: float | None = None) -> None:
        """Reenvio manual de um item que falhou: zera tentativas e volta para a fila."""
        now = time.time() if now is None else now
        self._conn.execute(
            "UPDATE itens SET status = ?, tentativas = 0, proxima_em = 0, atualizado_em = ? WHERE id = ?",
            (NA_FILA, now, item_id),
        )

    def requeue_stuck(self) -> int:
        """Itens 'processando' de uma execução interrompida voltam para a fila."""
        cur = self._conn.execute("UPDATE itens SET status = ? WHERE status = ?", (NA_FILA, PROCESSANDO))
        return cur.rowcount

    def set_resposta(self, item_id: int, resposta_id: int | None) -> None:
        """Guarda a mensagem do bot que avisou o resultado, para a correção por resposta achar o item."""
        if resposta_id is not None:
            self._conn.execute("UPDATE itens SET resposta_id = ? WHERE id = ?", (resposta_id, item_id))

    def set_nota(self, item_id: int, titulo: str, nota_path: str, now: float | None = None) -> None:
        now = time.time() if now is None else now
        self._conn.execute("UPDATE itens SET titulo = ?, nota_path = ?, atualizado_em = ? WHERE id = ?",
                           (titulo, nota_path, now, item_id))

    def find_by_resposta(self, chat_id: int, resposta_id: int) -> Item | None:
        row = self._conn.execute("SELECT * FROM itens WHERE chat_id = ? AND resposta_id = ?",
                                 (chat_id, resposta_id)).fetchone()
        return self._item(row) if row else None

    def find_by_message(self, chat_id: int, message_id: int) -> list[Item]:
        rows = self._conn.execute("SELECT * FROM itens WHERE chat_id = ? AND message_id = ? ORDER BY id",
                                  (chat_id, message_id)).fetchall()
        return [self._item(r) for r in rows]

    def by_canonica(self, url_canonica: str) -> Item | None:
        row = self._conn.execute("SELECT * FROM itens WHERE url_canonica = ?", (url_canonica,)).fetchone()
        return self._item(row) if row else None

    def proxima_tentativa(self, now: float | None = None) -> float | None:
        """Quando o item em espera de retentativa mais próximo fica elegível (None se não há)."""
        now = time.time() if now is None else now
        row = self._conn.execute("SELECT MIN(proxima_em) FROM itens WHERE status = ? AND proxima_em > ?",
                                 (NA_FILA, now)).fetchone()
        return row[0]

    def falhas_recentes(self, limite: int = 5) -> list[Item]:
        rows = self._conn.execute("SELECT * FROM itens WHERE status = ? ORDER BY atualizado_em DESC LIMIT ?",
                                  (FALHOU, limite)).fetchall()
        return [self._item(r) for r in rows]

    def ultimo_concluido(self) -> tuple[Item, float] | None:
        row = self._conn.execute("SELECT * FROM itens WHERE status = ? ORDER BY atualizado_em DESC LIMIT 1",
                                 (CONCLUIDO,)).fetchone()
        return (self._item(row), row["atualizado_em"]) if row else None

    def get(self, item_id: int) -> Item | None:
        row = self._conn.execute("SELECT * FROM itens WHERE id = ?", (item_id,)).fetchone()
        return self._item(row) if row else None

    def counts(self) -> dict[str, int]:
        rows = self._conn.execute("SELECT status, COUNT(*) n FROM itens GROUP BY status").fetchall()
        return {r["status"]: r["n"] for r in rows}
