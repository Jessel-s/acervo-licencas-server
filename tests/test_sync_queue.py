import os
import tempfile
import unittest
from pathlib import Path

from sync_queue import SyncQueue, enqueue_asset, enqueue_booking, enqueue_history, enqueue_issue, enqueue_session


class SyncQueueTests(unittest.TestCase):
    def test_latest_operation_replaces_previous_event_for_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = SyncQueue(str(Path(directory) / "sync_queue.db"))
            try:
                queue.enqueue("ativo", "AT-001", "upsert", {"status": "Disponível"})
                queue.enqueue("ativo", "AT-001", "upsert", {"status": "Em uso"})

                pending = queue.pending()

                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["operation"], "upsert")
                self.assertEqual(pending[0]["payload"], {"status": "Em uso"})
            finally:
                queue.close()

    def test_pending_count_reflects_current_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = SyncQueue(str(Path(directory) / "sync_queue.db"))
            try:
                self.assertEqual(queue.pending_count(), 0)
                queue.enqueue("ativo", "AT-001", "upsert", {"status": "Disponível"})
                self.assertEqual(queue.pending_count(), 1)
            finally:
                queue.close()

    def test_delete_replaces_pending_upsert_for_asset(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = SyncQueue(str(Path(directory) / "sync_queue.db"))
            try:
                queue.enqueue("ativo", "AT-001", "upsert", {"status": "Disponível"})
                queue.enqueue("ativo", "AT-001", "delete")

                pending = queue.pending()

                self.assertEqual(len(pending), 1)
                self.assertEqual(pending[0]["operation"], "delete")
                self.assertIsNone(pending[0]["payload"])
            finally:
                queue.close()

    def test_queue_serializes_datetime_values(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = SyncQueue(str(Path(directory) / "sync_queue.db"))
            try:
                from datetime import datetime

                queue.enqueue("ativo", "AT-001", "upsert", {"alterado_em": datetime(2026, 9, 1)})

                pending = queue.pending()

                self.assertEqual(pending[0]["payload"]["alterado_em"], "2026-09-01 00:00:00")
            finally:
                queue.close()

    def test_enqueue_asset_records_current_status(self):
        class Asset:
            id = "AT-001"
            numero_carrinho = 1
            tipo = "IMPRESSORA"
            modelo = "MODELO"
            numero_serie = "SERIE"
            data_compra = "2026-09-01"
            status = "Em uso"
            localizacao = "SETOR"
            observacoes = ""
            data_cadastro = "2026-09-01T00:00:00"

        with tempfile.TemporaryDirectory() as directory:
            queue_path = str(Path(directory) / "sync_queue.db")
            previous = os.environ.get("COLEGIO_ID")
            os.environ["COLEGIO_ID"] = "tenant"
            try:
                enqueue_asset(Asset(), queue_path=queue_path)
                queue = SyncQueue(queue_path)
                try:
                    self.assertEqual(queue.pending()[0]["payload"]["status"], "Em uso")
                finally:
                    queue.close()
            finally:
                if previous is None:
                    os.environ.pop("COLEGIO_ID", None)
                else:
                    os.environ["COLEGIO_ID"] = previous

    def test_enqueue_session_uses_local_id_as_source_id(self):
        class Session:
            id = 42
            turma = "SETOR"
            professor = "RESPONSAVEL"
            programa = "USO"
            data_inicio = "2026-09-01T00:00:00"
            quantidade_notebooks = 2
            observacoes = ""
            previsao_devolucao = None
            usuario_movimentacao = "OPERADOR"

        with tempfile.TemporaryDirectory() as directory:
            queue_path = str(Path(directory) / "sync_queue.db")
            previous = os.environ.get("COLEGIO_ID")
            os.environ["COLEGIO_ID"] = "tenant"
            try:
                enqueue_session(Session(), queue_path)
                queue = SyncQueue(queue_path)
                try:
                    pending = queue.pending()[0]
                    self.assertEqual(pending["entity_type"], "sessao_uso")
                    self.assertEqual(pending["payload"]["source_id"], "42")
                finally:
                    queue.close()
            finally:
                if previous is None:
                    os.environ.pop("COLEGIO_ID", None)
                else:
                    os.environ["COLEGIO_ID"] = previous

    def test_enqueue_history_uses_local_id_as_source_id(self):
        class History:
            id = 43
            id_etiqueta = "AT-001"
            acao = "Cadastro"
            usuario_movimentacao = "OPERADOR"
            responsavel = "-"
            data = "2026-09-01T00:00:00"
            obs = ""

        with tempfile.TemporaryDirectory() as directory:
            queue_path = str(Path(directory) / "sync_queue.db")
            previous = os.environ.get("COLEGIO_ID")
            os.environ["COLEGIO_ID"] = "tenant"
            try:
                enqueue_history(History(), queue_path)
                queue = SyncQueue(queue_path)
                try:
                    pending = queue.pending()[0]
                    self.assertEqual(pending["entity_type"], "historico")
                    self.assertEqual(pending["payload"]["source_id"], "43")
                finally:
                    queue.close()
            finally:
                if previous is None:
                    os.environ.pop("COLEGIO_ID", None)
                else:
                    os.environ["COLEGIO_ID"] = previous

    def test_enqueue_issue_maps_asset_reference(self):
        class Issue:
            id = 44
            notebook_id = "AT-001"
            tipo_problema = "FALHA"
            descricao = ""
            data_registro = "2026-09-01T00:00:00"
            responsavel = "OPERADOR"
            status = "Aberto"
            prioridade = "Normal"
            categoria = "Hardware"
            parecer_tecnico = None
            local_incidente = "SETOR"
            data_resolucao = None

        with tempfile.TemporaryDirectory() as directory:
            queue_path = str(Path(directory) / "sync_queue.db")
            previous = os.environ.get("COLEGIO_ID")
            os.environ["COLEGIO_ID"] = "tenant"
            try:
                enqueue_issue(Issue(), queue_path)
                queue = SyncQueue(queue_path)
                try:
                    payload = queue.pending()[0]["payload"]
                    self.assertEqual(payload["source_id"], "44")
                    self.assertEqual(payload["ativo_id"], "AT-001")
                finally:
                    queue.close()
            finally:
                if previous is None:
                    os.environ.pop("COLEGIO_ID", None)
                else:
                    os.environ["COLEGIO_ID"] = previous

    def test_enqueue_booking_uses_local_id_as_source_id(self):
        class Booking:
            id = 45
            solicitante = "RESPONSAVEL"
            data_uso = "2026-09-01"
            periodo = "Matutino"
            quantidade = 1
            finalidade = "SETOR"
            itens_reservados = "AT-001"
            horario_retirada = "08:00"
            horario_devolucao = "12:00"
            status = "Agendado"
            data_criacao = "2026-09-01T00:00:00"
            registrado_por = "OPERADOR"
            codigo_reserva = "AG1234"

        with tempfile.TemporaryDirectory() as directory:
            queue_path = str(Path(directory) / "sync_queue.db")
            previous = os.environ.get("COLEGIO_ID")
            os.environ["COLEGIO_ID"] = "tenant"
            try:
                enqueue_booking(Booking(), queue_path)
                queue = SyncQueue(queue_path)
                try:
                    pending = queue.pending()[0]
                    self.assertEqual(pending["entity_type"], "agendamento")
                    self.assertEqual(pending["payload"]["source_id"], "45")
                finally:
                    queue.close()
            finally:
                if previous is None:
                    os.environ.pop("COLEGIO_ID", None)
                else:
                    os.environ["COLEGIO_ID"] = previous