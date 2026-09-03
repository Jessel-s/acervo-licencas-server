import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class LocalDatabase:
    """Persistência local do PDV para operação offline resiliente."""

    def __init__(self, db_path: str = "pdv_local.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS licenca_estado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                serial_pdv TEXT NOT NULL,
                chave_ativacao TEXT NOT NULL,
                colegio_id TEXT,
                status TEXT NOT NULL DEFAULT 'pendente',
                ultima_checagem TEXT,
                ultima_validacao_sucesso TEXT,
                bloqueado INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_licenca_estado_serial ON licenca_estado(serial_pdv, chave_ativacao)"
        )
        self.conn.commit()

    def salvar_estado(
        self,
        serial_pdv: str,
        chave_ativacao: str,
        colegio_id: Optional[str],
        status: str,
        ultima_checagem: Optional[datetime] = None,
        ultima_validacao_sucesso: Optional[datetime] = None,
        bloqueado: int = 0,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO licenca_estado (
                serial_pdv,
                chave_ativacao,
                colegio_id,
                status,
                ultima_checagem,
                ultima_validacao_sucesso,
                bloqueado
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                serial_pdv,
                chave_ativacao,
                colegio_id,
                status,
                self._fmt(ultima_checagem),
                self._fmt(ultima_validacao_sucesso),
                bloqueado,
            ),
        )
        self.conn.commit()

    def get_estado(self, serial_pdv: str, chave_ativacao: str) -> Optional[Dict[str, Any]]:
        row = self.conn.execute(
            """
            SELECT *
            FROM licenca_estado
            WHERE serial_pdv = ? AND chave_ativacao = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (serial_pdv, chave_ativacao),
        ).fetchone()

        if row is None:
            return None
        return dict(row)

    def atualizar_estado(self, serial_pdv: str, chave_ativacao: str, **kwargs) -> None:
        if not self.get_estado(serial_pdv, chave_ativacao):
            raise ValueError("Estado local não encontrado para o serial e chave informados.")

        campos: list[str] = []
        valores: list[Any] = []

        for chave, valor in kwargs.items():
            if valor is not None and chave in {"ultima_checagem", "ultima_validacao_sucesso"} and isinstance(valor, datetime):
                valor = self._fmt(valor)
            campos.append(f"{chave} = ?")
            valores.append(valor)

        query = f"UPDATE licenca_estado SET {', '.join(campos)} WHERE serial_pdv = ? AND chave_ativacao = ?"
        self.conn.execute(query, (*valores, serial_pdv, chave_ativacao))
        self.conn.commit()

    @staticmethod
    def _fmt(value: Optional[datetime]) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        return str(value)

    def close(self) -> None:
        self.conn.close()
