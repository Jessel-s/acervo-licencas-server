"""Migra notebooks do SQLite local para o tenant configurado no Supabase."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "patrimonio_ti.db"
BATCH_SIZE = 100


def get_configuration():
    load_dotenv(BASE_DIR / ".env")
    required = {
        "SUPABASE_URL": os.getenv("SUPABASE_URL"),
        "SUPABASE_SERVICE_ROLE_KEY": os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        "COLEGIO_ID": os.getenv("COLEGIO_ID"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Variaveis ausentes no .env: {', '.join(missing)}")
    return required


def read_notebooks(colegio_id):
    if not SQLITE_PATH.exists():
        raise RuntimeError(f"Banco SQLite nao encontrado: {SQLITE_PATH}")

    columns = (
        "id, numero_carrinho, tipo, modelo, numero_serie, data_compra, "
        "status, localizacao, observacoes, data_cadastro"
    )
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(f"SELECT {columns} FROM notebooks ORDER BY id").fetchall()

    return [{**dict(row), "colegio_id": colegio_id} for row in rows]


def chunks(records, size):
    for start in range(0, len(records), size):
        yield records[start:start + size]


def migrate(apply_changes):
    configuration = get_configuration()
    records = read_notebooks(configuration["COLEGIO_ID"])
    print(f"Notebooks encontrados no SQLite: {len(records)}")

    if not apply_changes:
        print("Simulacao concluida. Nenhum dado foi enviado ao Supabase.")
        return

    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    for batch in chunks(records, BATCH_SIZE):
        client.table("ativos").upsert(batch, on_conflict="colegio_id,id").execute()

    result = (
        client.table("ativos")
        .select("id", count="exact")
        .eq("colegio_id", configuration["COLEGIO_ID"])
        .execute()
    )
    print(f"Migracao concluida. Ativos no tenant: {result.count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Envia os notebooks ao Supabase. Sem esta opcao, apenas simula.",
    )
    arguments = parser.parse_args()
    try:
        migrate(arguments.apply)
    except Exception as error:
        print(f"Falha na migracao: {error}", file=sys.stderr)
        sys.exit(1)