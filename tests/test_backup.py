import os
import sqlite3
import tempfile
import unittest

from backup import create_database_backup


class BackupTests(unittest.TestCase):
    def test_creates_a_restorable_sqlite_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = os.path.join(temp_dir, 'source.db')
            backup_dir = os.path.join(temp_dir, 'backups')

            connection = sqlite3.connect(database_path)
            connection.execute('CREATE TABLE assets (id INTEGER PRIMARY KEY, name TEXT)')
            connection.execute("INSERT INTO assets (name) VALUES ('teste')")
            connection.commit()
            connection.close()

            backup_path = create_database_backup(database_path, backup_dir)

            self.assertTrue(os.path.isfile(backup_path))
            restored = sqlite3.connect(backup_path)
            row = restored.execute('SELECT name FROM assets').fetchone()
            restored.close()
            self.assertEqual(row[0], 'teste')


if __name__ == '__main__':
    unittest.main()