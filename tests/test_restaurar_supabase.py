import sqlite3
import tempfile
import unittest
from pathlib import Path

from restaurar_supabase import (
    _count_from_content_range,
    local_database_has_operational_data,
    restore_to_sqlite,
)


class RestoreSupabaseTests(unittest.TestCase):
    def test_parses_exact_count_from_supabase_header(self):
        self.assertEqual(_count_from_content_range("0-0/101"), 101)

    def test_rejects_missing_count_header(self):
        with self.assertRaises(RuntimeError):
            _count_from_content_range(None)

    def test_detects_operational_data_in_local_database(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "local.db"
            connection = sqlite3.connect(database_path)
            try:
                connection.execute("CREATE TABLE notebooks (id TEXT PRIMARY KEY)")
                connection.execute("INSERT INTO notebooks (id) VALUES ('AT-001')")
                connection.commit()
            finally:
                connection.close()

            self.assertTrue(local_database_has_operational_data(database_path))

    def test_recreates_missing_sqlite_schema_during_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "restored.db"
            rows = {"ativos": [], "configuracoes_sistema": [], "sessoes_uso": [], "historico": [], "problemas": [], "agendamentos": [], "almox_produtos": [], "almox_movimentacoes": []}

            restore_to_sqlite(rows, database_path)

            connection = sqlite3.connect(database_path)
            try:
                tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            finally:
                connection.close()
            self.assertIn("notebooks", tables)
            self.assertIn("almox_movimentacoes", tables)