from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, g
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import pandas as pd
import io
import os
import uuid
import sys
from PIL import Image

from models import db, Usuario, ConfiguracaoSistema, Historico
from auth import login_required, permission_required

settings_bp = Blueprint('settings', __name__)

if getattr(sys, 'frozen', False):
    basedir = os.path.dirname(sys.executable)
else:
    basedir = os.path.abspath(os.path.dirname(__file__))

@settings_bp.route('/configuracoes', methods=['GET', 'POST'])
@permission_required('perm_config')
def configuracoes():
    users = Usuario.query.order_by(Usuario.username.asc()).all()

    # --- NOVO: Obtém IP da máquina e Lê o Log ---
    # CORREÇÃO: Usa a mesma função de ID da tela de ativação para consistência.
    from utils import obter_ip_local
    meu_ip = obter_ip_local()
    url_acesso = f"https://{meu_ip}:8080"

    log_path = os.path.join(basedir, 'sistema_erros.log')
    if os.path.exists(log_path):
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            log_content = "".join(f.readlines()[-100:]) # Pega as últimas 100 linhas para não travar
    else:
        log_content = "Nenhum log de inicialização encontrado ainda."

    # --- NOVO: Busca o IP do Totem ---
    config_iot = db.session.get(ConfiguracaoSistema, 'ip_totem_iot') # MODERNIZADO
    ip_totem = config_iot.valor if config_iot else '192.168.0.50'

    # g.license_status e g.days_left são definidos no before_request do app.py
    return render_template('configuracoes.html', users=users, status=g.license_status, days=g.days_left, url_acesso=url_acesso, log_content=log_content, modules=g.modules, ip_totem=ip_totem)

@settings_bp.route('/configuracoes/salvar_iot', methods=['POST'])
@permission_required('perm_config')
def salvar_iot():
    ip = request.form.get('ip_totem', '').strip()
    if ip:
        config = db.session.get(ConfiguracaoSistema, 'ip_totem_iot') or ConfiguracaoSistema(chave='ip_totem_iot') # MODERNIZADO
        config.valor = ip
        db.session.commit()
        flash('Endereço IP da placa IoT do Totem atualizado com sucesso!', 'success')
    return redirect(url_for('settings.configuracoes'))

@settings_bp.route('/configuracoes/add_user', methods=['GET', 'POST'])
@permission_required('perm_config')
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        perm_movimentacao = 1 if 'perm_movimentacao' in request.form else 0
        perm_cadastro = 1 if 'perm_cadastro' in request.form else 0
        perm_config = 1 if 'perm_config' in request.form else 0
        perm_kiosk = 1 if 'perm_kiosk' in request.form else 0
        perm_chamados = 1 if 'perm_chamados' in request.form else 0
        perm_ajuda = 1 if 'perm_ajuda' in request.form else 0
        perm_almoxarifado = 1 if 'perm_almoxarifado' in request.form else 0

        novo_usuario = Usuario(
            username=username,
            password=generate_password_hash(password),
            perm_movimentacao=bool(perm_movimentacao),
            perm_cadastro=bool(perm_cadastro),
            perm_config=bool(perm_config),
            perm_kiosk=bool(perm_kiosk),
            perm_chamados=bool(perm_chamados),
            perm_ajuda=bool(perm_ajuda),
            perm_almoxarifado=bool(perm_almoxarifado)
        )
        db.session.add(novo_usuario)
        db.session.commit()
        flash(f'Usuário {username} criado!', 'success')
        return redirect(url_for('settings.configuracoes'))
    return render_template('add_user.html')

@settings_bp.route('/configuracoes/edit_user/<int:user_id>', methods=['GET', 'POST'])
@permission_required('perm_config')
def edit_user(user_id):
    user = Usuario.query.get_or_404(user_id)
    if request.method == 'POST':
        password = request.form.get('password')
        perm_movimentacao = 1 if 'perm_movimentacao' in request.form else 0
        perm_cadastro = 1 if 'perm_cadastro' in request.form else 0
        perm_config = 1 if 'perm_config' in request.form else 0
        perm_kiosk = 1 if 'perm_kiosk' in request.form else 0
        perm_chamados = 1 if 'perm_chamados' in request.form else 0
        perm_ajuda = 1 if 'perm_ajuda' in request.form else 0
        perm_almoxarifado = 1 if 'perm_almoxarifado' in request.form else 0
        if password:
            user.password = generate_password_hash(password)
        user.perm_movimentacao = bool(perm_movimentacao)
        user.perm_cadastro = bool(perm_cadastro)
        user.perm_config = bool(perm_config)
        user.perm_kiosk = bool(perm_kiosk)
        user.perm_chamados = bool(perm_chamados)
        user.perm_ajuda = bool(perm_ajuda)
        user.perm_almoxarifado = bool(perm_almoxarifado)
        db.session.commit()
        flash(f'Usuário atualizado!', 'success')
        return redirect(url_for('settings.configuracoes'))
    return render_template('edit_user.html', user=user)

@settings_bp.route('/configuracoes/remove_user/<int:user_id>', methods=['POST'])
@permission_required('perm_config')
def remove_user(user_id):
    if user_id == 1:
        flash('Não é possível remover o usuário administrador principal.', 'error')
        return redirect(url_for('settings.configuracoes'))
    user = db.session.get(Usuario, user_id) # MODERNIZADO
    if user:
        db.session.delete(user)
        db.session.commit()
    flash('Usuário removido.', 'success')
    return redirect(url_for('settings.configuracoes'))

