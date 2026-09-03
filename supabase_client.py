import os
from typing import Any, Dict, Optional

from supabase import Client, create_client


class SupabaseClient:
    """Cliente para interagir com o Supabase PostgreSQL + Auth + Edge Functions."""

    def __init__(self, url: Optional[str] = None, key: Optional[str] = None):
        self.url = url or os.getenv("SUPABASE_URL")
        self.key = key or os.getenv("SUPABASE_SERVICE_ROLE_KEY")

        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar configurados.")

        self.client: Client = create_client(self.url, self.key)

    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        response = self.client.table("perfis").select("*").eq("id", user_id).execute()
        return response.data[0] if response.data else {}

    def get_colegio(self, colegio_id: str) -> Dict[str, Any]:
        response = self.client.table("colegios").select("*").eq("id", colegio_id).execute()
        return response.data[0] if response.data else {}

    def get_licenca_by_serial(self, serial_pdv: str) -> Dict[str, Any]:
        response = self.client.table("licencas").select("*").eq("serial_pdv", serial_pdv).execute()
        return response.data[0] if response.data else {}

    def atualizar_licenca_status(self, licenca_id: str, status: str, ultima_checagem: str) -> None:
        self.client.table("licencas").update({
            "status": status,
            "ultima_checagem": ultima_checagem,
        }).eq("id", licenca_id).execute()
