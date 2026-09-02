# c:\DESENVOLVIMENTO\gestao_ativos_web\app.py
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, g, send_file, session, jsonify
import sqlite3
from datetime import datetime, timedelta, timezone
from sqlalchemy import event, func, or_, and_
import os
import uuid
import hashlib
import json
import logging
from logging.handlers import RotatingFileHandler
import traceback
import sys
from flask_wtf.csrf import CSRFProtect
import base64
from flask_migrate import Migrate
import time
import threading
import urllib.request # Importação já existe
from cryptography.fernet import Fernet, InvalidToken

from auth import auth_bp, login_required, permission_required, kiosk_unlock, kiosk_exit
from inventory import inventory_bp
from movements import movements_bp # Importa o novo Blueprint de Movimentações
from maintenance import maintenance_bp # Importa o novo Blueprint de Manutenção
from settings import settings_bp # Importa o novo Blueprint de Configurações
from storeroom import storeroom_bp # Importa o Blueprint de Almoxarifado
from models import db, Notebook, Historico, SessaoUso, Agendamento, AlmoxProduto, Problema # Importação já existe
from utils import trigger_iot_relay
from availability import is_available_after_return, parse_datetime_value, schedule_start
from backup import create_database_backup

# Define o caminho absoluto para a pasta do projeto
if getattr(sys, 'frozen', False):
    basedir = os.path.dirname(sys.executable)
else:
    basedir = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__, template_folder=os.path.join(basedir, 'templates'), static_folder=os.path.join(basedir, 'static'))
app.config['TEMPLATES_AUTO_RELOAD'] = False

# --- CONFIGURAÇÃO DO BANCO DE DADOS (SQLAlchemy) ---
# --- ADAPTAÇÃO PARA CLOUD: Lê a URL do banco de uma variável de ambiente ---
# No servidor cloud, você define: DATABASE_URL=postgresql://user:password@host:port/dbname
# Se a variável não existir, ele usa o SQLite local (para desenvolvimento).
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres'):
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url.replace("postgres://", "postgresql://", 1)
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "patrimonio_ti.db")}'
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'check_same_thread': False, 'timeout': 30}
    }
db.init_app(app)
migrate = Migrate(app, db)

if not database_url:
    with app.app_context():
        with db.engine.connect() as connection:
            connection.exec_driver_sql('PRAGMA journal_mode = WAL')

        @event.listens_for(db.engine, 'connect')
        def configure_sqlite_connection(dbapi_connection, _):
            dbapi_connection.execute('PRAGMA busy_timeout = 30000')

app.register_blueprint(auth_bp)
app.register_blueprint(inventory_bp) 
app.register_blueprint(movements_bp) 
app.register_blueprint(maintenance_bp) 
app.register_blueprint(settings_bp) 
app.register_blueprint(storeroom_bp) 

