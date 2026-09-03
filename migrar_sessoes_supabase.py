"""Migra sessoes de uso locais para o tenant configurado no Supabase."""

import argparse
import sqlite3
import sys

from supabase import create_client

from migrar_notebooks_supabase import SQLITE_PATH, get_configuration


def read_sessions(colegio_id):
    if not SQLITE_PATH.exists():
        raise RuntimeError(f"Banco SQLite nao encontrado: {SQLITE_PATH}")

    columns = (
        "id, turma, professor, programa, data_inicio, quantidade_notebooks, "
        "observacoes, previsao_devolucao, usuario_movimentacao"
    )
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT {columns} FROM sessoes_uso ORDER BY id"
        ).fetchall()

    return [{**dict(row), "colegio_id": colegio_id} for row in rows]


def migrate(apply_changes):
    configuration = get_configuration()
    records = read_sessions(configuration["COLEGIO_ID"])
    print(f"Sessoes encontradas no SQLite: {len(records)}")

    if not apply_changes:
        print("Simulacao concluida. Nenhum dado foi enviado ao Supabase.")
        return

    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    client.table("sessoes_uso").upsert(records, on_conflict="id").execute()

    result = (
        client.table("sessoes_uso")
        .select("id", count="exact")
        .eq("colegio_id", configuration["COLEGIO_ID"])
        .execute()
    )
    print(f"Migracao concluida. Sessoes no tenant: {result.count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Envia as sessoes ao Supabase. Sem esta opcao, apenas simula.",
    )
    arguments = parser.parse_args()
    try:
        migrate(arguments.apply)
    except Exception as error:
        print(f"Falha na migracao: {error}", file=sys.stderr)
        sys.exit(1)