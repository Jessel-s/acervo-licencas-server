"""Fila persistente para sincronizar operacoes locais quando houver conexao."""

import json
import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class SyncQueue:
    def __init__(self, db_path: str = "sync_queue.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                operation TEXT NOT NULL CHECK (operation IN ('upsert', 'delete')),
                payload TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (entity_type, entity_id)
            )
            """
        )
        self.connection.commit()

    def enqueue(self, entity_type: str, entity_id: str, operation: str, payload: Dict[str, Any] | None = None) -> None:
        if operation not in {"upsert", "delete"}:
            raise ValueError("A operacao deve ser 'upsert' ou 'delete'.")

        serialized_payload = json.dumps(payload, ensure_ascii=True, default=str) if payload else None
        self.connection.execute(
            """
            INSERT INTO sync_queue (entity_type, entity_id, operation, payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                operation = excluded.operation,
                payload = excluded.payload,
                created_at = CURRENT_TIMESTAMP
            """,
            (entity_type, entity_id, operation, serialized_payload),
        )
        self.connection.commit()

    def pending(self) -> List[Dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT id, entity_type, entity_id, operation, payload FROM sync_queue ORDER BY id"
        ).fetchall()
        return [
            {
                **dict(row),
                "payload": json.loads(row["payload"]) if row["payload"] else None,
            }
            for row in rows
        ]

    def pending_count(self) -> int:
        return self.connection.execute("SELECT COUNT(*) FROM sync_queue").fetchone()[0]

    def remove(self, queue_id: int) -> None:
        self.connection.execute("DELETE FROM sync_queue WHERE id = ?", (queue_id,))
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()


def enqueue_asset(asset, operation: str = "upsert", queue_path: str = "sync_queue.db") -> None:
    queue = SyncQueue(queue_path)
    try:
        payload = None
        if operation == "upsert":
            payload = {
                "id": asset.id,
                "colegio_id": os.getenv("COLEGIO_ID"),
                "numero_carrinho": asset.numero_carrinho,
                "tipo": asset.tipo,
                "modelo": asset.modelo,
                "numero_serie": asset.numero_serie,
                "data_compra": asset.data_compra,
                "status": asset.status,
                "localizacao": asset.localizacao,
                "observacoes": asset.observacoes,
                "data_cadastro": asset.data_cadastro,
            }
        queue.enqueue("ativo", asset.id, operation, payload)
    finally:
        queue.close()


def enqueue_session(session, queue_path: str = "sync_queue.db") -> None:
    payload = {
        "colegio_id": os.getenv("COLEGIO_ID"),
        "source_id": str(session.id),
        "turma": session.turma,
        "professor": session.professor,
        "programa": session.programa,
        "data_inicio": session.data_inicio,
        "quantidade_notebooks": session.quantidade_notebooks,
        "observacoes": session.observacoes,
        "previsao_devolucao": session.previsao_devolucao,
        "usuario_movimentacao": session.usuario_movimentacao,
    }
    queue = SyncQueue(queue_path)
    try:
        queue.enqueue("sessao_uso", str(session.id), "upsert", payload)
    finally:
        queue.close()


def enqueue_history(record, queue_path: str = "sync_queue.db") -> None:
    payload = {
        "colegio_id": os.getenv("COLEGIO_ID"),
        "source_id": str(record.id),
        "id_etiqueta": record.id_etiqueta,
        "acao": record.acao,
        "usuario_movimentacao": record.usuario_movimentacao,
        "responsavel": record.responsavel,
        "data": record.data,
        "obs": record.obs,
    }
    queue = SyncQueue(queue_path)
    try:
        queue.enqueue("historico", str(record.id), "upsert", payload)
    finally:
        queue.close()


def enqueue_issue(issue, queue_path: str = "sync_queue.db") -> None:
    payload = {
        "colegio_id": os.getenv("COLEGIO_ID"),
        "source_id": str(issue.id),
        "ativo_id": issue.notebook_id,
        "tipo_problema": issue.tipo_problema,
        "descricao": issue.descricao,
        "data_registro": issue.data_registro,
        "responsavel": issue.responsavel,
        "status": issue.status,
        "prioridade": issue.prioridade,
        "categoria": issue.categoria,
        "parecer_tecnico": issue.parecer_tecnico,
        "local_incidente": issue.local_incidente,
        "data_resolucao": issue.data_resolucao,
    }
    queue = SyncQueue(queue_path)
    try:
        queue.enqueue("problema", str(issue.id), "upsert", payload)
    finally:
        queue.close()


def enqueue_booking(booking, queue_path: str = "sync_queue.db") -> None:
    payload = {
        "colegio_id": os.getenv("COLEGIO_ID"),
        "source_id": str(booking.id),
        "solicitante": booking.solicitante,
        "data_uso": booking.data_uso,
        "periodo": booking.periodo,
        "quantidade": booking.quantidade,
        "finalidade": booking.finalidade,
        "itens_reservados": booking.itens_reservados,
        "horario_retirada": booking.horario_retirada,
        "horario_devolucao": booking.horario_devolucao,
        "status": booking.status,
        "data_criacao": booking.data_criacao,
        "registrado_por": booking.registrado_por,
        "codigo_reserva": booking.codigo_reserva,
    }
    queue = SyncQueue(queue_path)
    try:
        queue.enqueue("agendamento", str(booking.id), "upsert", payload)
    finally:
        queue.close()


def enqueue_storeroom_product(product, operation: str = "upsert", queue_path: str = "sync_queue.db") -> None:
    payload = None
    if operation == "upsert":
        payload = {
            "colegio_id": os.getenv("COLEGIO_ID"),
            "source_id": str(product.id),
            "sku": product.sku,
            "nome": product.nome,
            "categoria": product.categoria,
            "quantidade_atual": product.quantidade_atual,
            "estoque_minimo": product.estoque_minimo,
            "custo_unitario": product.custo_unitario,
        }
    queue = SyncQueue(queue_path)
    try:
        queue.enqueue("almox_produto", str(product.id), operation, payload)
    finally:
        queue.close()


def enqueue_storeroom_movement(movement, operation: str = "upsert", queue_path: str = "sync_queue.db") -> None:
    payload = None
    if operation == "upsert":
        payload = {
            "colegio_id": os.getenv("COLEGIO_ID"),
            "source_id": str(movement.id),
            "produto_source_id": str(movement.produto_id),
            "tipo": movement.tipo,
            "quantidade": movement.quantidade,
            "usuario": movement.usuario,
            "destino_id": movement.destino_id,
            "data_movimentacao": movement.data_movimentacao,
            "observacao": movement.observacao,
        }
    queue = SyncQueue(queue_path)
    try:
        queue.enqueue("almox_movimentacao", str(movement.id), operation, payload)
    finally:
        queue.close()