# --- SISTEMA DE LOGS PARA SUPORTE TÉCNICO ---
log_file = os.path.join(basedir, 'sistema_erros.log')
# Cria um arquivo de log que chega no máximo a 1MB e guarda até 3 backups antigos
file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s [em %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('--- INICIALIZANDO O SISTEMA ---')

# --- SEGURANÇA COMERCIAL: GERENCIAMENTO DE CHAVE SECRETA ---
secret_file = os.path.join(basedir, 'secret.key')
if os.path.exists(secret_file):
    with open(secret_file, 'rb') as f:
        app.secret_key = f.read()
else:
    random_key = os.urandom(24)
    with open(secret_file, 'wb') as f:
        f.write(random_key)
    app.secret_key = random_key

# --- CONFIGURAÇÃO DE SEGURANÇA COMERCIAL ---
csrf = CSRFProtect(app) 

# Isenta as APIs do Kiosk da verificação CSRF 
# (Elas exigem usuário e senha na requisição. Se não isentarmos, o Kiosk_Exit falha com erro 400 pois o unlock troca a sessão e invalida o token da tela)
csrf.exempt(kiosk_unlock)
csrf.exempt(kiosk_exit)

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
SLOW_REQUEST_SECONDS = 1.0

# --- TRATAMENTO GLOBAL DE ERROS ---
@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    # Se for um erro normal de navegação (como página ou imagem não encontrada - 404), deixa o Flask cuidar
    if isinstance(e, HTTPException):
        return e
    # Grava o erro completo (Traceback) no arquivo de log
    app.logger.error(f"Erro não tratado capturado:\n{traceback.format_exc()}")
    # Retorna uma mensagem amigável para o usuário em vez da tela branca do Flask
    return "Ocorreu um erro interno no sistema. Por favor, contate o suporte e envie o arquivo 'sistema_erros.log'.", 500

# --- SISTEMA DE LICENÇA MODULAR E TRIAL ---
def get_license_secret():
    """Carrega a chave secreta de um arquivo para não deixá-la no código."""
    secret_file = os.path.join(basedir, 'license_secret.bin')
    if os.path.exists(secret_file):
        with open(secret_file, 'rb') as f:
            return f.read()
    # Se o arquivo não existir, o sistema não pode validar licenças.
    # Retornar None fará com que a validação falhe de forma segura.
    return None

_license_cache = {'time': 0, 'data': None}
LICENSE_ONLINE_GRACE_SECONDS = 7 * 24 * 60 * 60

def get_license_online_cache_path():
    return os.path.join(basedir, '.license_online_cache.json')

def save_license_online_validation(machine_id, license_key):
    cache_data = {
        'machine_id': machine_id,
        'license_hash': hashlib.sha256(license_key.encode()).hexdigest(),
        'validated_at': time.time()
    }
    with open(get_license_online_cache_path(), 'w', encoding='utf-8') as cache_file:
        json.dump(cache_data, cache_file)

def has_recent_online_validation(machine_id, license_key):
    try:
        with open(get_license_online_cache_path(), 'r', encoding='utf-8') as cache_file:
            cache_data = json.load(cache_file)
        return (
            cache_data.get('machine_id') == machine_id and
            cache_data.get('license_hash') == hashlib.sha256(license_key.encode()).hexdigest() and
            time.time() - float(cache_data.get('validated_at', 0)) < LICENSE_ONLINE_GRACE_SECONDS
        )
    except (OSError, ValueError, TypeError):
        return False

def get_license_info(force_revalidate: bool = False) -> tuple:
    """Valida a licença e retorna o status e os módulos habilitados."""
    global _license_cache
    
    # CORREÇÃO DEFINITIVA: Se forçar a revalidação, o cache antigo é destruído.
    if force_revalidate:
        _license_cache = {'time': 0, 'data': None}

    # Revalida licenças online com frequência suficiente para permitir revogação.
    if not force_revalidate and _license_cache['data'] and time.time() - _license_cache['time'] < 300:
        return _license_cache['data']

    # O modo cloud pertence ao servidor de licenças, não ao executável do cliente.
    # Nunca ignore a licença no cliente, pois isso impede revogação remota.
    if os.environ.get('CLOUD_DEPLOY') == 'TRUE' and os.environ.get('LICENSE_SERVER_MODE') == 'TRUE':
        all_modules = {'iot': True, 'helpdesk': True, 'storeroom': True}
        result = ('VALID', 36500, all_modules) # Licença "infinita" para o seu próprio servidor
        _license_cache = {'time': time.time(), 'data': result}
        return result
        
    # NOVA LÓGICA: Help Desk e Almoxarifado são padrão. Apenas IoT é opcional.
    # CORREÇÃO: Durante o Trial, TODOS os módulos devem estar liberados para teste.
    default_modules = {'iot': True, 'helpdesk': True, 'storeroom': True}
    
    from utils import gerar_machine_id
    current_machine_id = gerar_machine_id()
    license_file = os.path.join(basedir, "licenca.key")
    
    # 1. Tenta validar a licença completa
    if os.path.exists(license_file):
        try:
            with open(license_file, 'r') as f:
                stored_key = f.read().strip()
            
            license_secret = get_license_secret()
            if not license_secret:
                app.logger.error("FALHA CRÍTICA: Arquivo 'license_secret.bin' não encontrado. Não é possível validar a licença.")
                return 'INVALID', 0, default_modules

            fernet_obj = Fernet(license_secret)
            decrypted_data = fernet_obj.decrypt(stored_key.encode()).decode()
            
            parts = decrypted_data.split('|')
            licensed_id = parts[0]
            
            if licensed_id == current_machine_id:
                # NOVA LÓGICA: Licença Anual (SaaS)
                days_left = 36500 # Padrão para licenças vitalícias (formato antigo) -> ~100 anos
                
                # Verifica se a licença tem data de expiração (formato novo)
                if len(parts) > 1 and '-' in parts[1]:
                    try:
                        expiration_date_str = parts[1] # Espera o formato YYYY-MM-DD
                        expiration_date = datetime.strptime(expiration_date_str, '%Y-%m-%d')
                        # Adiciona um dia para incluir o dia da expiração
                        days_left = (expiration_date.date() - datetime.now().date()).days + 1

                        # CORREÇÃO: Se for 0 ou menos dias, a licença expirou.
                        if days_left <= 0:
                            return 'EXPIRED', 0, default_modules
                    except (ValueError, IndexError):
                        # Se a data estiver mal formatada, a chave é inválida. Não prossegue para o Trial.
                        return 'INVALID', 0, default_modules
                
                # NOVA LÓGICA: Help Desk e Almoxarifado são padrão. Apenas IoT é verificado.
                modules = {'iot': False, 'helpdesk': True, 'storeroom': True}
                # Itera sobre as partes da licença para encontrar o módulo IoT
                for part in parts[2:]: # Começa do índice 2 para pular MAC e DATA
                    if 'IOT=TRUE' in part: modules['iot'] = True

                # Licenças emitidas pelo servidor podem ser revogadas no painel.
                if 'ONLINE=TRUE' in parts[2:]:
                    if not has_recent_online_validation(current_machine_id, stored_key):
                        try:
                            validation_data = json.dumps({'machine_id': current_machine_id}).encode('utf-8')
                            validation_request = urllib.request.Request(
                                'https://acervo-licencas-server.onrender.com/api/validar',
                                data=validation_data,
                                headers={'Content-Type': 'application/json'}
                            )
                            with urllib.request.urlopen(validation_request, timeout=8) as response:
                                validation_result = json.loads(response.read().decode('utf-8'))
                            if not validation_result.get('valida', False):
                                app.logger.warning('Licença online revogada pelo servidor.')
                                return 'INVALID', 0, default_modules
                            save_license_online_validation(current_machine_id, stored_key)
                        except Exception as validation_error:
                            app.logger.error(f'Falha na validação online sem cache válido: {validation_error}')
                            return 'INVALID', 0, default_modules

                # LÓGICA HÍBRIDA: Se a licença não tem IoT, mas o trial ainda está ativo, libera o IoT temporariamente.
                if not modules['iot']:
                    trial_file_check = os.path.join(basedir, '.sys_init')
                    if os.path.exists(trial_file_check):
                        try:
                            with open(trial_file_check, 'r') as f:
                                start_timestamp = float(f.read().strip())
                            start_date = datetime.fromtimestamp(start_timestamp)
                            days_passed = (datetime.now() - start_date).days
                            trial_days_left = 7 - days_passed
                            if trial_days_left >= 1:
                                modules['iot'] = True # Libera o IoT pelo período restante do trial
                                # Adiciona um marcador para a interface saber que é um trial
                                modules['iot_trial_active'] = True
                        except (IOError, ValueError):
                            pass # Se o arquivo de trial estiver corrompido, ignora.

                result = ('VALID', days_left, modules)
                _license_cache = {'time': time.time(), 'data': result}
                app.logger.info("Licença validada com SUCESSO.")
                return result
        except InvalidToken:
            app.logger.error(f"FALHA NA VALIDAÇÃO DA LICENÇA: Chave inválida ou corrompida (InvalidToken).")
            return 'INVALID', 0, default_modules # Se a chave não pode ser descriptografada, é inválida.
        except Exception as e: # Captura outros erros (ex: arquivo mal formatado)
            print("\n\n--- ERRO NA VALIDAÇÃO DA LICENÇA ---")
            traceback.print_exc()
            print("-------------------------------------\n\n")
            app.logger.error(f"FALHA NA VALIDAÇÃO DA LICENÇA: {e}\n{traceback.format_exc()}")
            return 'INVALID', 0, default_modules # Se a chave não pode ser descriptografada, é inválida.

    # 2. Se a licença falhou, verifica o Trial
    # LÓGICA DE TRIAL APRIMORADA: Uma vez que o Trial é iniciado, ele não pode ser resetado.
    first_run_file = os.path.join(basedir, '.sys_first_run')
    trial_file = os.path.join(basedir, '.sys_init')

    if not os.path.exists(trial_file):
        # Se o arquivo de início do Trial não existe, verifica se já houve uma primeira execução.
        if os.path.exists(first_run_file):
            # Se já houve, significa que o Trial foi usado e os arquivos foram apagados. Força a expiração.
            return 'EXPIRED', 0, default_modules
        
        # Se nenhum dos dois existe, é a primeira vez que o sistema roda. Inicia o Trial.
        with open(trial_file, 'w') as f:
            f.write(str(datetime.now().timestamp()))
        result = ('TRIAL', 7, default_modules)
        _license_cache = {'time': time.time(), 'data': result}
        return result
    
    try:
        with open(trial_file, 'r') as f:
            start_timestamp = float(f.read().strip())
        start_date = datetime.fromtimestamp(start_timestamp)
        days_passed = (datetime.now() - start_date).days
        days_left = 7 - days_passed
        
        # CORREÇÃO: O período de trial termina quando os dias restantes são 0 ou menos.
        if days_left >= 1:
            result = ('TRIAL', days_left, default_modules)
            # Cria o arquivo de "primeira execução" na primeira vez que o Trial é validado.
            if not os.path.exists(first_run_file):
                with open(first_run_file, 'w') as f: f.write('activated')
        else:
            result = ('EXPIRED', 0, default_modules)
            
        _license_cache = {'time': time.time(), 'data': result}
        return result
        
    except (IOError, ValueError):
        return 'EXPIRED', 0, default_modules

# --- MONITORAMENTO DE DESEMPENHO ---
@app.before_request
def start_request_timer():
    g.request_started_at = time.perf_counter()

# --- BLOQUEADOR DE CACHE PARA O TABLET ---
@app.after_request
def add_header(response):
    started_at = getattr(g, 'request_started_at', None)
    if started_at is not None:
        elapsed_seconds = time.perf_counter() - started_at
        if elapsed_seconds >= SLOW_REQUEST_SECONDS:
            app.logger.warning(
                'REQUISIÇÃO LENTA: %.3fs | %s %s | status=%s | ip=%s',
                elapsed_seconds,
                request.method,
                request.path,
                response.status_code,
                request.remote_addr
            )

    if 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response

# --- CACHE BUSTER AUTOMÁTICO (Força todos os aparelhos a terem a mesma tela) ---
@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path, endpoint, filename)
            try:
                values['q'] = int(os.stat(file_path).st_mtime)
            except OSError:
                pass
    from flask import url_for as flask_url_for
    return flask_url_for(endpoint, **values)

@app.before_request
def check_license_access():
    license_check_started_at = time.perf_counter()
    status, days, modules = get_license_info()
    license_check_elapsed = time.perf_counter() - license_check_started_at
    if license_check_elapsed >= SLOW_REQUEST_SECONDS:
        app.logger.warning(
            'VALIDAÇÃO DE LICENÇA LENTA: %.3fs | %s %s | status=%s',
            license_check_elapsed,
            request.method,
            request.path,
            status
        )
    
    g.license_status = status
    g.days_left = days
    g.modules = modules # Armazena os módulos disponíveis para esta requisição

    # Mantém as rotas de recuperação disponíveis quando a licença expirou.
    allowed_endpoints = {
        'ativacao', 'ativacao_online', 'static', 'favicon',
        'auth.login', 'auth.logout'
    }
    if request.endpoint in allowed_endpoints or request.path == '/ativacao':
        return
    
    # CORREÇÃO CRÍTICA: Garante que a sessão do usuário reflita o estado ATUAL da licença.
    # Se a licença mudou (ex: foi removida), a sessão é atualizada para corresponder.
    if 'user_id' in session and session.get('modules') != modules:
        session['modules'] = modules

    # Nunca redireciona a própria tela de ativação, evitando ciclos de redirect.
    if status in ['EXPIRED', 'INVALID'] and request.path != '/ativacao':
        return redirect(url_for('ativacao'))

# A rota '/bloqueado' foi removida por ser redundante.

