from flask import Flask, request, jsonify
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_basicauth import BasicAuth
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import os

from models import db, Compra

app = Flask(__name__)

# --- CONFIGURAÇÃO DE SEGURANÇA E BANCO DE DADOS ---
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'uma-chave-secreta-muito-forte-para-desenvolvimento')
# CORREÇÃO PARA O RENDER: O Render usa 'postgres://', mas o SQLAlchemy espera 'postgresql://'
database_url = os.environ.get('DATABASE_URL')

if not database_url:
    raise ValueError("ERRO CRÍTICO: A variável de ambiente 'DATABASE_URL' não foi encontrada. Verifique as configurações do serviço no Render.com e garanta que um banco de dados PostgreSQL está vinculado.")

if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url

db.init_app(app)

# --- PROTEÇÃO DO PAINEL ADMIN ---
# DEFINA ESSAS VARIÁVEIS DE AMBIENTE NO RENDER.COM
app.config['BASIC_AUTH_USERNAME'] = os.environ.get('ADMIN_USER', 'admin')
app.config['BASIC_AUTH_PASSWORD'] = os.environ.get('ADMIN_PASS', 'senhaSuperSecreta')
basic_auth = BasicAuth(app)

# --- CHAVE DE CRIPTOGRAFIA DA LICENÇA ---
# DEFINA ESSA VARIÁVEL DE AMBIENTE NO RENDER.COM
LICENSE_SECRET_KEY = os.environ.get('LICENSE_SECRET', 'V2FGVzQ1dGdfSGVscERlc2tfU2VjcmV0S2V5XzIwMjQ=').encode()
fernet = Fernet(LICENSE_SECRET_KEY)

# --- PAINEL DE ADMINISTRAÇÃO ---
class CompraView(ModelView):
    # Protege a view com senha
    def is_accessible(self):
        # Agora o 'basic_auth' já existe quando este método é chamado.
        return basic_auth.check()

    # Colunas visíveis na lista
    column_list = ['nome_cliente', 'chave_compra', 'inclui_iot', 'ativado', 'machine_id_ativado', 'data_ativacao']
    column_searchable_list = ['nome_cliente', 'chave_compra', 'machine_id_ativado']
    column_filters = ['ativado', 'inclui_iot']
    form_columns = ['nome_cliente', 'email_cliente', 'inclui_iot']

# --- ROTA PRINCIPAL (para não dar erro "Not Found") ---
@app.route('/')
def index():
    return "Servidor de Licenças AcervoTI - Online", 200

# --- API DE ATIVAÇÃO (LÓGICA ATUALIZADA) ---
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

    if compra.ativado:
        # Se já foi ativado, verifica se é para a mesma máquina (reinstalação)
        if compra.machine_id_ativado == machine_id:
             pass # Permite reativar na mesma máquina
        else:
            return jsonify({'sucesso': False, 'mensagem': f'Esta Chave de Compra já foi utilizada em outra máquina.'})

    # Atualiza o registro da compra
    compra.ativado = True
    compra.machine_id_ativado = machine_id
    compra.data_ativacao = datetime.now().isoformat()
    db.session.commit()

    # Gera a licença final
    validade = (datetime.now() + timedelta(days=366)).strftime('%Y-%m-%d')
    modulos = f"|IOT={'TRUE' if compra.inclui_iot else 'FALSE'}"
    
    dados_licenca = f"{machine_id}|{validade}{modulos}"
    chave_licenca_final = fernet.encrypt(dados_licenca.encode()).decode()

    return jsonify({
        'sucesso': True,
        'mensagem': 'Sistema ativado com sucesso!',
        'chave_licenca': chave_licenca_final
    })

# Comando para criar o banco de dados na primeira vez
with app.app_context():
    db.create_all() # Garante que as tabelas existam

    # Inicializa o painel de admin DEPOIS que as tabelas foram criadas
    admin = Admin(app, name='Painel de Licenças', template_mode='bootstrap4')
    admin.add_view(CompraView(Compra, db.session))

if __name__ == '__main__':
    # O Render.com usa um servidor de produção (como Gunicorn), então esta parte não é executada lá.
    # A porta 5000 é um padrão para desenvolvimento Flask.
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)