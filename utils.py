import socket
import threading
import urllib.request
import subprocess
import hashlib
import uuid
from functools import lru_cache
from flask import session
from models import db, ConfiguracaoSistema

def obter_ip_local():
    try:
        # Tenta descobrir o IP usando a tabela de roteamento local (não requer internet liberada)
        # Conecta a um IP externo conhecido (Google DNS) para determinar o IP da interface de saída.
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)) 
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        try:
            return socket.gethostbyname(socket.gethostname())
        except:
            return "127.0.0.1"

@lru_cache(maxsize=1)
def gerar_machine_id():
    """
    Gera um ID de máquina robusto baseado em múltiplos componentes de hardware.
    É mais estável que usar apenas o MAC Address.
    """
    try:
        # 1. Pega o ID do Processador (CPU)
        cpu_id = subprocess.check_output(
            'wmic cpu get ProcessorId', timeout=5
        ).decode().split('\n')[1].strip()
    except Exception:
        cpu_id = "cpu_fallback"

    try:
        # 2. Pega o Serial da Placa-Mãe
        baseboard_id = subprocess.check_output(
            'wmic baseboard get SerialNumber', timeout=5
        ).decode().split('\n')[1].strip()
    except Exception:
        baseboard_id = "board_fallback"
        
    # 3. Pega o MAC Address (como parte da combinação)
    mac_address = str(uuid.getnode())

    # 4. Combina tudo e cria um hash seguro e consistente
    combined_id = f"acervo-ti-{cpu_id}-{baseboard_id}-{mac_address}"
    hashed_id = hashlib.sha256(combined_id.encode()).hexdigest()
    
    return hashed_id

def trigger_iot_relay(force_open=False):
    """Centraliza o disparo do relé usando IP dinâmico do Banco de Dados."""
    # CORREÇÃO DEFINITIVA: A verificação da licença é feita AQUI DENTRO.
    # A função só prossegue se o módulo 'iot' estiver ativo na sessão.
    from flask import session
    if not session.get('modules', {}).get('iot', False):
        return

    try:
        # Acesso ao banco de dados precisa do contexto da aplicação
        from app import app
        with app.app_context():
            config = ConfiguracaoSistema.query.get('ip_totem_iot')
            ip = config.valor if config else '192.168.0.50'
    except Exception:
        ip = '192.168.0.50'

    def acionar(target_ip):
        try:
            urllib.request.urlopen(f'http://{target_ip}/abrir_porta', timeout=3)
        except Exception: pass # Silencia erros de comunicação com o totem
    threading.Thread(target=acionar, args=(ip,), daemon=True).start()