def limpar_reservas_expiradas():
    """Cancela automaticamente reservas com mais de 30 minutos de atraso (No-show)"""
    agora = datetime.now()
    hoje_str = agora.strftime('%Y-%m-%d')
    limite_str = (agora - timedelta(minutes=30)).strftime('%H:%M')
    
    expirados = Agendamento.query.filter(
        Agendamento.status == 'Agendado',
        or_(
            Agendamento.data_uso < hoje_str,
            and_( # Agendamentos de hoje que estão atrasados
                Agendamento.data_uso == hoje_str, 
                Agendamento.horario_retirada < limite_str # Comparar horario_retirada como string
            )
        )
    ).all()
    
    if not expirados:
        return 0

    for exp in expirados:
        exp.status = 'Cancelado'
        exp.finalidade = (exp.finalidade or '') + ' (Cancelado Automático: Tempo Limite)'
        if exp.itens_reservados:
            ids = [x.strip() for x in str(exp.itens_reservados).split(',') if x.strip()]
            if ids:
                Notebook.query.filter(Notebook.status == 'Reservado', Notebook.id.in_(ids)).update({'status': 'Disponível'}, synchronize_session=False)
    try:
        db.session.commit()
        return len(expirados)
    except Exception:
        db.session.rollback()
        app.logger.exception('Falha ao cancelar reservas expiradas.')
        return 0

@app.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    limpar_reservas_expiradas() # Executa a limpeza automática

    # --- CONSULTAS MODERNIZADAS COM SQLAlchemy ---
    total = db.session.query(func.count(Notebook.id)).filter(Notebook.status != 'Inativo').scalar()
    disponiveis = db.session.query(func.count(Notebook.id)).filter(Notebook.status == 'Disponível').scalar()
    manutencao = db.session.query(func.count(Notebook.id)).filter(Notebook.status == 'Em manutenção').scalar()
    por_tipo = db.session.query(Notebook.tipo, func.count(Notebook.tipo).label('qtd')).filter(Notebook.status != 'Inativo').group_by(Notebook.tipo).all()
    
    data_limite = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    movimentacoes_query = db.session.query(
        func.strftime('%Y-%m-%d', Historico.data).label('dia'),
        Historico.acao,
        func.count().label('total')
    ).filter(
        Historico.data >= data_limite,
        Historico.acao.in_(['Saída/Empréstimo', 'Devolução'])
    ).group_by('dia', 'acao').order_by('dia').all()
    # Transforma o resultado em dicionário para o Chart.js
    movimentacoes = [row._asdict() for row in movimentacoes_query]

    # --- OTIMIZAÇÃO DE PERFORMANCE DO DASHBOARD ---
    # Subquery para encontrar o ID da última sessão de uso para cada notebook 'Em uso'
    subquery_last_session = db.session.query(
        Historico.id_etiqueta, # CORREÇÃO: Adiciona id_etiqueta à seleção da subquery
        func.max(SessaoUso.id).label('last_sessao_id') # CORREÇÃO: Nome da coluna estava 'last_session_id'
    ).join(SessaoUso, Historico.data == SessaoUso.data_inicio).join(Notebook, Notebook.id == Historico.id_etiqueta).filter(
        Notebook.status == 'Em uso',
        Historico.acao == 'Saída/Empréstimo'
    ).group_by(Historico.id_etiqueta).subquery()

    # CORREÇÃO DEFINITIVA: Lê as colunas de data como texto para evitar erro de conversão
    # se houver dados corrompidos no banco de dados.
    from sqlalchemy import cast, Text
    em_uso_agora = db.session.query(
        Notebook.id, Notebook.tipo, Notebook.modelo, Notebook.localizacao,
        cast(SessaoUso.data_inicio, Text).label('data_inicio_raw'), 
        cast(SessaoUso.previsao_devolucao, Text).label('previsao_devolucao_raw'), 
        SessaoUso.professor
    ).join(
        subquery_last_session,
        Notebook.id == subquery_last_session.c.id_etiqueta
    ).join(
        SessaoUso,
        SessaoUso.id == subquery_last_session.c.last_sessao_id # Usa o nome correto da coluna da subquery
    ).filter(Notebook.status == 'Em uso').all()

    lista_em_uso = []
    agora = datetime.now()
    for item in em_uso_agora:
        item_dict = item._asdict()
        item_dict['alerta_atraso'] = False
        item_dict['tempo_decorrido'] = "Recente"
        
        data_inicio_obj = None
        if item.data_inicio_raw:
            try:
                data_inicio_obj = datetime.fromisoformat(item.data_inicio_raw)
                diff = agora - data_inicio_obj
                horas_totais = diff.total_seconds() / 3600

                if item.previsao_devolucao_raw:
                    try:
                        previsao_obj = datetime.fromisoformat(item.previsao_devolucao_raw)
                        if agora > previsao_obj: item_dict['alerta_atraso'] = True
                    except Exception: pass
                elif horas_totais > 5: # Fallback: Se não botaram previsão, avisa depois de 5 horas
                    item_dict['alerta_atraso'] = True
                
                if horas_totais < 1:
                    item_dict['tempo_decorrido'] = f"{int(diff.total_seconds() / 60)} min"
                else:
                    item_dict['tempo_decorrido'] = f"{int(horas_totais)}h"
            except (ValueError, TypeError): pass # Ignora se a data estiver corrompida
                
        lista_em_uso.append(item_dict)

    # CORRECAO: Conta baseado na lista real processada para evitar divergência
    em_uso = len(lista_em_uso)

    # Busca agendamentos de HOJE
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    agendamentos_hoje = Agendamento.query.filter_by(data_uso=hoje_str, status='Agendado').order_by(Agendamento.horario_retirada.asc()).all()

    # --- VISUALIZACAO DE ITENS (Cronograma) ---
    # Busca apenas os que ainda estão pendentes (Agendado). Se já foi 'Realizado' (saiu para uso), some da agenda.
    todos_agendamentos = Agendamento.query.filter_by(status='Agendado').order_by(
        Agendamento.data_uso.asc(), Agendamento.horario_retirada.asc()
    ).all()
    
    raw_agendamentos = []
    for row in todos_agendamentos:
        # CORREÇÃO: Acessa o atributo do objeto, não uma chave de dicionário.
        # Compara a data como string ISO YYYY-MM-DD.
        if row.data_uso and row.data_uso >= hoje_str:
            raw_agendamentos.append(row) # row é um objeto Agendamento
        else:
            # Opcional: Mostra no console o que foi ignorado (passado)
            pass

    agenda_map = {} # CORREÇÃO: Define agenda_map antes do loop
    for row in raw_agendamentos:
        d = row.data_uso
        if d not in agenda_map: agenda_map[d] = [] # d é a data_uso (string)
        
        horario = f"{row.horario_retirada or '?'}h" # CORREÇÃO: Acessa atributo
        prof_nome = row.solicitante.split()[0] if row.solicitante else '?' # CORREÇÃO: Acessa atributo

        # Verifica se tem itens reservados e se não é uma string vazia ou 'None'
        tem_itens = row.itens_reservados and str(row.itens_reservados).strip() # CORREÇÃO: Acessa atributo
        
        if tem_itens:
            itens = [x.strip() for x in str(row.itens_reservados).split(',') if x.strip()] # CORREÇÃO: Acessa atributo
            itens_str = ", ".join(itens)
            agenda_map[d].append({'id': itens_str, 'prof': prof_nome, 'hora': horario, 'agendamento_id': row.id, 'codigo': row.codigo_reserva or ''}) # CORREÇÃO: Acessa atributos
        else:
            # Fallback: Se não houver itens específicos, cria itens genéricos baseados na quantidade
            qtd = row.quantidade if row.quantidade else 1 # CORREÇÃO: Acessa atributo
            itens_str = f"{qtd} Item(s)"
            agenda_map[d].append({'id': itens_str, 'prof': prof_nome, 'hora': horario, 'agendamento_id': row.id, 'codigo': row.codigo_reserva or ''}) # CORREÇÃO: Acessa atributos
            
    previsao_agenda = []
    dias_semana = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']
    
    for d in sorted(agenda_map.keys())[:14]:
        try:
            dt_obj = datetime.strptime(d, '%Y-%m-%d')
            dia_sem = dias_semana[dt_obj.weekday()]
            data_fmt = dt_obj.strftime('%d/%m')
        except ValueError:
            data_fmt = d
            dia_sem = '-'

        previsao_agenda.append({
            'data': data_fmt, 
            'dia_sem': dia_sem, 
            'itens': agenda_map[d]
        })

    # --- INTEGRAÇÃO ENTERPRISE: INDICADORES DO ALMOXARIFADO NO DASHBOARD PRINCIPAL ---
    almox_kpis = None
    if session.get('perm_almoxarifado'):
        try: # Adicionado try-except para robustez
            total_itens = db.session.query(func.sum(AlmoxProduto.quantidade_atual)).scalar() or 0
            baixo_estoque = db.session.query(func.count(AlmoxProduto.id)).filter(AlmoxProduto.quantidade_atual <= AlmoxProduto.estoque_minimo).scalar() or 0
            
            # Busca os detalhes exatos de quais peças estão acabando
            itens_alerta = AlmoxProduto.query.filter(AlmoxProduto.quantidade_atual <= AlmoxProduto.estoque_minimo).order_by(AlmoxProduto.quantidade_atual.asc()).limit(5).all()
            
            almox_kpis = {
                'total': total_itens, 
                'alertas': baixo_estoque,
                'itens_alerta': [item.__dict__ for item in itens_alerta]
            }
        except Exception as e:
            app.logger.error(f"Erro ao buscar KPIs do Almoxarifado no Dashboard: {e}")

    return render_template('dashboard.html', 
                           total=total, 
                           disponiveis=disponiveis, 
                           em_uso=em_uso, 
                           manutencao=manutencao, 
                           por_tipo=por_tipo, 
                           movimentacoes=movimentacoes, 
                           em_uso_agora=lista_em_uso, 
                           agendamentos_hoje=agendamentos_hoje, 
                           previsao_agenda=previsao_agenda,
                           almox_kpis=almox_kpis)

