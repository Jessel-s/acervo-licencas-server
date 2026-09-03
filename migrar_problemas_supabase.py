"""Migra ocorrencias de manutencao locais para o tenant no Supabase."""

import argparse
import sqlite3
import sys

from supabase import create_client

from migrar_notebooks_supabase import SQLITE_PATH, get_configuration


def read_issues(colegio_id):
    if not SQLITE_PATH.exists():
        raise RuntimeError(f"Banco SQLite nao encontrado: {SQLITE_PATH}")

    columns = (
        "id, notebook_id, tipo_problema, descricao, data_registro, responsavel, "
        "status, prioridade, categoria, parecer_tecnico, local_incidente, data_resolucao"
    )
    with sqlite3.connect(SQLITE_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT {columns} FROM problemas ORDER BY id"
        ).fetchall()

    return [
        {
            **{
                key: value
                for key, value in dict(row).items()
                if key != "notebook_id"
            },
            "ativo_id": row["notebook_id"],
            "colegio_id": colegio_id,
        }
        for row in rows
    ]


def migrate(apply_changes):
    configuration = get_configuration()
    records = read_issues(configuration["COLEGIO_ID"])
    print(f"Ocorrencias encontradas no SQLite: {len(records)}")

    if not apply_changes:
        print("Simulacao concluida. Nenhum dado foi enviado ao Supabase.")
        return

    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    client.table("problemas").upsert(records, on_conflict="id").execute()

    result = (
        client.table("problemas")
        .select("id", count="exact")
        .eq("colegio_id", configuration["COLEGIO_ID"])
        .execute()
    )
    print(f"Migracao concluida. Ocorrencias no tenant: {result.count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Envia as ocorrencias ao Supabase. Sem esta opcao, apenas simula.",
    )
    arguments = parser.parse_args()
    try:
        migrate(arguments.apply)
    except Exception as error:
        print(f"Falha na migracao: {error}", file=sys.stderr)
        sys.exit(1)