import os
import sys
from datetime import datetime

from database_local import LocalDatabase
from licenca_manager import LicencaManager


def main() -> int:
    serial_pdv = os.getenv("PDV_SERIAL", "PDV-001")
    chave_ativacao = os.getenv("PDV_CHAVE", "LIC-TESTE-123")
    colegio_id = os.getenv("COLEGIO_ID")

    db = LocalDatabase("pdv_local.db")
    manager = LicencaManager(
        db=db,
        serial_pdv=serial_pdv,
        chave_ativacao=chave_ativacao,
        colegio_id=colegio_id,
    )

    try:
        if not manager.verificar():
            print(f"[{datetime.utcnow().isoformat()}] PDV bloqueado: licença inválida ou sem checagem há mais de 3 dias.")
            return 1

        print(f"[{datetime.utcnow().isoformat()}] Licença validada com sucesso.")
        print("Sistema pronto para inicializar a interface do kiosk.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
