from flask import Flask, request, jsonify, redirect, url_for
from flask_admin import Admin, AdminIndexView
from flask_admin.contrib.sqla import ModelView
from flask_basicauth import BasicAuth
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import os
import logging
from sqlalchemy import update
from markupsafe import Markup

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
    app.config['SECRET_KEY'] = (
        os.environ.get('FLASK_SECRET_KEY')
        or os.environ.get('SECRET_KEY')
        or os.urandom(32)
    )
    if not os.environ.get('FLASK_SECRET_KEY') and not os.environ.get('SECRET_KEY'):
        app.logger.warning(
            "FLASK_SECRET_KEY/SECRET_KEY não configurada; usando chave temporária para esta execução."
        )
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
    basic_auth.init_app(app)
    app.logger.info("   OK: Extensões inicializadas.")

    # --- PROTEÇÃO DO PAINEL ADMIN ---
    app.logger.info("3. Configurando autenticação do painel de admin...")
    app.config['BASIC_AUTH_USERNAME'] = os.environ.get('ADMIN_USER', 'admin')
    app.config['BASIC_AUTH_PASSWORD'] = os.environ.get('ADMIN_PASS', 'senhaSuperSecreta')
    if not os.environ.get('ADMIN_USER') or not os.environ.get('ADMIN_PASS'):
        app.logger.warning('ADMIN_USER/ADMIN_PASS não configuradas; usando credenciais legadas.')
    app.logger.info("   OK: Autenticação configurada.")

    class SecureAdminIndexView(AdminIndexView):
        def is_accessible(self):
            return basic_auth.authenticate()

        def inaccessible_callback(self, name, **kwargs):
            return basic_auth.challenge()

    # Protege também a Home do Flask-Admin; sem isso as views protegidas ficam ocultas.
    admin = Admin(
        app,
        name='Painel de Licenças',
        template_mode='bootstrap4',
        index_view=SecureAdminIndexView(name='Home')
    )

    # --- CHAVE DE CRIPTOGRAFIA DA LICENÇA ---
    app.logger.info("4. Configurando chave de criptografia (Fernet)...")
    # A chave padrão DEVE ser uma chave base64 válida de 32 bytes.
    license_secret_key = os.environ.get(
        'LICENSE_SECRET',
        'V2FGVzQ1dGdfSGVscERlc2tfU2VjcmV0S2V5XzIwMjQ='
    )
    if not os.environ.get('LICENSE_SECRET'):
        app.logger.warning('LICENSE_SECRET não configurada; usando segredo legado.')
    license_secret_key = license_secret_key.encode()
    fernet = Fernet(license_secret_key)
    app.logger.info("   OK: Chave de criptografia carregada.")

    # --- PAINEL DE ADMINISTRAÇÃO ---
    app.logger.info("5. Criando a view do painel de administração (CompraView)...")
    class CompraView(ModelView):
        # Este método é chamado pelo Flask-Admin para cada requisição à view.
        def is_accessible(self):
            return basic_auth.authenticate()

        # Este método é chamado se is_accessible() retornar False.
        def inaccessible_callback(self, name, **kwargs):
            # Força o navegador a pedir o login e senha.
            return basic_auth.challenge()

        column_list = ['nome_cliente', 'chave_compra', 'inclui_iot', 'ativado', 'machine_id_ativado', 'data_ativacao']
        column_searchable_list = ['nome_cliente', 'chave_compra', 'machine_id_ativado']
        column_filters = ['ativado', 'inclui_iot']
        form_columns = ['nome_cliente', 'email_cliente', 'inclui_iot']

        @staticmethod
        def format_activation_action(view, context, model, name):
            if not model.ativado:
                return Markup('<span class="text-muted">Ainda não ativada</span>')
            action_url = url_for('resetar_ativacao', compra_id=model.id)
            return Markup(
                f'<form method="post" action="{action_url}" '
                'onsubmit="return confirm(\'Liberar esta chave para outro computador?\');" '
                'style="display:inline">'
                '<button type="submit" class="btn btn-sm btn-warning">'
                'Liberar máquina</button></form>'
            )

        column_formatters = {'data_ativacao': format_activation_action}
    app.logger.info("   OK: View do admin criada.")
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
        data = request.get_json(silent=True) or {}
        chave_compra = str(data.get('chave_compra', '')).strip().upper()
        machine_id = str(data.get('machine_id', '')).strip()

        if not chave_compra or not machine_id:
            return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos.'})

        compra = Compra.query.filter_by(chave_compra=chave_compra).first()

        if not compra:
            return jsonify({'sucesso': False, 'mensagem': 'Chave de Compra inválida ou não encontrada.'})

        if compra.ativado and compra.machine_id_ativado != machine_id:
            return jsonify({'sucesso': False, 'mensagem': 'Esta Chave de Compra já foi utilizada em outra máquina.'})

        if not compra.ativado:
            ativacao = db.session.execute(
                update(Compra)
                .where(Compra.id == compra.id, Compra.ativado.is_(False))
                .values(
                    ativado=True,
                    machine_id_ativado=machine_id,
                    data_ativacao=datetime.now().isoformat()
                )
            )
            db.session.commit()
            if ativacao.rowcount != 1:
                compra = db.session.get(Compra, compra.id)
                if not compra or compra.machine_id_ativado != machine_id:
                    return jsonify({'sucesso': False, 'mensagem': 'Esta Chave de Compra já foi utilizada em outra máquina.'})

        validade = (datetime.now() + timedelta(days=366)).strftime('%Y-%m-%d')
        modulos = f"|IOT={'TRUE' if compra.inclui_iot else 'FALSE'}|ONLINE=TRUE"
        dados_licenca = f"{machine_id}|{validade}{modulos}"
        chave_licenca_final = fernet.encrypt(dados_licenca.encode()).decode()

        return jsonify({
            'sucesso': True,
            'mensagem': 'Sistema ativado com sucesso!',
            'chave_licenca': chave_licenca_final
        })

    @app.route('/api/validar', methods=['POST'])
    def validar_licenca():
        data = request.get_json(silent=True) or {}
        machine_id = str(data.get('machine_id', '')).strip()
        if not machine_id:
            return jsonify({'valida': False, 'mensagem': 'ID de máquina ausente.'}), 400

        compra = Compra.query.filter_by(
            ativado=True,
            machine_id_ativado=machine_id
        ).first()
        if not compra:
            return jsonify({'valida': False, 'mensagem': 'Licença revogada ou não encontrada.'})

        return jsonify({'valida': True})

    @app.route('/admin/compra/reset/<int:compra_id>', methods=['POST'])
    def resetar_ativacao(compra_id):
        if not basic_auth.authenticate():
            return basic_auth.challenge()

        compra = db.session.get(Compra, compra_id)
        if not compra:
            return 'Compra não encontrada.', 404

        compra.ativado = False
        compra.machine_id_ativado = None
        compra.data_ativacao = None
        db.session.commit()
        return redirect(url_for('compra.index_view'))

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