@app.route('/kiosk')
@login_required
def kiosk_home():
    # CORREÇÃO DE SEGURANÇA: Verifica se o módulo IoT está licenciado antes de permitir o acesso.
    # A permissão do usuário não é suficiente se o módulo não foi adquirido.
    if not g.modules.get('iot', False):
        flash('Módulo Kiosk/IoT não licenciado. Contate o suporte para ativar.', 'error')
        return redirect(url_for('dashboard'))
    return render_template('kiosk.html')

@app.route('/favicon.ico')
def favicon():
    return "", 204

@app.route('/api/gerar_qr/<string:texto>')
def gerar_qr(texto):
    import qrcode
    import io
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H, # Alta tolerância para leitura em telas de celular com brilho baixo ou trincadas
        box_size=8,
        border=2,
    )
    qr.add_data(texto.upper())
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to buffer
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')

@app.route('/api/verificar_ativo/<path:asset_id>')
@login_required
def api_verificar_ativo(asset_id):
    asset_id = asset_id.strip().upper()
    if 'ATIVO' in asset_id or 'NOTEBOOK' in asset_id: # Mantém compatibilidade com QR antigo
        asset_id = asset_id.replace(';', '/').replace('\\', '/').replace('Ç', ':')
        asset_id = asset_id.split('/')[-1]

    if asset_id.isdigit():
        asset_id = asset_id.zfill(5)
    asset = db.session.get(Notebook, asset_id) # MODERNIZADO
    if asset:
        return {"exists": True, "status": asset.status, "modelo": asset.modelo, "id_limpo": asset_id}
    return {"exists": False}

# --- API PARA O GRID DE AGENDAMENTO ---
@app.route('/api/disponibilidade')
@login_required
def api_disponibilidade():
    data_uso = request.args.get('data') # YYYY-MM-DD
    # Recebe horários solicitados (defaults para garantir funcionamento)
    req_inicio = request.args.get('hora_inicio', '07:00')
    req_fim = request.args.get('hora_fim', '12:30')
    
    if not data_uso:
        return {'items': []}
        
    limpar_reservas_expiradas() # Executa a limpeza antes de mostrar os itens na tela

    try:
        # OTIMIZAÇÃO E CORREÇÃO: Busca apenas as colunas necessárias, evitando o erro de conversão
        # da coluna 'data_compra' que é uma string e estava quebrando a API.
        notebooks = db.session.query(Notebook).with_entities(
            Notebook.id, Notebook.numero_carrinho, Notebook.modelo, Notebook.tipo, Notebook.status
        ).filter(Notebook.status != 'Inativo').order_by(Notebook.numero_carrinho, Notebook.id).all()

        # Busca todos agendamentos do dia
        agendamentos = Agendamento.query.filter_by(data_uso=data_uso, status='Agendado').all()
        
        # Inteligência: Busca a previsão de devolução dos equipamentos que estão fisicamente fora (Em uso)
        # A saída e seus itens são gravados em linhas separadas. Como os
        # timestamps podem diferir por microssegundos, não usamos igualdade
        # exata para relacionar a sessão ao histórico.
        historicos_ativos = db.session.query(Historico).join(
            Notebook, Notebook.id == Historico.id_etiqueta
        ).filter(
            Notebook.status == 'Em uso', Historico.acao == 'Saída/Empréstimo'
        ).all()
        sessoes_com_previsao = SessaoUso.query.filter(
            SessaoUso.previsao_devolucao != None
        ).all()
        previsao_em_uso = {}
        for historico in historicos_ativos:
            data_historico = parse_datetime_value(historico.data)
            sessoes_proximas = [
                sessao for sessao in sessoes_com_previsao
                if data_historico and parse_datetime_value(sessao.data_inicio)
                and 0 <= (data_historico - parse_datetime_value(sessao.data_inicio)).total_seconds() <= 10
            ]
            if sessoes_proximas:
                sessao = min(
                    sessoes_proximas,
                    key=lambda item: abs(
                        (data_historico - parse_datetime_value(item.data_inicio)).total_seconds()
                    )
                )
                previsao = parse_datetime_value(sessao.previsao_devolucao)
                if previsao:
                    previsao_em_uso[historico.id_etiqueta] = previsao

        blocked_ids = []
        
        def t2m(t_str):
            try:
                h, m = map(int, t_str.split(':'))
                return h * 60 + m
            except:
                return 0
                
        req_in_m = t2m(req_inicio)
        req_fi_m = t2m(req_fim)
        
        for ag in agendamentos:
            if ag.itens_reservados:
                ag_inicio = ag.horario_retirada or '07:00'
                ag_fim = ag.horario_devolucao or '18:00' # Se não tiver devolução, assume dia todo
                
                ag_in_m = t2m(ag_inicio)
                ag_fi_m = t2m(ag_fim)
                
                # Inteligência de Tolerância: Permite uma sobreposição de até 10 minutos entre agendamentos
                # Isso garante que se um termina 12:00, o outro pode começar 11:50 e o equipamento aparecerá livre.
                if req_in_m < (ag_fi_m - 10) and req_fi_m > (ag_in_m + 10):
                    blocked_ids.extend([x.strip() for x in str(ag.itens_reservados).split(',') if x.strip()])

        resultado = []
        hoje_str = datetime.now().strftime('%Y-%m-%d')
        
        for nb in notebooks:
            status_visual = 'livre'
            if nb.id in blocked_ids:
                status_visual = 'reservado'
            elif nb.status == 'Em manutenção':
                status_visual = 'manutencao'
            elif nb.status == 'Em uso':
                prev_devolucao = previsao_em_uso.get(nb.id)
                # Um item em uso só fica indisponível até a previsão de devolução.
                # Sem previsão, permanece bloqueado por segurança.
                if not prev_devolucao or not is_available_after_return(
                    data_uso, req_inicio, prev_devolucao
                ):
                    status_visual = 'reservado'
                
            resultado.append({
                'id': nb.id,
                'carrinho': nb.numero_carrinho if nb.numero_carrinho else '?',
                'modelo': nb.modelo,
                'tipo': nb.tipo,
                'status_visual': status_visual
            })
            
        return {'items': resultado}
    except Exception as e:
        app.logger.error(f"ERRO API AGENDAMENTO: {e}")
        return {'items': []}

@app.route('/api/verificar_agendamento_item/<path:item_id>')
@login_required
def api_verificar_agendamento_item(item_id):
    item_id = item_id.strip().upper()
    if 'ATIVO' in item_id or 'NOTEBOOK' in item_id: # Mantém compatibilidade com QR antigo
        item_id = item_id.replace(';', '/').replace('\\', '/').replace('Ç', ':')
        item_id = item_id.split('/')[-1]

    if item_id.isdigit():
        item_id = item_id.zfill(5)
    hoje_str = datetime.now().strftime('%Y-%m-%d')
    hora_atual_str = datetime.now().strftime('%H:%M')

    conflito = Agendamento.query.filter(
        Agendamento.data_uso == hoje_str,
        Agendamento.status == 'Agendado',
        Agendamento.horario_retirada <= hora_atual_str,
        Agendamento.horario_devolucao > hora_atual_str,
        Agendamento.itens_reservados.like(f'%,{item_id},%')
    ).first()

    if conflito:
        return {"reservado": True, "responsavel": conflito.solicitante, "id_limpo": item_id}
    return {"reservado": False, "id_limpo": item_id}

