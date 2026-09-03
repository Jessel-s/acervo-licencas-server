"""Migra agendamentos locais para o tenant configurado no Supabase."""

import argparse
import sqlite3
import sys

from supabase import create_client

from migrar_notebooks_supabase import BATCH_SIZE, SQLITE_PATH, chunks, get_configuration


def read_bookings(colegio_id):
    if not SQLITE_PATH.exists():
        raise RuntimeError(f"Banco SQLite nao encontrado: {SQLITE_PATH}")

    columns = (
        "id, solicitante, data_uso, periodo, quantidade, finalidade, itens_reservados, "
        "horario_retirada, horario_devolucao, status, data_criacao, registrado_por, "
        "codigo_reserva"
    )
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT {columns} FROM agendamentos ORDER BY id"
        ).fetchall()

    return [{**dict(row), "colegio_id": colegio_id} for row in rows]


def migrate(apply_changes):
    configuration = get_configuration()
    records = read_bookings(configuration["COLEGIO_ID"])
    print(f"Agendamentos encontrados no SQLite: {len(records)}")

    if not apply_changes:
        print("Simulacao concluida. Nenhum dado foi enviado ao Supabase.")
        return

    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    for batch in chunks(records, BATCH_SIZE):
        client.table("agendamentos").upsert(batch, on_conflict="id").execute()

    result = (
        client.table("agendamentos")
        .select("id", count="exact")
        .eq("colegio_id", configuration["COLEGIO_ID"])
        .execute()
    )
    print(f"Migracao concluida. Agendamentos no tenant: {result.count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Envia os agendamentos ao Supabase. Sem esta opcao, apenas simula.",
    )
    arguments = parser.parse_args()
    try:
        migrate(arguments.apply)
    except Exception as error:
        print(f"Falha na migracao: {error}", file=sys.stderr)
        sys.exit(1)