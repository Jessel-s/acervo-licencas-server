import unittest

import sync_supabase
from sync_supabase import sync_assets, sync_once


class FakeTable:
    def __init__(self):
        self.payload = None
        self.conflict = None

    def upsert(self, payload, on_conflict):
        self.payload = payload
        self.conflict = on_conflict
        return self

    def execute(self):
        return self


class FakeClient:
    def __init__(self):
        self.table_instance = FakeTable()

    def table(self, name):
        self.table_name = name
        return self.table_instance


class FakeQueue:
    def __init__(self):
        self.removed = []

    def pending(self):
        return [{
            "id": 1,
            "entity_type": "ativo",
            "entity_id": "99999",
            "operation": "upsert",
            "payload": {"id": "99999", "colegio_id": "tenant"},
        }]

    def remove(self, queue_id):
        self.removed.append(queue_id)


class SyncSupabaseTests(unittest.TestCase):
    def test_successful_asset_sync_removes_event(self):
        queue = FakeQueue()

        import sync_supabase

        original_configuration = sync_supabase.get_configuration
        original_client_factory = sync_supabase.create_client
        try:
            sync_supabase.get_configuration = lambda: {
                "SUPABASE_URL": "https://example.test",
                "SUPABASE_SERVICE_ROLE_KEY": "key",
                "COLEGIO_ID": "tenant",
            }
            sync_supabase.create_client = lambda *_: FakeClient()

            pending, sent = sync_assets(queue)

            self.assertEqual((pending, sent), (1, 1))
            self.assertEqual(queue.removed, [1])
        finally:
            sync_supabase.get_configuration = original_configuration
            sync_supabase.create_client = original_client_factory

    def test_sync_once_closes_queue_after_synchronizing(self):
        import sync_supabase

        class Queue:
            closed = False

            def close(self):
                self.closed = True

        queue = Queue()
        original_queue = sync_supabase.SyncQueue
        original_sync_with_edge_function = sync_supabase.sync_with_edge_function
        try:
            sync_supabase.SyncQueue = lambda _: queue
            sync_supabase.sync_with_edge_function = lambda _: (2, 2)

            self.assertEqual(sync_once("temporary.db"), (2, 2))
            self.assertTrue(queue.closed)
        finally:
            sync_supabase.SyncQueue = original_queue
            sync_supabase.sync_with_edge_function = original_sync_with_edge_function

    def test_edge_function_sync_removes_events_after_confirmation(self):
        queue = FakeQueue()
        calls = []
        original_configuration = sync_supabase.get_sync_configuration
        original_token = sync_supabase.get_access_token
        original_post = sync_supabase.requests.post
        try:
            sync_supabase.get_sync_configuration = lambda: {"url": "https://example.test", "anon_key": "anon"}
            sync_supabase.get_access_token = lambda: "token"
            sync_supabase.requests.post = lambda *args, **kwargs: calls.append((args, kwargs)) or type(
                "Response", (), {"status_code": 200, "json": lambda _: {"ok": True, "processed": 1}}
            )()

            pending, sent = sync_supabase.sync_with_edge_function(queue)

            self.assertEqual((pending, sent), (1, 1))
            self.assertEqual(queue.removed, [1])
            self.assertEqual(calls[0][0][0], "https://example.test/functions/v1/sincronizar-operacoes")
            self.assertEqual(calls[0][1]["headers"]["Authorization"], "Bearer token")
        finally:
            sync_supabase.get_sync_configuration = original_configuration
            sync_supabase.get_access_token = original_token
            sync_supabase.requests.post = original_post

    def test_successful_session_sync_removes_event(self):
        import sync_supabase

        queue = FakeQueue()
        queue.pending = lambda: [{
            "id": 2,
            "entity_type": "sessao_uso",
            "entity_id": "42",
            "operation": "upsert",
            "payload": {"source_id": "42", "colegio_id": "tenant"},
        }]
        original_configuration = sync_supabase.get_configuration
        original_client_factory = sync_supabase.create_client
        try:
            sync_supabase.get_configuration = lambda: {
                "SUPABASE_URL": "https://example.test",
                "SUPABASE_SERVICE_ROLE_KEY": "key",
                "COLEGIO_ID": "tenant",
            }
            sync_supabase.create_client = lambda *_: FakeClient()

            pending, sent = sync_supabase.sync_sessions(queue)

            self.assertEqual((pending, sent), (1, 1))
            self.assertEqual(queue.removed, [2])
        finally:
            sync_supabase.get_configuration = original_configuration
            sync_supabase.create_client = original_client_factory

    def test_successful_history_sync_removes_event(self):
        import sync_supabase

        queue = FakeQueue()
        queue.pending = lambda: [{
            "id": 3,
            "entity_type": "historico",
            "entity_id": "43",
            "operation": "upsert",
            "payload": {"source_id": "43", "colegio_id": "tenant"},
        }]
        original_configuration = sync_supabase.get_configuration
        original_client_factory = sync_supabase.create_client
        try:
            sync_supabase.get_configuration = lambda: {
                "SUPABASE_URL": "https://example.test",
                "SUPABASE_SERVICE_ROLE_KEY": "key",
                "COLEGIO_ID": "tenant",
            }
            sync_supabase.create_client = lambda *_: FakeClient()

            pending, sent = sync_supabase.sync_history(queue)

            self.assertEqual((pending, sent), (1, 1))
            self.assertEqual(queue.removed, [3])
        finally:
            sync_supabase.get_configuration = original_configuration
            sync_supabase.create_client = original_client_factory

    def test_successful_issue_sync_removes_event(self):
        import sync_supabase

        queue = FakeQueue()
        queue.pending = lambda: [{
            "id": 4,
            "entity_type": "problema",
            "entity_id": "44",
            "operation": "upsert",
            "payload": {"source_id": "44", "colegio_id": "tenant"},
        }]
        original_configuration = sync_supabase.get_configuration
        original_client_factory = sync_supabase.create_client
        try:
            sync_supabase.get_configuration = lambda: {
                "SUPABASE_URL": "https://example.test",
                "SUPABASE_SERVICE_ROLE_KEY": "key",
                "COLEGIO_ID": "tenant",
            }
            sync_supabase.create_client = lambda *_: FakeClient()

            pending, sent = sync_supabase.sync_issues(queue)

            self.assertEqual((pending, sent), (1, 1))
            self.assertEqual(queue.removed, [4])
        finally:
            sync_supabase.get_configuration = original_configuration
            sync_supabase.create_client = original_client_factory

    def test_successful_booking_sync_removes_event(self):
        import sync_supabase

        queue = FakeQueue()
        queue.pending = lambda: [{
            "id": 5,
            "entity_type": "agendamento",
            "entity_id": "45",
            "operation": "upsert",
            "payload": {"source_id": "45", "colegio_id": "tenant"},
        }]
        original_configuration = sync_supabase.get_configuration
        original_client_factory = sync_supabase.create_client
        try:
            sync_supabase.get_configuration = lambda: {
                "SUPABASE_URL": "https://example.test",
                "SUPABASE_SERVICE_ROLE_KEY": "key",
                "COLEGIO_ID": "tenant",
            }
            sync_supabase.create_client = lambda *_: FakeClient()

            pending, sent = sync_supabase.sync_bookings(queue)

            self.assertEqual((pending, sent), (1, 1))
            self.assertEqual(queue.removed, [5])
        finally:
            sync_supabase.get_configuration = original_configuration
            sync_supabase.create_client = original_client_factory