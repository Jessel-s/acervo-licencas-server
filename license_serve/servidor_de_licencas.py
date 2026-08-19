from flask import Flask, request, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_basicauth import BasicAuth
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import os
import logging

from models import db, Compra

# Inicializa a extensão de autenticação globalmente
basic_auth = BasicAuth() # BasicAuth pode ser global

def create_app():
    """Cria e configura uma instância da aplicação Flask."""
    app = Flask(__name__)
    
    # Configura o sistema de logs para nos dar mais detalhes no Render.com
    logging.basicConfig(level=logging.INFO)
    app.logger.info("--- INICIANDO DIAGNÓSTICO DO SERVIDOR DE LICENÇAS ---")

    # --- CONFIGURAÇÃO DE SEGURANÇA E BANCO DE DADOS ---
    app.logger.info("1. Configurando SECRET_KEY e DATABASE_URL...")
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'uma-chave-secreta-muito-forte-para-desenvolvimento')
    database_url = os.environ.get('DATABASE_URL')

    if not database_url:
        app.logger.critical("FALHA: A variável de ambiente 'DATABASE_URL' não foi encontrada.")
        raise ValueError("ERRO CRÍTICO: A variável de ambiente 'DATABASE_URL' não foi encontrada.")

    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.logger.info("   OK: Configuração do banco de dados concluída.")

    # --- INICIALIZAÇÃO DAS EXTENSÕES ---
    app.logger.info("2. Inicializando extensões (DB, Admin, Auth)...")
    db.init_app(app)
    # O Admin deve ser inicializado DENTRO da fábrica para evitar conflitos de nome
    admin = Admin(app, name='Painel de Licenças', template_mode='bootstrap4')
    basic_auth.init_app(app)
    app.logger.info("   OK: Extensões inicializadas.")

    # --- PROTEÇÃO DO PAINEL ADMIN ---
    app.logger.info("3. Configurando autenticação do painel de admin...")
    app.config['BASIC_AUTH_USERNAME'] = os.environ.get('ADMIN_USER', 'admin')
    app.config['BASIC_AUTH_PASSWORD'] = os.environ.get('ADMIN_PASS', 'senhaSuperSecreta')
    app.logger.info("   OK: Autenticação configurada.")

    # --- CHAVE DE CRIPTOGRAFIA DA LICENÇA ---
    app.logger.info("4. Configurando chave de criptografia (Fernet)...")
    # A chave padrão DEVE ser uma chave base64 válida de 32 bytes.
    license_secret_key = os.environ.get('LICENSE_SECRET', 'V2FGVzQ1dGdfSGVscERlc2tfU2VjcmV0S2V5XzIwMjQ=').encode()
    fernet = Fernet(license_secret_key)
    app.logger.info("   OK: Chave de criptografia carregada.")

    # --- PAINEL DE ADMINISTRAÇÃO ---
    app.logger.info("5. Criando a view do painel de administração (CompraView)...")
    class CompraView(ModelView):
        def is_accessible(self):
            return basic_auth.check()

        column_list = ['nome_cliente', 'chave_compra', 'inclui_iot', 'ativado', 'machine_id_ativado', 'data_ativacao']
        column_searchable_list = ['nome_cliente', 'chave_compra', 'machine_id_ativado']
        column_filters = ['ativado', 'inclui_iot']
        form_columns = ['nome_cliente', 'email_cliente', 'inclui_iot']
    app.logger.info("   OK: View do admin criada.")

    # Adiciona a view ao admin DENTRO da fábrica
    app.logger.info("6. Adicionando a view ao painel de administração...")
    admin.add_view(CompraView(Compra, db.session))
    app.logger.info("   OK: View adicionada ao admin.")

    # --- ROTAS DA APLICAÇÃO ---
    @app.route('/')
    def index():
        app.logger.info("Acesso à rota principal ('/').")
        return "Servidor de Licenças AcervoTI - Online", 200

    @app.route('/api/ativar', methods=['POST'])
    def ativar():
        data = request.get_json()
        chave_compra = data.get('chave_compra')
        machine_id = data.get('machine_id')

        if not chave_compra or not machine_id:
            return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos.'})

        compra = Compra.query.filter_by(chave_compra=chave_compra).first()

        if not compra:
            return jsonify({'sucesso': False, 'mensagem': 'Chave de Compra inválida ou não encontrada.'})

        if compra.ativado and compra.machine_id_ativado != machine_id:
            return jsonify({'sucesso': False, 'mensagem': 'Esta Chave de Compra já foi utilizada em outra máquina.'})

        compra.ativado = True
        compra.machine_id_ativado = machine_id
        compra.data_ativacao = datetime.now().isoformat()
        db.session.commit()

        validade = (datetime.now() + timedelta(days=366)).strftime('%Y-%m-%d')
        modulos = f"|IOT={'TRUE' if compra.inclui_iot else 'FALSE'}"
        
        dados_licenca = f"{machine_id}|{validade}{modulos}"
        chave_licenca_final = fernet.encrypt(dados_licenca.encode()).decode()

        return jsonify({
            'sucesso': True,
            'mensagem': 'Sistema ativado com sucesso!',
            'chave_licenca': chave_licenca_final
        })

    # --- COMANDOS DE INICIALIZAÇÃO ---
    app.logger.info("7. Sincronizando modelos com o banco de dados (db.create_all)...")
    with app.app_context():
        db.create_all()
    app.logger.info("   OK: Banco de dados sincronizado.")
    app.logger.info("--- DIAGNÓSTICO CONCLUÍDO. APLICAÇÃO PRONTA. ---")

    return app

# Cria a instância da aplicação para o Gunicorn encontrar
app = create_app()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5001)), debug=False)