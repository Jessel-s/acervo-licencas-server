from datetime import datetime
import os
import sqlite3


DEFAULT_RETENTION_DAYS = 14


def create_database_backup(database_path, backup_dir, retention_days=DEFAULT_RETENTION_DAYS):
    """Create a consistent SQLite backup and remove backups older than retention."""
    if not os.path.isfile(database_path):
        raise FileNotFoundError(database_path)

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'patrimonio_ti_{timestamp}.db')

    source = sqlite3.connect(database_path)
    destination = sqlite3.connect(backup_path)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()

    cutoff = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)
    for filename in os.listdir(backup_dir):
        if not filename.startswith('patrimonio_ti_') or not filename.endswith('.db'):
            continue
        path = os.path.join(backup_dir, filename)
        if path != backup_path and os.path.getmtime(path) < cutoff:
            os.remove(path)

    return backup_path
