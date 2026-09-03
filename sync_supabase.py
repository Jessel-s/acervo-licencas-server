"""Envia pendencias da fila offline para o Supabase."""

import os
import sys
import threading
from pathlib import Path
from typing import Callable

import requests
from supabase import create_client
from dotenv import load_dotenv

from migrar_notebooks_supabase import get_configuration
from supabase_login import get_supabase_client
from supabase_session import SupabaseSessionStore
from sync_queue import SyncQueue


BASE_DIR = Path(__file__).resolve().parent
SYNC_ORDER = (
    "ativo",
    "sessao_uso",
    "historico",
    "problema",
    "agendamento",
    "almox_produto",
    "almox_movimentacao",
    "almox_produto_delete",
)


def get_sync_configuration():
    load_dotenv(BASE_DIR / ".env")
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not anon_key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_ANON_KEY devem estar configurados.")
    return {"url": url.rstrip("/"), "anon_key": anon_key}


def get_access_token():
    stored_session = SupabaseSessionStore().load()
    if not stored_session:
        raise RuntimeError("Faça login com uma conta Supabase para sincronizar.")

    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Cliente Supabase não configurado.")
    response = client.auth.refresh_session(stored_session["refresh_token"])
    if not response.session:
        raise RuntimeError("Sessão Supabase expirada. Faça login novamente.")

    SupabaseSessionStore().save(
        response.session.access_token,
        response.session.refresh_token,
    )
    return response.session.access_token


def _ordered_events(events):
    ordered = []
    for entity_type in SYNC_ORDER:
        for event in events:
            is_product_delete = (
                event["entity_type"] == "almox_produto"
                and event["operation"] == "delete"
            )
            if entity_type == "almox_produto_delete" and is_product_delete:
                ordered.append(event)
            elif entity_type == event["entity_type"] and not is_product_delete:
                ordered.append(event)
    return ordered


def sync_with_edge_function(queue):
    events = queue.pending()
    if not events:
        return 0, 0

    configuration = get_sync_configuration()
    token = get_access_token()
    endpoint = f"{configuration['url']}/functions/v1/sincronizar-operacoes"
    ordered_events = _ordered_events(events)
    sent = 0

    for start in range(0, len(ordered_events), 100):
        batch = ordered_events[start:start + 100]
        response = requests.post(
            endpoint,
            json={"events": batch},
            headers={
                "apikey": configuration["anon_key"],
                "Authorization": f"Bearer {token}",
            },
            timeout=30,
        )
        if response.status_code != 200:
            raise RuntimeError(f"Edge Function recusou a sincronizacao: HTTP {response.status_code}")
        result = response.json()
        if not result.get("ok") or result.get("processed") != len(batch):
            raise RuntimeError("Edge Function nao confirmou todas as operacoes.")
        for event in batch:
            queue.remove(event["id"])
        sent += len(batch)
    return len(events), sent


def sync_assets(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [event for event in queue.pending() if event["entity_type"] == "ativo"]
    sent = 0

    for event in pending:
        if event["operation"] == "upsert":
            client.table("ativos").upsert(
                event["payload"],
                on_conflict="colegio_id,id",
            ).execute()
        else:
            client.table("ativos").delete().eq(
                "colegio_id", configuration["COLEGIO_ID"]
            ).eq("id", event["entity_id"]).execute()
        queue.remove(event["id"])
        sent += 1

    return len(pending), sent


def sync_sessions(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [event for event in queue.pending() if event["entity_type"] == "sessao_uso"]
    sent = 0

    for event in pending:
        client.table("sessoes_uso").upsert(
            event["payload"],
            on_conflict="colegio_id,source_id",
        ).execute()
        queue.remove(event["id"])
        sent += 1

    return len(pending), sent


def sync_history(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [event for event in queue.pending() if event["entity_type"] == "historico"]
    sent = 0

    for event in pending:
        client.table("historico").upsert(
            event["payload"],
            on_conflict="colegio_id,source_id",
        ).execute()
        queue.remove(event["id"])
        sent += 1

    return len(pending), sent


def sync_issues(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [event for event in queue.pending() if event["entity_type"] == "problema"]
    sent = 0

    for event in pending:
        client.table("problemas").upsert(
            event["payload"],
            on_conflict="colegio_id,source_id",
        ).execute()
        queue.remove(event["id"])
        sent += 1

    return len(pending), sent


def sync_bookings(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [event for event in queue.pending() if event["entity_type"] == "agendamento"]
    sent = 0

    for event in pending:
        client.table("agendamentos").upsert(
            event["payload"],
            on_conflict="colegio_id,source_id",
        ).execute()
        queue.remove(event["id"])
        sent += 1

    return len(pending), sent


def sync_storeroom_products(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [
        event for event in queue.pending()
        if event["entity_type"] == "almox_produto" and event["operation"] == "upsert"
    ]
    sent = 0

    for event in pending:
        client.table("almox_produtos").upsert(
            event["payload"], on_conflict="colegio_id,source_id"
        ).execute()
        queue.remove(event["id"])
        sent += 1

    return len(pending), sent


def sync_storeroom_movements(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [event for event in queue.pending() if event["entity_type"] == "almox_movimentacao"]
    sent = 0

    for event in pending:
        if event["operation"] == "upsert":
            client.table("almox_movimentacoes").upsert(
                event["payload"], on_conflict="colegio_id,source_id"
            ).execute()
        else:
            client.table("almox_movimentacoes").delete().eq(
                "colegio_id", configuration["COLEGIO_ID"]
            ).eq("source_id", event["entity_id"]).execute()
        queue.remove(event["id"])
        sent += 1

    return len(pending), sent


def sync_storeroom_product_deletions(queue):
    configuration = get_configuration()
    client = create_client(
        configuration["SUPABASE_URL"],
        configuration["SUPABASE_SERVICE_ROLE_KEY"],
    )
    pending = [
        event for event in queue.pending()
        if event["entity_type"] == "almox_produto" and event["operation"] == "delete"
    ]
    sent = 0
    for event in pending:
        client.table("almox_produtos").delete().eq(
            "colegio_id", configuration["COLEGIO_ID"]
        ).eq("source_id", event["entity_id"]).execute()
        queue.remove(event["id"])
        sent += 1
    return len(pending), sent


def sync_once(queue_path="sync_queue.db"):
    queue = SyncQueue(queue_path)
    try:
        return sync_with_edge_function(queue)
    finally:
        queue.close()


def start_periodic_sync(queue_path, interval_seconds, log: Callable[[str], None]):
    def run():
        stop_event = threading.Event()
        while True:
            try:
                pending, sent = sync_once(queue_path)
                if pending:
                    log(f"Sincronizacao de ativos concluida: {sent}/{pending} pendencias enviadas.")
            except Exception as error:
                log(f"Sincronizacao pendente indisponivel: {type(error).__name__}.")
            stop_event.wait(interval_seconds)

    worker = threading.Thread(target=run, name="supabase-sync", daemon=True)
    worker.start()
    return worker


def main():
    pending, sent = sync_once()
    print(f"Pendencias de ativos encontradas: {pending}")
    print(f"Sincronizacao concluida. Pendencias enviadas: {sent}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Falha na sincronizacao: {error}", file=sys.stderr)
        sys.exit(1)