from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, jsonify
import os
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime
from urllib.parse import urlparse
from models import db, Usuario
from supabase_session import SupabaseSessionStore

try:
    from supabase_login import sign_in_with_supabase
except Exception:
    sign_in_with_supabase = None

auth_bp = Blueprint('auth', __name__)


class DeviceTenantMismatchError(Exception):
    pass


def _validate_device_tenant(profile):
    device_tenant_id = os.getenv('COLEGIO_ID')
    if device_tenant_id and profile.get('colegio_id') != device_tenant_id:
        raise DeviceTenantMismatchError(
            'Este dispositivo está vinculado a outro cliente e não pode acessar seus dados locais.'
        )


def _permissions_for_role(role):
    permissions = {
        'perm_movimentacao': False,
        'perm_cadastro': False,
        'perm_config': False,
        'perm_kiosk': False,
        'perm_chamados': False,
        'perm_ajuda': True,
        'perm_almoxarifado': False,
    }
    if role == 'admin_geral':
        return {key: True for key in permissions}
    if role == 'gestor_colegio':
        permissions.update({
            'perm_movimentacao': True,
            'perm_cadastro': True,
            'perm_chamados': True,
            'perm_almoxarifado': True,
        })
    elif role == 'tecnico_ti':
        permissions.update({
            'perm_movimentacao': True,
            'perm_cadastro': True,
            'perm_chamados': True,
            'perm_almoxarifado': True,
        })
    return permissions

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            session['next_url'] = request.url
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                session['next_url'] = request.url
                return redirect(url_for('auth.login'))
            if not session.get(permission):
                flash('Acesso negado. Você não tem permissão para realizar esta ação.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@auth_bp.route('/logout')
def logout():
    SupabaseSessionStore().clear()
    session.clear()
    return redirect(url_for('auth.login'))

@auth_bp.route('/login', methods=('GET', 'POST'))
def login():
    # CORREÇÃO DEFINITIVA: Verifica o status da licença ANTES de processar o login.
    # Se estiver expirada, redireciona para a tela de bloqueio imediatamente.
    from app import get_license_info
    status, _, _ = get_license_info() # Não força revalidação aqui, pois o before_request já fará isso.
    if status in ['EXPIRED', 'INVALID']: # CORREÇÃO: Bloqueia também se a licença for INVÁLIDA
        return redirect(url_for('ativacao'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Primeiro tenta autenticar no Supabase quando configurado.
        if sign_in_with_supabase is not None:
            try:
                supabase_result = sign_in_with_supabase(username, password)
                profile = supabase_result['profile']
                if not profile:
                    raise ValueError('Usuário autenticado sem perfil de acesso.')
                _validate_device_tenant(profile)
                if not supabase_result['access_token'] or not supabase_result['refresh_token']:
                    raise ValueError('Sessão de autenticação indisponível.')
                SupabaseSessionStore().save(
                    supabase_result['access_token'],
                    supabase_result['refresh_token'],
                )

                session.clear()
                session.permanent = True
                session['user_id'] = supabase_result['user_id']
                session['username'] = supabase_result['email']
                session['supabase_auth'] = True
                session['colegio_id'] = profile['colegio_id']
                session['papel'] = profile['papel']
                session.update(_permissions_for_role(profile['papel']))
                session['modules'] = getattr(g, 'modules', {})
                flash('Login realizado com autenticação Supabase.', 'success')
                return redirect(url_for('dashboard'))
            except DeviceTenantMismatchError as error:
                flash(str(error), 'error')
                return render_template('login.html')
            except Exception:
                # Se falhar no Supabase, cai para o login local do sistema.
                pass

        user = Usuario.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            user.last_login = datetime.now()
            db.session.commit()

            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            if hasattr(g, 'modules'):
                session['modules'] = g.modules

            session['username'] = user.username
            session['perm_movimentacao'] = user.perm_movimentacao
            session['perm_cadastro'] = user.perm_cadastro
            session['perm_config'] = user.perm_config
            session['perm_kiosk'] = user.perm_kiosk
            session['perm_chamados'] = user.perm_chamados
            session['perm_ajuda'] = user.perm_ajuda
            session['perm_almoxarifado'] = user.perm_almoxarifado

            next_url = session.pop('next_url', None)
            next_path = urlparse(next_url).path if next_url else None
            if next_path == '/kiosk' and not session.get('modules', {}).get('iot', False):
                flash('Módulo Kiosk/IoT não licenciado. Acesso redirecionado para o painel principal.', 'warning')
                return redirect(url_for('dashboard'))
            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha inválidos.', 'error')

    return render_template('login.html')

@auth_bp.route('/api/kiosk_unlock', methods=['POST'])
def kiosk_unlock():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False})
    username = data.get('username')
    password = data.get('password')
    user = Usuario.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        # ATUALIZA O HORÁRIO DO ÚLTIMO LOGIN
        user.last_login = datetime.now()
        db.session.commit()

        session.clear()
        session.permanent = True
        session['user_id'] = user.id
        session['username'] = user.username
        session['perm_movimentacao'] = user.perm_movimentacao
        session['perm_cadastro'] = user.perm_cadastro
        session['perm_config'] = user.perm_config
        session['perm_kiosk'] = user.perm_kiosk
        session['perm_chamados'] = user.perm_chamados
        session['perm_ajuda'] = user.perm_ajuda
        session['perm_almoxarifado'] = user.perm_almoxarifado
        
        return jsonify({"success": True})
    return jsonify({"success": False})

@auth_bp.route('/api/kiosk_exit', methods=['POST'])
def kiosk_exit():
    """Desliga o modo Totem e devolve o PC para o Dashboard se for Admin"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "msg": "Dados vazios"})
    username = data.get('username')
    password = data.get('password')
    user = Usuario.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        if user.perm_config:
            # ATUALIZA O HORÁRIO DO ÚLTIMO LOGIN
            user.last_login = datetime.now()
            db.session.commit()

            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            # CORREÇÃO: Transfere os módulos da licença para a sessão do usuário
            if hasattr(g, 'modules'):
                session['modules'] = g.modules
            session['username'] = user.username
            session['perm_movimentacao'] = user.perm_movimentacao
            session['perm_cadastro'] = user.perm_cadastro
            session['perm_config'] = user.perm_config
            session['perm_kiosk'] = user.perm_kiosk
            session['perm_chamados'] = user.perm_chamados
            session['perm_ajuda'] = user.perm_ajuda
            session['perm_almoxarifado'] = user.perm_almoxarifado
            
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "msg": "Apenas Administradores podem desligar o Totem."})
    return jsonify({"success": False, "msg": "Credenciais inválidas."})

@auth_bp.route('/api/current_user')
def current_user():
    """Informa ao JavaScript quem está usando a tela agora"""
    if 'user_id' in session:
        return jsonify({
            "logged_in": True, 
            "username": session.get('username'), 
            "is_admin": session.get('perm_config') == 1
        })
    return jsonify({"logged_in": False})