@app.route('/api/reserva/<string:codigo>')
@login_required
def api_reserva(codigo):
    agendamento = Agendamento.query.filter(
        Agendamento.codigo_reserva == codigo.upper(),
        Agendamento.status.in_(['Agendado', 'Realizado'])
    ).first()
    if agendamento:
        return { # agendamento é um objeto Agendamento, não um dicionário
            "found": True,
            "status": agendamento.status,
            "solicitante": agendamento.solicitante,
            "finalidade": agendamento.finalidade,
            "data_uso": agendamento.data_uso,
            "horario_devolucao": agendamento.horario_devolucao,
            "itens": [x.strip() for x in str(agendamento.itens_reservados).split(',') if x.strip() and x.strip() != 'None'] if agendamento.itens_reservados else [],
            "id": agendamento.id
        }
    return {"found": False}

@app.route('/api/reserva_by_id/<int:id>')
@login_required
def api_reserva_by_id(id):
    agendamento = db.session.get(Agendamento, id) # MODERNIZADO
    if agendamento:
        return { # agendamento é um objeto Agendamento, não um dicionário
            "found": True,
            "solicitante": agendamento.solicitante,
            "finalidade": agendamento.finalidade,
            "data_uso": agendamento.data_uso,
            "horario_devolucao": agendamento.horario_devolucao,
            "itens": [x.strip() for x in str(agendamento.itens_reservados).split(',') if x.strip() and x.strip() != 'None'] if agendamento.itens_reservados else [],
            "id": agendamento.id,
            "codigo": agendamento.codigo_reserva
        }
    return {"found": False}

@app.route('/agendamento', methods=['GET', 'POST'])
@login_required
def agendamento():
    modo = request.args.get('modo', 'reserva')
    
    if request.method == 'POST':
        modo_post = request.form.get('modo', 'reserva')
        itens = request.form.get('itens_selecionados', '')
        is_kiosk = request.form.get('kiosk') or request.args.get('kiosk')
        
        from movements import extrair_ids_limpos
        itens_validos = extrair_ids_limpos(itens)
        
        if not itens_validos:
            flash('Erro: Selecione pelo menos um equipamento no mapa antes de confirmar.', 'error')
            return redirect(url_for('agendamento', kiosk=is_kiosk, modo=modo_post))
            
        itens_formatados = ', '.join(itens_validos) # CORREÇÃO: Define itens_formatados aqui para ser sempre acessível
        registrado_por = session.get('username', 'Sistema')
        
        if session.get('perm_config') == 1:
            solicitante = request.form.get('solicitante', '').strip().upper()
        else:
            solicitante = session.get('username', '').upper()
            
        finalidade = request.form.get('finalidade', '').strip()

        if modo_post == 'express':
            # --- FLUXO DE SAÍDA RÁPIDA IMEDIATA ---
            data_dev = request.form.get('data_devolucao', '')
            hora_dev = request.form.get('horario_devolucao', '')
            previsao_devolucao = datetime.strptime(f"{data_dev} {hora_dev}", '%Y-%m-%d %H:%M') if data_dev and hora_dev else None
            
            nova_sessao = SessaoUso( # data_inicio é datetime
                turma=finalidade, professor=solicitante, programa='Saída Rápida', data_inicio=datetime.now(),
                quantidade_notebooks=len(itens_validos), observacoes="Saída expressa", 
                previsao_devolucao=previsao_devolucao,
                usuario_movimentacao=registrado_por
            )
            db.session.add(nova_sessao)
            
            for notebook_id in itens_validos:
                Notebook.query.filter_by(id=notebook_id).update({'status': 'Em uso', 'localizacao': finalidade}) # Atualiza diretamente
                novo_historico = Historico(id_etiqueta=notebook_id, acao='Saída/Empréstimo', usuario_movimentacao=registrado_por, responsavel=solicitante, data=datetime.now(), obs=f"Destino: {finalidade} - Saída Rápida")
                db.session.add(novo_historico)
            db.session.commit()
            trigger_iot_relay(force_open=getattr(g, 'modules', {}).get('iot', False))
            if is_kiosk:
                    # Recuperar posições dos itens
                    nbs = Notebook.query.filter(Notebook.id.in_(itens_validos)).all()
                    slots = []
                    for nb in nbs:
                        if nb.numero_carrinho is not None:
                            slots.append(str(nb.numero_carrinho))
                    slots = sorted(list(set(slots)), key=lambda x: int(x) if str(x).isdigit() else 999)
                    slots_str = ", ".join(slots) if slots else "Qualquer"
                    
                    return redirect(url_for('kiosk_home', kiosk_success='saida', usuario=solicitante, slots=slots_str))
            else:
                itens_formatados = ', '.join(itens_validos)
                iot_enabled = getattr(g, 'modules', {}).get('iot', False)
                if iot_enabled:
                    flash(f'Retirada Liberada com Sucesso! 🔓<br><div style="background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px; margin: 15px 0;"><span style="color: #94a3b8; font-size: 0.9em;">A porta foi destravada. Pode retirar:</span><br><b style="color: #3b82f6; font-size: 1.1em; word-break: break-word;">{itens_formatados}</b></div>', 'success')
                else:
                    flash(f'Saída registrada com sucesso para <b>{solicitante}</b>!<br>Itens: {itens_formatados}', 'success')
        else:
            # --- FLUXO DE RESERVA TRADICIONAL ---
            data_uso_str = request.form.get('data_uso')
            horario_retirada = request.form.get('horario_retirada')
            
            if data_uso_str and horario_retirada:
                try:
                    agora = datetime.now()
                    dt_agendamento = datetime.strptime(f"{data_uso_str} {horario_retirada}", "%Y-%m-%d %H:%M")
                    if dt_agendamento < agora:
                        flash('<b>Data ou Horário Inválido!</b><br>Não é possível realizar um agendamento com uma data ou horário no passado.', 'error')
                        return redirect(url_for('agendamento', modo=modo_post, kiosk=is_kiosk))
                except Exception:
                    pass

            import random
            codigo_reserva = f"AG{random.randint(1000, 9999)}"
            itens_limpos_str = ','.join(itens_validos)
                
            novo_agendamento = Agendamento(
                solicitante=solicitante, registrado_por=registrado_por, data_uso=request.form.get('data_uso'),
                periodo='Matutino', quantidade=len(itens_validos), finalidade=finalidade,
                itens_reservados=itens_limpos_str, horario_retirada=request.form.get('horario_retirada'), 
                horario_devolucao=request.form.get('horario_devolucao'), 
                codigo_reserva=codigo_reserva
            )
            db.session.add(novo_agendamento)
            
            # Um equipamento ainda em uso mantém seu status físico até a devolução.
            # A API de disponibilidade já considera a reserva futura pelo horário.
            Notebook.query.filter(
                Notebook.id.in_(itens_validos), Notebook.status == 'Disponível'
            ).update({'status': 'Reservado'}, synchronize_session=False)
            
            db.session.commit() # CORREÇÃO: Salva o agendamento e a atualização de status no banco de dados.
            
            flash(f'Agendamento confirmado para <b>{solicitante}</b>!<br><div style="background: rgba(0,0,0,0.2); padding: 10px; border-radius: 8px; margin: 15px 0;"><span style="color: #94a3b8; font-size: 0.9em;">Equipamentos reservados:</span><br><b style="color: #10b981; font-size: 1.1em; word-break: break-word;">{itens_formatados}</b></div>Código de Reserva:<br><span style="font-size: 1.8em; color: #10b981; letter-spacing: 2px;"><b>{codigo_reserva}</b></span>', 'success')
            
        if is_kiosk:
            return redirect(url_for('kiosk_home'))
            
        return redirect(url_for('agendamento', modo=modo_post))
            
    hoje = datetime.now().strftime('%Y-%m-%d')
    
    # Busca agendamentos brutos
    raw_agendamentos = Agendamento.query.filter(Agendamento.data_uso >= hoje, Agendamento.status == 'Agendado').order_by(Agendamento.data_uso.asc(), Agendamento.horario_retirada.asc()).all()
    
    # Mapa de Modelos (ID -> Modelo) para consulta rápida
    all_notebooks = Notebook.query.with_entities(Notebook.id, Notebook.modelo).all()
    model_map = {nb.id: nb.modelo for nb in all_notebooks}

    meus_agendamentos = []
    for row in raw_agendamentos:
        if row.itens_reservados:
            ids = [x.strip() for x in str(row.itens_reservados).split(',') if x.strip()]
            # Cria string: "NB01 (Chromebook), NB02 (Tablet)..."
            detalhes = []
            for i in ids:
                m = model_map.get(i, '')
                detalhes.append(f"{i} ({m})" if m else i)
            row.itens_detalhados = ", ".join(detalhes)
        else:
            row.itens_detalhados = f"{row.quantidade} itens (s/ detalhes)"
        meus_agendamentos.append(row)

    return render_template('agendamento.html', agendamentos=meus_agendamentos, username=session.get('username'), hoje=hoje, modo=modo)

