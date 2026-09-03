"""Restaura os dados do tenant do Supabase para um SQLite local vazio."""

import argparse
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import requests

from sync_supabase import get_access_token, get_sync_configuration


BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "patrimonio_ti.db"
RESTORE_TABLES = (
    "ativos",
    "configuracoes_sistema",
    "sessoes_uso",
    "historico",
    "problemas",
    "agendamentos",
    "almox_produtos",
    "almox_movimentacoes",
)

TABLE_COLUMNS = {
    "ativos": "id, numero_carrinho, tipo, modelo, numero_serie, data_compra, status, localizacao, observacoes, data_cadastro",
    "configuracoes_sistema": "chave, valor",
    "sessoes_uso": "source_id, turma, professor, programa, data_inicio, quantidade_notebooks, observacoes, previsao_devolucao, usuario_movimentacao",
    "historico": "source_id, id_etiqueta, acao, usuario_movimentacao, responsavel, data, obs",
    "problemas": "source_id, ativo_id, tipo_problema, descricao, data_registro, responsavel, status, prioridade, categoria, parecer_tecnico, local_incidente, data_resolucao",
    "agendamentos": "source_id, solicitante, data_uso, periodo, quantidade, finalidade, itens_reservados, horario_retirada, horario_devolucao, status, data_criacao, registrado_por, codigo_reserva",
    "almox_produtos": "source_id, sku, nome, categoria, quantidade_atual, estoque_minimo, custo_unitario",
    "almox_movimentacoes": "source_id, produto_source_id, tipo, quantidade, usuario, destino_id, data_movimentacao, observacao",
}

LOCAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS notebooks (
    id TEXT PRIMARY KEY, numero_carrinho INTEGER UNIQUE, tipo TEXT NOT NULL DEFAULT 'Notebook',
    modelo TEXT, numero_serie TEXT, data_compra TEXT, status TEXT NOT NULL DEFAULT 'Disponível',
    localizacao TEXT, observacoes TEXT, data_cadastro TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS configuracoes_sistema (chave TEXT PRIMARY KEY, valor TEXT);
CREATE TABLE IF NOT EXISTS sessoes_uso (
    id INTEGER PRIMARY KEY AUTOINCREMENT, turma TEXT, professor TEXT, programa TEXT,
    data_inicio TEXT NOT NULL, quantidade_notebooks INTEGER, observacoes TEXT,
    previsao_devolucao TEXT, usuario_movimentacao TEXT
);
CREATE TABLE IF NOT EXISTS problemas (
    id INTEGER PRIMARY KEY AUTOINCREMENT, notebook_id TEXT REFERENCES notebooks(id) ON DELETE CASCADE,
    tipo_problema TEXT, descricao TEXT, data_registro TEXT NOT NULL, responsavel TEXT, status TEXT,
    prioridade TEXT NOT NULL DEFAULT 'Normal', categoria TEXT NOT NULL DEFAULT 'Hardware',
    parecer_tecnico TEXT, local_incidente TEXT NOT NULL DEFAULT 'NÃO INFORMADO', data_resolucao TEXT
);
CREATE TABLE IF NOT EXISTS historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT, id_etiqueta TEXT, acao TEXT, usuario_movimentacao TEXT,
    responsavel TEXT NOT NULL DEFAULT '-', data TEXT NOT NULL, obs TEXT
);
CREATE TABLE IF NOT EXISTS agendamentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, solicitante TEXT, data_uso TEXT, periodo TEXT, quantidade INTEGER,
    finalidade TEXT, itens_reservados TEXT, horario_retirada TEXT, horario_devolucao TEXT,
    status TEXT NOT NULL DEFAULT 'Agendado', data_criacao TEXT NOT NULL, registrado_por TEXT, codigo_reserva TEXT
);
CREATE TABLE IF NOT EXISTS almox_produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT, sku TEXT NOT NULL UNIQUE, nome TEXT NOT NULL, categoria TEXT,
    quantidade_atual INTEGER NOT NULL DEFAULT 0, estoque_minimo INTEGER NOT NULL DEFAULT 5,
    custo_unitario REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS almox_movimentacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT, produto_id INTEGER NOT NULL REFERENCES almox_produtos(id),
    tipo TEXT NOT NULL, quantidade INTEGER NOT NULL, usuario TEXT, destino_id TEXT,
    data_movimentacao TEXT NOT NULL, observacao TEXT
);
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL UNIQUE, password TEXT NOT NULL,
    perm_movimentacao INTEGER NOT NULL DEFAULT 0, perm_cadastro INTEGER NOT NULL DEFAULT 0,
    perm_config INTEGER NOT NULL DEFAULT 0, perm_kiosk INTEGER NOT NULL DEFAULT 0,
    perm_chamados INTEGER NOT NULL DEFAULT 0, perm_ajuda INTEGER NOT NULL DEFAULT 0,
    perm_almoxarifado INTEGER NOT NULL DEFAULT 0, last_login TEXT
);
"""


def _count_from_content_range(content_range):
    match = re.search(r"/(\d+)$", content_range or "")
    if not match:
        raise RuntimeError("O Supabase não informou a contagem da tabela.")
    return int(match.group(1))


def get_cloud_counts(request_head=requests.head):
    configuration = get_sync_configuration()
    token = get_access_token()
    headers = {
        "apikey": configuration["anon_key"],
        "Authorization": f"Bearer {token}",
        "Prefer": "count=exact",
    }
    counts = {}
    for table in RESTORE_TABLES:
        response = request_head(
            f"{configuration['url']}/rest/v1/{table}",
            params={"select": "*"},
            headers=headers,
            timeout=20,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Não foi possível consultar {table}: HTTP {response.status_code}")
        counts[table] = _count_from_content_range(response.headers.get("content-range"))
    return counts


def get_cloud_rows(request_get=requests.get):
    configuration = get_sync_configuration()
    token = get_access_token()
    headers = {
        "apikey": configuration["anon_key"],
        "Authorization": f"Bearer {token}",
    }
    rows = {}
    for table in RESTORE_TABLES:
        response = request_get(
            f"{configuration['url']}/rest/v1/{table}",
            params={"select": TABLE_COLUMNS[table], "order": "id.asc"},
            headers=headers,
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Não foi possível baixar {table}: HTTP {response.status_code}")
        rows[table] = response.json()
    return rows


def local_database_has_operational_data(database_path=SQLITE_PATH):
    if not database_path.exists():
        return False
    connection = sqlite3.connect(database_path)
    try:
        for table in ("notebooks", "sessoes_uso", "historico", "problemas", "agendamentos", "almox_produtos", "almox_movimentacoes"):
            try:
                if connection.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
                    return True
            except sqlite3.OperationalError:
                continue
    finally:
        connection.close()
    return False


def create_restore_backup(database_path=SQLITE_PATH):
    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"antes_restauracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(database_path, backup_path)
    return backup_path


def restore_to_sqlite(rows, database_path=SQLITE_PATH):
    if local_database_has_operational_data(database_path):
        raise RuntimeError("O SQLite local possui dados. A restauração só é permitida em um banco vazio.")

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(LOCAL_SCHEMA)
        connection.executemany(
            "INSERT INTO notebooks (id, numero_carrinho, tipo, modelo, numero_serie, data_compra, status, localizacao, observacoes, data_cadastro) VALUES (:id, :numero_carrinho, :tipo, :modelo, :numero_serie, :data_compra, :status, :localizacao, :observacoes, :data_cadastro)",
            rows["ativos"],
        )
        connection.executemany(
            "INSERT INTO configuracoes_sistema (chave, valor) VALUES (:chave, :valor)",
            rows["configuracoes_sistema"],
        )
        connection.executemany(
            "INSERT INTO sessoes_uso (id, turma, professor, programa, data_inicio, quantidade_notebooks, observacoes, previsao_devolucao, usuario_movimentacao) VALUES (CAST(:source_id AS INTEGER), :turma, :professor, :programa, :data_inicio, :quantidade_notebooks, :observacoes, :previsao_devolucao, :usuario_movimentacao)",
            rows["sessoes_uso"],
        )
        connection.executemany(
            "INSERT INTO historico (id, id_etiqueta, acao, usuario_movimentacao, responsavel, data, obs) VALUES (CAST(:source_id AS INTEGER), :id_etiqueta, :acao, :usuario_movimentacao, :responsavel, :data, :obs)",
            rows["historico"],
        )
        connection.executemany(
            "INSERT INTO problemas (id, notebook_id, tipo_problema, descricao, data_registro, responsavel, status, prioridade, categoria, parecer_tecnico, local_incidente, data_resolucao) VALUES (CAST(:source_id AS INTEGER), :ativo_id, :tipo_problema, :descricao, :data_registro, :responsavel, :status, :prioridade, :categoria, :parecer_tecnico, :local_incidente, :data_resolucao)",
            rows["problemas"],
        )
        connection.executemany(
            "INSERT INTO agendamentos (id, solicitante, data_uso, periodo, quantidade, finalidade, itens_reservados, horario_retirada, horario_devolucao, status, data_criacao, registrado_por, codigo_reserva) VALUES (CAST(:source_id AS INTEGER), :solicitante, :data_uso, :periodo, :quantidade, :finalidade, :itens_reservados, :horario_retirada, :horario_devolucao, :status, :data_criacao, :registrado_por, :codigo_reserva)",
            rows["agendamentos"],
        )
        connection.executemany(
            "INSERT INTO almox_produtos (id, sku, nome, categoria, quantidade_atual, estoque_minimo, custo_unitario) VALUES (CAST(:source_id AS INTEGER), :sku, :nome, :categoria, :quantidade_atual, :estoque_minimo, :custo_unitario)",
            rows["almox_produtos"],
        )
        connection.executemany(
            "INSERT INTO almox_movimentacoes (id, produto_id, tipo, quantidade, usuario, destino_id, data_movimentacao, observacao) VALUES (CAST(:source_id AS INTEGER), CAST(:produto_source_id AS INTEGER), :tipo, :quantidade, :usuario, :destino_id, :data_movimentacao, :observacao)",
            rows["almox_movimentacoes"],
        )
        connection.commit()
    finally:
        connection.close()


def apply_restore():
    if local_database_has_operational_data():
        backup_path = create_restore_backup()
        raise RuntimeError(f"Restauração cancelada: o banco local não está vazio. Backup criado em {backup_path.name}.")
    rows = get_cloud_rows()
    restore_to_sqlite(rows)
    return {table: len(records) for table, records in rows.items()}


def simulate_restore():
    counts = get_cloud_counts()
    print("Simulacao de restauracao concluida. Nenhum arquivo local foi alterado.")
    for table in RESTORE_TABLES:
        print(f"{table}: {counts[table]}")
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Restaura em um SQLite local vazio.")
    arguments = parser.parse_args()
    try:
        if arguments.apply:
            counts = apply_restore()
            print("Restauração concluída.")
            for table in RESTORE_TABLES:
                print(f"{table}: {counts[table]}")
        else:
            simulate_restore()
    except Exception as error:
        print(f"Falha na simulacao de restauracao: {error}", file=sys.stderr)
        sys.exit(1)