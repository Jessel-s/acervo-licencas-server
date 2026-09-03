"""Configura uma instalação local do Acervo TI para um único tenant."""

import argparse
import os
import re
import sys
import uuid
from pathlib import Path


BASE_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"


def validate_tenant_id(value: str) -> str:
    try:
        return str(uuid.UUID(value.strip()))
    except ValueError as error:
        raise ValueError("COLEGIO_ID deve ser um UUID válido.") from error


def validate_supabase_url(value: str) -> str:
    url = value.strip().rstrip("/")
    if not re.fullmatch(r"https://[a-z0-9-]+\.supabase\.co", url):
        raise ValueError("SUPABASE_URL deve ter o formato https://seu-projeto.supabase.co.")
    return url


def build_environment(supabase_url: str, anon_key: str, serial: str, license_key: str, tenant_id: str) -> str:
    return "\n".join([
        "# Configuracao local do Acervo TI. Nao compartilhe este arquivo.",
        f"SUPABASE_URL={validate_supabase_url(supabase_url)}",
        f"SUPABASE_ANON_KEY={anon_key.strip()}",
        "",
        f"PDV_SERIAL={serial.strip()}",
        f"PDV_CHAVE={license_key.strip()}",
        f"COLEGIO_ID={validate_tenant_id(tenant_id)}",
        "",
        "# Mantenha vazio: a instalacao opera com SQLite local e sincronizacao segura.",
        "DATABASE_URL=",
        "",
    ])


def write_environment(content: str, env_path: Path = ENV_PATH, replace: bool = False) -> None:
    if env_path.exists() and not replace:
        raise RuntimeError("Já existe um .env. Use --replace somente para reconfigurar esta instalação.")
    env_path.write_text(content, encoding="utf-8")


def prompt_value(label: str) -> str:
    value = input(f"{label}: ").strip()
    if not value:
        raise ValueError(f"{label} é obrigatório.")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Grava a configuração no arquivo .env.")
    parser.add_argument("--replace", action="store_true", help="Permite substituir um .env existente.")
    arguments = parser.parse_args()

    content = build_environment(
        prompt_value("SUPABASE_URL"),
        prompt_value("SUPABASE_ANON_KEY"),
        prompt_value("PDV_SERIAL"),
        prompt_value("PDV_CHAVE"),
        prompt_value("COLEGIO_ID"),
    )
    if not arguments.apply:
        print("Validação concluída. Nenhum arquivo foi alterado. Execute novamente com --apply para gravar.")
        return
    write_environment(content, replace=arguments.replace)
    print("Configuração do cliente gravada com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as error:
        print(f"Falha na configuração: {error}", file=sys.stderr)
        sys.exit(1)