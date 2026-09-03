import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import requests

from database_local import LocalDatabase


class LicencaManager:
    """Valida a licença do PDV com fallback local por até 3 dias."""

    def __init__(
        self,
        db: LocalDatabase,
        serial_pdv: str,
        chave_ativacao: str,
        colegio_id: Optional[str] = None,
        supabase_url: Optional[str] = None,
        supabase_key: Optional[str] = None,
    ):
        self.db = db
        self.serial_pdv = serial_pdv
        self.chave_ativacao = chave_ativacao
        self.colegio_id = colegio_id
        self.supabase_url = supabase_url or os.getenv("SUPABASE_URL")
        self.supabase_key = supabase_key or os.getenv("SUPABASE_ANON_KEY")

    def _online_status(self) -> bool:
        if not self.supabase_url:
            return False
        try:
            response = requests.get(
                f"{self.supabase_url}/rest/v1/",
                headers={"apikey": self.supabase_key or ""},
                timeout=5,
            )
            return response.status_code < 500
        except Exception:
            return False

    def validar_licenca_online(self) -> Dict[str, Any]:
        if not self.supabase_url:
            return {"ok": False, "valid": False, "mensagem": "SUPABASE_URL não configurada."}

        url = f"{self.supabase_url}/functions/v1/validar-licenca"
        payload = {
            "serial_pdv": self.serial_pdv,
            "chave_ativacao": self.chave_ativacao,
            "colegio_id": self.colegio_id,
        }

        headers = {
            "Content-Type": "application/json",
            "apikey": self.supabase_key or "",
            "Authorization": f"Bearer {self.supabase_key or ''}",
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code != 200:
                return {"ok": False, "valid": False, "mensagem": response.text}

            data = response.json()
            agora = datetime.now(timezone.utc)

            estado = self.db.get_estado(self.serial_pdv, self.chave_ativacao)
            if estado:
                self.db.atualizar_estado(
                    self.serial_pdv,
                    self.chave_ativacao,
                    status="ativa" if data.get("valid") else "expirada",
                    ultima_checagem=agora,
                    ultima_validacao_sucesso=agora if data.get("valid") else None,
                    bloqueado=0 if data.get("valid") else 1,
                )
            else:
                self.db.salvar_estado(
                    self.serial_pdv,
                    self.chave_ativacao,
                    self.colegio_id,
                    status="ativa" if data.get("valid") else "expirada",
                    ultima_checagem=agora,
                    ultima_validacao_sucesso=agora if data.get("valid") else None,
                    bloqueado=0 if data.get("valid") else 1,
                )

            return data
        except Exception as exc:
            return {"ok": False, "valid": False, "mensagem": str(exc)}

    def validar_licenca_local(self) -> bool:
        estado = self.db.get_estado(self.serial_pdv, self.chave_ativacao)
        if not estado:
            return False

        ultima_validacao = estado.get("ultima_validacao_sucesso")
        if not ultima_validacao:
            return False

        try:
            data_ultima = datetime.fromisoformat(ultima_validacao.replace("Z", "+00:00"))
            agora = datetime.now(timezone.utc)
            limite = data_ultima + timedelta(days=3)

            if agora <= limite:
                return True

            self.db.atualizar_estado(
                self.serial_pdv,
                self.chave_ativacao,
                status="bloqueado",
                ultima_checagem=agora,
                bloqueado=1,
            )
            return False
        except Exception:
            return False

    def verificar(self) -> bool:
        if self._online_status():
            resultado = self.validar_licenca_online()
            return bool(resultado.get("valid"))
        return self.validar_licenca_local()