@app.route('/imprimir_ticket/<string:codigo>')
@login_required
def imprimir_ticket(codigo):
    ag = Agendamento.query.filter_by(codigo_reserva=codigo.upper()).first()
    
    if not ag:
        flash('Reserva não encontrada.', 'error')
        return redirect(url_for('dashboard'))
        
    itens_str = ag.itens_reservados
    itens_list = [x.strip() for x in str(itens_str).split(',') if x.strip() and x.strip() != 'None'] if itens_str else []
    
    try:
        data_criacao = ag.data_criacao.strftime('%d/%m/%Y %H:%M') if ag.data_criacao else 'N/A'
    except AttributeError:
        data_criacao = 'N/A'
    
    data_uso_fmt = datetime.strptime(ag.data_uso, '%Y-%m-%d').strftime('%d/%m/%Y') if ag.data_uso else 'Imediato'
    hora_ret = ag.horario_retirada if ag.horario_retirada else '--:--'
    
    # Usa um arquivo de template dedicado para facilitar a manutenção
    return render_template('ticket_58mm.html', ag=ag, itens=itens_list, codigo=codigo.upper(), data_criacao=data_criacao, data_uso=data_uso_fmt, hora_uso=hora_ret)


@app.route('/agendamento/cancelar/<int:id>')
@login_required
def cancelar_agendamento(id):
    # Pega os IDs antes de cancelar
    agendamento = db.session.get(Agendamento, id)
    
    if not agendamento:
        flash('Agendamento não encontrado.', 'error')
        return redirect(url_for('dashboard'))

    agendamento.status = 'Cancelado'
    
    # Libera os equipamentos de volta para o Estoque
    if agendamento and agendamento.itens_reservados:
        from movements import extrair_ids_limpos
        ids = extrair_ids_limpos(agendamento.itens_reservados)
        Notebook.query.filter(Notebook.status == 'Reservado', Notebook.id.in_(ids)).update({'status': 'Disponível'}, synchronize_session=False)
            
    db.session.commit()
    flash('Agendamento cancelado e estoque liberado.', 'success')
    if request.referrer and ('agendamento' in request.referrer or 'sessoes' in request.referrer):
        return redirect(request.referrer)
    return redirect(url_for('dashboard'))

@app.route('/agendamentos/historico')
@login_required
def historico_agendamentos():
    if not request.args:
        data_inicio = datetime.now().strftime('%Y-%m-%d')
        data_fim = datetime.now().strftime('%Y-%m-%d')
    else:
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')

    busca = request.args.get('busca', '').strip()
    status_filtro = request.args.get('status', '').strip()
    
    query = Agendamento.query
    
    if data_inicio:
        query = query.filter(Agendamento.data_uso >= data_inicio)
    if data_fim:
        query = query.filter(Agendamento.data_uso <= data_fim)
        
    if status_filtro:
        query = query.filter(Agendamento.status == status_filtro)
        
    if busca:
        busca_like = f'%{busca}%'
        query = query.filter(or_(Agendamento.solicitante.like(busca_like), Agendamento.finalidade.like(busca_like), Agendamento.codigo_reserva.like(busca_like)))
        
    agendamentos_brutos = query.order_by(Agendamento.data_uso.desc(), Agendamento.horario_retirada.desc()).all()
    
    agendamentos = []
    for ag in agendamentos_brutos:
        try: ag.data_fmt = datetime.strptime(ag.data_uso, '%Y-%m-%d').strftime('%d/%m/%Y')
        except: ag.data_fmt = ag.data_uso
        agendamentos.append(ag)
        
    return render_template('historico_agendamentos.html', agendamentos=agendamentos, data_inicio=data_inicio, data_fim=data_fim, filtro_busca=busca, filtro_status=status_filtro)

# --- API IoT (CARRINHO INTELIGENTE) ---
@app.route('/api/iot/validar_reserva/<string:codigo>')
def iot_validar_reserva(codigo):
    agendamento = Agendamento.query.filter(
        Agendamento.codigo_reserva == codigo.upper(),
        Agendamento.status.in_(['Agendado', 'Realizado'])
    ).first()
    
    if not agendamento:
        return {"autorizado": False, "mensagem": "Reserva inválida, cancelada ou já devolvida."}
        
    itens_str = agendamento['itens_reservados']
    if not itens_str:
        return {"autorizado": False, "mensagem": "Reserva sem itens específicos."}
        
    ids_list = [x.strip() for x in itens_str.split(',') if x.strip()]
    
    notebooks = Notebook.query.filter(Notebook.id.in_(ids_list)).all()
    
    slots = []
    for nb in notebooks:
        if nb.numero_carrinho is not None: # nb é um objeto Notebook
            slots.append(str(nb.numero_carrinho)) # nb é um objeto Notebook
    slots = sorted(list(set(slots)), key=lambda x: int(x) if str(x).isdigit() else 999)
    
    # Define se a ação será uma Retirada ou uma Devolução baseada no status atual
    tipo_acao = "saida" if agendamento.status == 'Agendado' else "devolucao"
    
    return {
        "autorizado": True,
        "tipo": tipo_acao,
        "usuario": agendamento.solicitante,
        "agendamento_id": agendamento.id,
        "slots": slots,
        "qtd": len(ids_list)
    }

@app.route('/api/iot/confirmar_saida', methods=['POST'])
@csrf.exempt
def iot_confirmar_saida():
    data = request.get_json()
    if not data or 'agendamento_id' not in data:
        return {"sucesso": False, "mensagem": "Dados inválidos."}, 400
        
    agendamento_id = data['agendamento_id']
    agendamento = Agendamento.query.filter_by(id=agendamento_id, status='Agendado').first()
    
    if not agendamento:
        return {"sucesso": False, "mensagem": "Agendamento não encontrado ou já efetivado."}
        
    turma = agendamento.finalidade
    professor = agendamento.solicitante
    lista_ids_str = agendamento.itens_reservados
    
    from movements import extrair_ids_limpos
    ids_list = extrair_ids_limpos(lista_ids_str)
    # data_inicio é definido por padrão no modelo
    previsao_devolucao = datetime.strptime(f"{agendamento.data_uso} {agendamento.horario_devolucao}", '%Y-%m-%d %H:%M') if agendamento.data_uso and agendamento.horario_devolucao else None
        
    nova_sessao = SessaoUso(
        turma=turma, professor=professor, programa='IoT Carrinho', quantidade_notebooks=len(ids_list), 
        observacoes=f"Saída automatizada via IoT (Reserva #{agendamento_id})", 
        previsao_devolucao=previsao_devolucao, usuario_movimentacao='Automacao_IoT'
    )
    db.session.add(nova_sessao)

    for notebook_id in ids_list:
        Notebook.query.filter_by(id=notebook_id).update({'status': 'Em uso', 'localizacao': turma})
        novo_historico = Historico(id_etiqueta=notebook_id, acao='Saída/Empréstimo', usuario_movimentacao='Automacao_IoT', responsavel=professor, data=datetime.now(), obs=f"Destino: {turma} - Retirada IoT")
        db.session.add(novo_historico)

    agendamento.status = 'Realizado'
    db.session.commit()

    # --- COMANDO IOT: O SERVIDOR CHAMA O ESP32-S3 ---
    trigger_iot_relay(force_open=getattr(g, 'modules', {}).get('iot', False))

    return {"sucesso": True, "mensagem": f"Saída registrada."}

