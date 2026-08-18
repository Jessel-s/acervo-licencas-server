from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Date, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

db = SQLAlchemy() # Importa o db do servidor_de_licencas.py, não do app.py principal

class Cliente(db.Model):
    __tablename__ = 'clientes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    chave_de_compra: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

class Licenca(db.Model):
    __tablename__ = 'licencas'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey('clientes.id'), nullable=False)
    machine_id: Mapped[str] = mapped_column(String(200), nullable=False)
    data_expiracao: Mapped[Date] = mapped_column(Date, nullable=False)
    modulo_iot: Mapped[bool] = mapped_column(Boolean, default=False)
    data_ativacao: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

# Não é necessário importar outros modelos aqui, apenas os que o servidor de licenças usa.