@settings_bp.route('/configuracoes/cleanup_history', methods=['POST'])
@permission_required('perm_config')
def cleanup_history():
    data_limite = datetime.now() - timedelta(days=30)
    delete_q = Historico.__table__.delete().where(Historico.data < data_limite)
    result = db.session.execute(delete_q)
    db.session.commit()
    flash(f'{result.rowcount} registros de histórico com mais de 30 dias foram removidos.', 'success')
    return redirect(url_for('settings.configuracoes'))

@settings_bp.route('/configuracoes/backup')
@permission_required('perm_config')
def backup_db():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_path = os.path.join(basedir, "patrimonio_ti.db")
    return send_file(db_path, as_attachment=True, download_name=f'backup_acervo_{timestamp}.db')

@settings_bp.route('/exportar')
@permission_required('perm_cadastro')
def exportar():
    conn = db.engine
    df_notebooks = pd.read_sql_query("SELECT * FROM notebooks", conn)
    df_sessoes = pd.read_sql_query("SELECT * FROM sessoes_uso ORDER BY data_inicio DESC", conn)
    df_problemas = pd.read_sql_query("SELECT * FROM problemas ORDER BY data_registro DESC", conn)
    df_historico = pd.read_sql_query("SELECT * FROM historico ORDER BY data DESC", conn)

    # --- Módulo Almoxarifado ---
    df_almox_prod = pd.read_sql_query("SELECT * FROM almox_produtos ORDER BY nome ASC", conn)
    df_almox_mov = pd.read_sql_query("SELECT * FROM almox_movimentacoes ORDER BY id DESC", conn)

    # Tradução corporativa: Renomeia as colunas do banco para nomes mais profissionais no Excel
    df_notebooks.rename(columns={'numero_carrinho': 'numero_controle'}, inplace=True)

    df_sessoes.rename(columns={
        'turma': 'setor_destino',
        'professor': 'responsavel',
        'programa': 'finalidade',
        'quantidade_notebooks': 'quantidade_itens',
        'usuario_movimentacao': 'operador_sistema'
    }, inplace=True)

    df_historico.rename(columns={
        'usuario_movimentacao': 'operador_sistema',
        'id_etiqueta': 'ativo_id'
    }, inplace=True)

    # Reorganiza as colunas de Sessões de Uso
    cols_sess = ['id', 'setor_destino', 'responsavel', 'operador_sistema', 'finalidade', 'data_inicio', 'previsao_devolucao', 'quantidade_itens', 'observacoes']
    cols_sess = [c for c in cols_sess if c in df_sessoes.columns]
    df_sessoes = df_sessoes[cols_sess]

    # Reorganiza as colunas do Histórico
    cols_hist = ['id', 'ativo_id', 'acao', 'operador_sistema', 'responsavel', 'data', 'obs']
    cols_hist = [c for c in cols_hist if c in df_historico.columns]
    df_historico = df_historico[cols_hist]

    # Formata todos os cabeçalhos das planilhas para MAIÚSCULAS
    df_notebooks.columns = [str(c).upper() for c in df_notebooks.columns]
    df_sessoes.columns = [str(c).upper() for c in df_sessoes.columns]
    df_problemas.columns = [str(c).upper() for c in df_problemas.columns]
    df_historico.columns = [str(c).upper() for c in df_historico.columns]
    df_almox_prod.columns = [str(c).upper() for c in df_almox_prod.columns]
    df_almox_mov.columns = [str(c).upper() for c in df_almox_mov.columns]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_notebooks.to_excel(writer, sheet_name='Inventario', index=False)
        df_sessoes.to_excel(writer, sheet_name='Movimentacoes_Saida', index=False)
        df_problemas.to_excel(writer, sheet_name='Problemas_e_Manutencao', index=False)
        df_historico.to_excel(writer, sheet_name='Historico_Completo', index=False)
        df_almox_prod.to_excel(writer, sheet_name='Almox_Estoque', index=False)
        df_almox_mov.to_excel(writer, sheet_name='Almox_Mov_Gerais', index=False)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='relatorio_acervo.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@settings_bp.route('/configuracoes/clear_logs', methods=['POST'])
@permission_required('perm_config')
def clear_logs():
    log_path = os.path.join(basedir, 'sistema_erros.log')
    if os.path.exists(log_path):
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("") # Apaga todo o conteúdo do arquivo
        flash('Logs do sistema limpos com sucesso!', 'success')
    return redirect(url_for('settings.configuracoes'))

@settings_bp.route('/configuracoes/upload_logo', methods=['POST'])
@permission_required('perm_config')
def upload_logo():
    if 'logo' not in request.files:
        flash('Nenhum arquivo enviado.', 'error')
        return redirect(url_for('settings.configuracoes'))

    file = request.files['logo']
    if file.filename == '':
        flash('Nenhum arquivo selecionado.', 'error')
        return redirect(url_for('settings.configuracoes'))

    if file and file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        try:
            logo_path = os.path.join(basedir, 'static', 'favicon.png')

            img = Image.open(file)
            img = img.convert("RGBA") # Mantém a transparência se for PNG
            img.save(logo_path, format="PNG")

            flash('Logotipo atualizado com sucesso! (O sistema carregará a nova imagem imediatamente)', 'success')
        except Exception as e:
            flash(f'Erro ao salvar logotipo: {str(e)}', 'error')
    else:
        flash('Formato de imagem inválido. Envie um arquivo .PNG ou .JPG.', 'error')

    return redirect(url_for('settings.configuracoes'))