@app.route('/api/iot/confirmar_devolucao', methods=['POST'])
@csrf.exempt
def iot_confirmar_devolucao():
    data = request.get_json()
    if not data or 'agendamento_id' not in data:
        return {"sucesso": False, "mensagem": "Dados inválidos."}, 400
        
    agendamento_id = data['agendamento_id']
    agendamento = Agendamento.query.filter_by(id=agendamento_id, status='Realizado').first()
    
    if not agendamento:
        return {"sucesso": False, "mensagem": "Agendamento não encontrado para devolução."}
        
    from movements import extrair_ids_limpos
    ids_list = extrair_ids_limpos(agendamento.itens_reservados)
        
    # Devolve fisicamente os itens ao estoque
    for notebook_id in ids_list:
        Notebook.query.filter_by(id=notebook_id).update({'status': 'Disponível', 'localizacao': ''})
        novo_historico = Historico(id_etiqueta=notebook_id, acao='Devolução', usuario_movimentacao='Automacao_IoT', responsavel=agendamento.solicitante, data=datetime.now(), obs="Devolução em lote via Carrinho Inteligente (IoT)")
        db.session.add(novo_historico)
        
    # Finaliza a reserva para não ser usada de novo
    agendamento.status = 'Finalizado'
    db.session.commit()

    # --- COMANDO IOT: O SERVIDOR CHAMA O ESP32-S3 ---
    trigger_iot_relay(force_open=getattr(g, 'modules', {}).get('iot', False))

    return {"sucesso": True, "mensagem": f"Devolução registrada."}

@app.route('/api/iot/devolucao_avulsa/<string:asset_id>', methods=['POST'])
@csrf.exempt
def iot_devolucao_avulsa(asset_id):
    notebook = db.session.get(Notebook, asset_id) # MODERNIZADO
    
    if not notebook:
        return {"sucesso": False, "mensagem": "Equipamento não reconhecido no sistema."}
        
    if notebook.status != 'Em uso':
        return {"sucesso": False, "mensagem": f"O equipamento {asset_id} não consta como 'Em uso'. Acesso negado."}

    # Devolve o item unitário
    notebook.status = 'Disponível'
    notebook.localizacao = ''
    novo_historico = Historico(id_etiqueta=asset_id, acao='Devolução', usuario_movimentacao='Automacao_IoT', responsavel='Devolução Expressa', data=datetime.now(), obs="Devolução unitária expressa via Carrinho (IoT)")
    db.session.add(novo_historico)
    db.session.commit()

    # --- COMANDO IOT: O SERVIDOR CHAMA O ESP32-S3 ---
    trigger_iot_relay(force_open=getattr(g, 'modules', {}).get('iot', False))

    return {"sucesso": True, 
            "mensagem": "Porta destravada para devolução.",
            "slot": notebook.numero_carrinho}

@app.route('/api/iot/devolucao_lote', methods=['POST'])
@csrf.exempt
def iot_devolucao_lote():
    data = request.get_json(silent=True)
    if not data or 'ids' not in data:
        return {"sucesso": False, "mensagem": "Dados inválidos."}, 400
        
    ids_list = data['ids']
    
    slots = []
    for asset_id in ids_list:
        notebook = db.session.get(Notebook, asset_id) # MODERNIZADO
        if notebook:
            if notebook.numero_carrinho is not None:
                slots.append(str(notebook.numero_carrinho))
            
            if notebook.status == 'Em uso':
                notebook.status = 'Disponível'
                notebook.localizacao = ''
                novo_historico = Historico(id_etiqueta=asset_id, acao='Devolução', usuario_movimentacao='Automacao_IoT', responsavel='Devolução Expressa', data=datetime.now(), obs="Devolução em lote via Carrinho Inteligente")
                db.session.add(novo_historico)
    
    # Inteligência: Baixa a reserva se todos os itens que faltavam foram devolvidos agora
    agendamentos = Agendamento.query.filter_by(status='Realizado').all()
    for ag in agendamentos:
        if ag.itens_reservados:
            ag_ids = [x.strip() for x in ag.itens_reservados.split(',') if x.strip()]
            disp_count = Notebook.query.filter(Notebook.id.in_(ag_ids), Notebook.status == 'Disponível').count()
            if disp_count == len(ag_ids):
                ag.status = 'Finalizado'
    
    db.session.commit()

    # --- COMANDO IOT: O SERVIDOR CHAMA O ESP32-S3 ---
    trigger_iot_relay(force_open=getattr(g, 'modules', {}).get('iot', False))

    # Organiza e formata a lista de slots para mostrar ao usuário
    slots = sorted(list(set(slots)), key=lambda x: int(x) if str(x).isdigit() else 999)
    slots_str = ", ".join(slots) if slots else "Qualquer"
    
    return {"sucesso": True, "slots": slots_str, "qtd": len(ids_list)}

@app.route('/ativacao', methods=['GET', 'POST'])
def ativacao():
    if request.method == 'POST':
        key_input = request.form.get('license_key', '').strip()
        license_path = os.path.join(basedir, "licenca.key")
        
        # Tenta salvar e validar
        with open(license_path, 'w') as f:
            f.write(key_input)
            
        new_status, _, _ = get_license_info(force_revalidate=True) # CORREÇÃO: Força a revalidação ignorando o cache
        if new_status == 'VALID':
            flash("Sistema ATIVADO com sucesso! Faça login.", "success")
            return redirect(url_for('auth.login'))
        else:
            if os.path.exists(license_path): os.remove(license_path)
            flash("Chave de licença inválida.", "error")

    from utils import gerar_machine_id
    current_machine_id = gerar_machine_id()
    return render_template('ativacao.html', machine_id=current_machine_id)

@app.route('/ativacao/online', methods=['POST'])
def ativacao_online():
    """
    Endpoint que o software cliente chama para se comunicar com o servidor de licenças.
    """
    chave_compra = request.form.get('chave_compra')
    machine_id = request.form.get('machine_id')

    if not chave_compra or not machine_id:
        return jsonify({'sucesso': False, 'mensagem': 'Dados de ativação ausentes.'})

    # --- URL DO SERVIDOR DE LICENÇAS ---
    # Para desenvolvimento local, use a primeira linha.
    # Quando hospedar na nuvem, comente a primeira e descomente a segunda, ajustando a URL para a do Render.
    # LICENSE_SERVER_URL = "http://127.0.0.1:5001/api/ativar" # URL para testes locais (desativada)
    LICENSE_SERVER_URL = "https://acervo-licencas-server.onrender.com/api/ativar" # URL de produção na nuvem (Render)

    try:
        import json
        data = json.dumps({'chave_compra': chave_compra, 'machine_id': machine_id}).encode('utf-8')
        req = urllib.request.Request(LICENSE_SERVER_URL, data=data, headers={'Content-Type': 'application/json'})
        
        with urllib.request.urlopen(req, timeout=10) as response:
            resposta_api = json.loads(response.read().decode())

        if resposta_api.get('sucesso'):
            chave_licenca_recebida = resposta_api.get('chave_licenca')
            license_path = os.path.join(basedir, "licenca.key")
            with open(license_path, 'w') as f:
                f.write(chave_licenca_recebida)
            # CORREÇÃO: Destrói o cache da licença para forçar a revalidação na próxima requisição.
            global _license_cache
            _license_cache = {'time': 0, 'data': None}
            return jsonify({'sucesso': True, 'mensagem': 'Ativação online concluída!'})
        else:
            return jsonify({'sucesso': False, 'mensagem': resposta_api.get('mensagem', 'Falha na comunicação com o servidor.')})
    except Exception as e:
        return jsonify({'sucesso': False, 'mensagem': f'Não foi possível conectar ao servidor de ativação. Verifique sua internet. ({e})'})

# Nova Rota: Redireciona links curtos (sem /scan) para o histórico ou ação correta
@app.route('/ativo/<string:notebook_id>')
def redirect_notebook_root(notebook_id):
    if notebook_id.isdigit():
        notebook_id = notebook_id.zfill(5)
    # Redireciona para a visualização de histórico/detalhes
    return redirect(url_for('inventory.historico', notebook_id=notebook_id))

@app.route('/ativo/<string:notebook_id>/scan')
def scan_notebook(notebook_id):
    if notebook_id.isdigit():
        notebook_id = notebook_id.zfill(5)
    if 'user_id' not in session:
        flash('Por favor, faça login.', 'warning')
        return redirect(url_for('auth.login', next=request.url))
    return redirect(url_for('movements.registrar_devolucao', auto_load=notebook_id))

