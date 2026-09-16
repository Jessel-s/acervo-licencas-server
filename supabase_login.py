import os
from typing import Any, Dict, Optional

try:
    from supabase import Client, create_client
except ImportError:  # pragma: no cover
    Client = Any  # type: ignore
    create_client = None  # type: ignore


def get_supabase_client() -> Optional[Client]:
    """Retorna cliente configurado do Supabase quando as variáveis estiverem presentes."""
    url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")

    if not url or not anon_key:
        return None

    if create_client is None:
        return None

    try:
        return create_client(url, anon_key)
    except Exception:
        return None


def sign_in_with_supabase(email: str, password: str) -> Dict[str, Any]:
    """Autentica no Supabase Auth usando e-mail e senha."""
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase não configurado. Verifique SUPABASE_URL e SUPABASE_ANON_KEY.")

    response = client.auth.sign_in_with_password({
        "email": email,
        "password": password,
    })

    if not response or response.user is None:
        raise ValueError("Credenciais inválidas no Supabase Auth.")

    profile_response = (
        client.table("perfis")
        .select("colegio_id, papel")
        .eq("id", response.user.id)
        .maybe_single()
        .execute()
    )
    # Com maybe_single(), algumas versões da lib retornam None quando não há linha
    # (em vez de um objeto com .data), o que causava AttributeError.
    profile_data = getattr(profile_response, "data", None) if profile_response is not None else None
    if not profile_data:
        raise ValueError("Usuário autenticado sem perfil de acesso.")

    return {
        "user_id": response.user.id,
        "email": response.user.email,
        "access_token": response.session.access_token if response.session else None,
        "refresh_token": response.session.refresh_token if response.session else None,
        "profile": profile_data,
    }