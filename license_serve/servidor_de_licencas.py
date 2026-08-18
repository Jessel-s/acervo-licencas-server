# c:\DESENVOLVIMENTO\license_server\servidor_de_licencas.py

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from cryptography.fernet import Fernet
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# --- CONFIGURAÇÃO ---
# Em um servidor real, use variáveis de ambiente para segurança e flexibilidade!
# Render.com injetará essas variáveis.
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///licenses.db')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'uma-chave-secreta-para-proteger-a-api') # Chave da API, não da licença

# A chave mestra que criptografa as licenças dos clientes
# Esta chave NUNCA sai deste servidor. Ela será injetada como variável de ambiente no Render.
LICENSE_MASTER_KEY = os.environ.get('LICENSE_MASTER_KEY', 'V2FGVzQ1dGdfSGVscERlc2tfU2VjcmV0S2V5XzIwMjQ=').encode('utf-8')

db = SQLAlchemy(app)

# --- MODELOS DE DADOS DO SERVIDOR ---

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Chave que você envia para o cliente para ele ativar o software
    chave_de_compra = db.Column(db.String(50), unique=True, nullable=False)

class Licenca(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('clientes.id'), nullable=False)
    machine_id = db.Column(db.String(200), nullable=False)
    data_expiracao = db.Column(db.Date, nullable=False)
    modulo_iot = db.Column(db.Boolean, default=False)
    data_ativacao = db.Column(db.DateTime, default=datetime.utcnow)

# --- API DE ATIVAÇÃO ---

@app.route('/api/ativar', methods=['POST'])
def ativar_licenca():
    data = request.json
    chave_compra = data.get('chave_compra')
    machine_id = data.get('machine_id')

    if not chave_compra or not machine_id:
        return jsonify({'sucesso': False, 'mensagem': 'Dados incompletos.'}), 400

    # 1. Encontra o cliente pela chave de compra
    cliente = Cliente.query.filter_by(chave_de_compra=chave_compra).first()
    if not cliente:
        return jsonify({'sucesso': False, 'mensagem': 'Chave de compra inválida.'}), 403

    # 2. Verifica se já existe uma licença para este cliente/máquina
    licenca_existente = Licenca.query.filter_by(cliente_id=cliente.id).first()
    if licenca_existente:
        # Lógica de renovação ou reativação poderia entrar aqui
        # Por enquanto, vamos apenas gerar uma nova chave com os dados existentes
        licenca = licenca_existente
        licenca.machine_id = machine_id # Atualiza o ID da máquina se for uma reinstalação
        licenca.data_ativacao = datetime.utcnow()
    else:
        # 3. Cria uma nova licença para o cliente (Ex: 1 ano de validade)
        data_expiracao = datetime.now().date() + timedelta(days=365)
        licenca = Licenca(
            cliente_id=cliente.id,
            machine_id=machine_id,
            data_expiracao=data_expiracao,
            modulo_iot=False # Lógica para ativar módulos premium iria aqui
        )
        db.session.add(licenca)
    
    db.session.commit()

    # 4. Gera a string da licença criptografada para enviar de volta ao cliente
    try:
        fernet_obj = Fernet(LICENSE_MASTER_KEY)
        
        modulos = []
        if licenca.modulo_iot:
            modulos.append('IOT=TRUE')
        modulos_str = '|'.join(modulos)

        # Formato: MACHINE_ID|YYYY-MM-DD|MODULOS...
        dados_licenca = f"{licenca.machine_id}|{licenca.data_expiracao.strftime('%Y-%m-%d')}|{modulos_str}"
        
        chave_final_cliente = fernet_obj.encrypt(dados_licenca.encode()).decode()

        return jsonify({
            'sucesso': True,
            'mensagem': 'Software ativado com sucesso!',
            'chave_licenca': chave_final_cliente
        })

    except Exception as e:
        return jsonify({'sucesso': False, 'mensagem': f'Erro interno ao gerar licença: {e}'}), 500

if __name__ == '__main__':
    # Este bloco é para execução local. No Render, Gunicorn será usado.
    with app.app_context():
        # Cria o banco de dados se ele não existir (útil para o primeiro deploy no Render)
        db.create_all()
        # Adiciona um cliente de exemplo se o banco estiver vazio
        if not Cliente.query.first():
            cliente_teste = Cliente(nome='Cliente Exemplo', email='exemplo@email.com', chave_de_compra='COMPRA-123-XYZ')
            db.session.add(cliente_teste)
            db.session.commit()
            print("Cliente de exemplo 'COMPRA-123-XYZ' adicionado ao banco de dados.")
    
    # Para execução local, use app.run(). Para produção no Render, Gunicorn será o servidor.
    # app.run(debug=True, port=5001) # Comente ou remova esta linha para deploy no Render
    # Render usará 'gunicorn servidor_de_licencas:app'