@app.route('/atalhos_acesso')
@permission_required('perm_config')
def atalhos_acesso():
    import socket
    import qrcode
    import io
    from PIL import Image, ImageDraw, ImageFont
    
    # --- CORREÇÃO: VOLTA A USAR O IP LOCAL DA REDE ---
    # Isso garante que celulares e outros dispositivos na mesma rede possam acessar os links.
    from utils import obter_ip_local
    IP = obter_ip_local() # Sempre tenta obter o IP real da rede
    
    base_url = f"https://{IP}:8080"

    kiosk_url = f"{base_url}{url_for('kiosk_home')}"
    
    # Cria uma folha A4 branca a 300dpi (2480 x 3508 pixels)
    img = Image.new('RGB', (2480, 3508), 'white')
    draw = ImageDraw.Draw(img)
    
    try:
        font_logo = ImageFont.truetype(os.path.join(basedir, "arialbd.ttf"), 110)
        font_title = ImageFont.truetype(os.path.join(basedir, "arialbd.ttf"), 80)
        font_sub = ImageFont.truetype(os.path.join(basedir, "arialbd.ttf"), 45)
        font_card_title = ImageFont.truetype(os.path.join(basedir, "arialbd.ttf"), 90)
        font_card_desc = ImageFont.truetype(os.path.join(basedir, "arialbd.ttf"), 55)
    except IOError:
        font_logo = font_title = font_sub = font_card_title = font_card_desc = ImageFont.load_default()

    # Header Elegante da Folha
    draw.rectangle([0, 0, 2480, 450], fill="#0f172a") # Fundo Escuro no Topo
    draw.text((1240, 180), "ACERVO TI", fill="#ffffff", font=font_logo, anchor="mm")
    draw.text((1240, 300), "PORTAL DE AUTOATENDIMENTO", fill="#3b82f6", font=font_title, anchor="mm")
    draw.text((1240, 390), "Aponte a câmera do celular para o QR Code abaixo para acessar o sistema", fill="#94a3b8", font=font_sub, anchor="mm")
    
    # --- DESENHA UM ÚNICO QR CODE GIGANTE CENTRALIZADO ---
    qr_img = qrcode.make(kiosk_url, box_size=35, border=1).convert('RGB')
    w, h = qr_img.size
    x_center, y_center = 1240, 1950
    
    box_w = 1700
    box_h = 1900
    left = x_center - box_w // 2
    top = y_center - box_h // 2
    right = x_center + box_w // 2
    bottom = y_center + box_h // 2
    
    # Sombra Suave e Caixa
    draw.rectangle([left+20, top+20, right+20, bottom+20], fill="#e2e8f0")
    draw.rectangle([left, top, right, bottom], fill="#ffffff", outline="#cbd5e1", width=8)
    draw.rectangle([left, top, right, top + 220], fill="#3b82f6") 
    
    draw.text((x_center, top + 110), "SISTEMA ACERVO TI", fill="white", font=font_card_title, anchor="mm")
    
    qr_y = top + 220 + (box_h - 220 - h) // 2 - 60
    img.paste(qr_img, (x_center - w//2, qr_y))
    
    draw.text((x_center, bottom - 100), "Agendamentos, Saídas, Devoluções e Chamados", fill="#64748b", font=font_card_desc, anchor="mm")
        
    pdf_io = io.BytesIO()
    img.save(pdf_io, "PDF", resolution=300.0)
    pdf_io.seek(0)
    
    # Retorna o arquivo diretamente na tela (as_attachment=False fará abrir no navegador)
    return send_file(pdf_io, as_attachment=False, download_name='qrs_acesso.pdf', mimetype='application/pdf')

@app.route('/ajuda')
@permission_required('perm_ajuda')
def ajuda():
    return render_template('ajuda.html')

@app.route('/desligar_sistema', methods=['POST'])
@login_required
def desligar_sistema():
    import os
    import threading
    import time
    
    # 1. Limpa a sessão para forçar o pedido de senha quando voltar
    session.clear()
    
    # Aguarda 1 segundo para a página carregar a mensagem e "mata" o processo do servidor
    threading.Thread(target=lambda: (time.sleep(1), os._exit(0)), daemon=True).start()
    
    # 3. Retorna a tela que vai forçar o redirecionamento
    return render_template_string("""
    <html>
    <body style="background:#0f172a;color:white;text-align:center;font-family:sans-serif;padding-top:100px;">
        <h1 style="color:#ef4444;">Sistema Encerrado!</h1>
        <p style="color:#94a3b8;font-size:1.2rem;">A memória do servidor foi limpa.</p>
        <p style="color:#cbd5e1;">O tablet será redirecionado para forçar a limpeza de cache...</p>
        <script>
            // Tenta recarregar a tela inicial após 3 segundos.
            // Como o servidor estará morto, o Chrome vai dar erro de conexão e limpar o cache.
            setTimeout(function() {
                window.location.href = '/';
            }, 3000);
        </script>
    </body>
    </html>
    """)

if __name__ == '__main__':
    try:
        if os.name == 'nt':
            import ctypes
            instance_mutex = ctypes.windll.kernel32.CreateMutexW(
                None, False, 'Global\\AcervoTI-Servidor-8080'
            )
            if ctypes.windll.kernel32.GetLastError() == 183:
                print('O Sistema Acervo TI já está em execução neste computador.')
                sys.exit(0)

        # --- HTTPS SETUP (MODERNIZADO E CORRIGIDO) ---
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import ipaddress
        from utils import obter_ip_local
        meu_ip = obter_ip_local()

        try:
            backup_path = create_database_backup(
                os.path.join(basedir, 'patrimonio_ti.db'),
                os.path.join(basedir, 'backups')
            )
            app.logger.info(f'Backup automático criado: {backup_path}')
        except FileNotFoundError:
            app.logger.warning('Backup automático ignorado: banco ainda não existe.')
        except Exception:
            app.logger.exception('Falha ao criar backup automático na inicialização.')

        cert_file = os.path.join(basedir, 'cert_secure.pem')
        key_file = os.path.join(basedir, 'key_secure.pem')
        ip_file = os.path.join(basedir, 'last_ip.txt')
        last_ip = ""
        if os.path.exists(ip_file):
            with open(ip_file, 'r') as f: last_ip = f.read().strip()

        if not os.path.exists(cert_file) or not os.path.exists(key_file) or last_ip != meu_ip:
            app.logger.info(f"Gerando novo certificado SSL para o IP: {meu_ip}") # Log
            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            with open(key_file, "wb") as f:
                f.write(key.private_bytes(
                    encoding=serialization.Encoding.PEM, format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption()))

            subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, u"Sistema Acervo TI Local")])
            cert_builder = x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(key.public_key()).serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)).not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
            cert_builder = cert_builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(u"localhost"), x509.IPAddress(ipaddress.ip_address(meu_ip)), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
            cert = cert_builder.sign(key, hashes.SHA256()) # Fim do builder

            with open(cert_file, "wb") as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
            with open(ip_file, "wt") as f: f.write(meu_ip)
            
        # NOVIDADE: Abre o navegador automaticamente
        import threading
        import time
        import subprocess
        import platform
        
        def open_browser():
            time.sleep(2)
            url = f"https://127.0.0.1:8080"
            
            # Se for Windows, força o Chrome a abrir num ambiente isolado e com impressão invisível
            if platform.system() == "Windows":
                chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
                chrome_path_x86 = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
                user_dir = r"C:\ChromeTotem"
                args = ["--kiosk-printing", f"--user-data-dir={user_dir}", url]
                
                if os.path.exists(chrome_path): subprocess.Popen([chrome_path] + args)
                elif os.path.exists(chrome_path_x86): subprocess.Popen([chrome_path_x86] + args)
                else:
                    import webbrowser; webbrowser.open(url)
            else:
                import webbrowser; webbrowser.open(url)
                
        threading.Thread(target=open_browser, daemon=True).start()
        
        print("\n" + "="*50)
        print(" SISTEMA INICIADO COM SUCESSO!")
        print(" O navegador abrira automaticamente em instantes.")
        print("="*50 + "\n")
        
        app.run(debug=False, use_reloader=False, threaded=True, host='0.0.0.0', port=8080, ssl_context=(cert_file, key_file))
    except ImportError as e:
        with open("erro_critico.txt", "w") as f: f.write(f"ERRO DE BIBLIOTECA: {e}")
    except Exception as e:
        import traceback
        with open("erro_critico.txt", "w") as f: f.write(f"ERRO FATAL:\n{traceback.format_exc()}")
