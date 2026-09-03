"""Armazenamento cifrado da sessão Supabase no dispositivo local."""

import json
from pathlib import Path
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken


BASE_DIR = Path(__file__).resolve().parent
KEY_PATH = BASE_DIR / ".supabase_session.key"
SESSION_PATH = BASE_DIR / ".supabase_session.enc"


class SupabaseSessionStore:
    def __init__(self, key_path: Path = KEY_PATH, session_path: Path = SESSION_PATH) -> None:
        self.key_path = key_path
        self.session_path = session_path

    def save(self, access_token: str, refresh_token: str) -> None:
        payload = json.dumps({"access_token": access_token, "refresh_token": refresh_token})
        self.session_path.write_bytes(Fernet(self._get_or_create_key()).encrypt(payload.encode("utf-8")))

    def load(self) -> Optional[Dict[str, str]]:
        if not self.key_path.exists() or not self.session_path.exists():
            return None
        try:
            decrypted = Fernet(self.key_path.read_bytes()).decrypt(self.session_path.read_bytes())
            payload = json.loads(decrypted.decode("utf-8"))
            if payload.get("access_token") and payload.get("refresh_token"):
                return payload
        except (InvalidToken, OSError, ValueError, json.JSONDecodeError):
            return None
        return None

    def clear(self) -> None:
        self.session_path.unlink(missing_ok=True)

    def _get_or_create_key(self) -> bytes:
        if self.key_path.exists():
            return self.key_path.read_bytes()
        key = Fernet.generate_key()
        self.key_path.write_bytes(key)
        return key