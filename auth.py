from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from datetime import datetime
from urllib.parse import urlparse
from models import db, Usuario

auth_bp = Blueprint('auth', __name__)

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
        
        user = Usuario.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            # ATUALIZA O HORÁRIO DO ÚLTIMO LOGIN
            user.last_login = datetime.now()
            db.session.commit()

            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            # CORREÇÃO: Transfere os módulos da licença para a sessão do usuário no login
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