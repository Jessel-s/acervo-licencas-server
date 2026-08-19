from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
import uuid

db = SQLAlchemy()

class Compra(db.Model):
    __tablename__ = 'compras'
    id: Mapped[int] = mapped_column(db.Integer, primary_key=True)
    chave_compra: Mapped[str] = mapped_column(db.String, unique=True, default=lambda: f"COMPRA-{str(uuid.uuid4())[:8].upper()}")
    nome_cliente: Mapped[str] = mapped_column(db.String, nullable=False)
    email_cliente: Mapped[str] = mapped_column(db.String, nullable=True)
    
    # Módulos
    inclui_iot: Mapped[bool] = mapped_column(db.Boolean, default=False)
    
    # Controle de Ativação
    ativado: Mapped[bool] = mapped_column(db.Boolean, default=False)
    machine_id_ativado: Mapped[str] = mapped_column(db.String, nullable=True)
    data_ativacao: Mapped[str] = mapped_column(db.String, nullable=True)

    def __repr__(self):
        return f"Compra de {self.nome_cliente} ({self.chave_compra})"