from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Integer, String, Text, ForeignKey, DateTime, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

db = SQLAlchemy()

class Notebook(db.Model):
    __tablename__ = 'notebooks'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    numero_carrinho: Mapped[int] = mapped_column(Integer, unique=True, nullable=True)
    tipo: Mapped[str] = mapped_column(String, default='Notebook')
    modelo: Mapped[str] = mapped_column(String, nullable=True)
    numero_serie: Mapped[str] = mapped_column(String, nullable=True)
    data_compra: Mapped[str] = mapped_column(Text, nullable=True) # CORREÇÃO DEFINITIVA: Usar Text para evitar conversão automática de data pelo SQLAlchemy.
    status: Mapped[str] = mapped_column(String, default='Disponível')
    localizacao: Mapped[str] = mapped_column(String, nullable=True)
    observacoes: Mapped[str] = mapped_column(Text, nullable=True)
    data_cadastro: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())

class ConfiguracaoSistema(db.Model):
    __tablename__ = 'configuracoes_sistema'
    chave: Mapped[str] = mapped_column(String, primary_key=True)
    valor: Mapped[str] = mapped_column(String, nullable=True)

class SessaoUso(db.Model):
    __tablename__ = 'sessoes_uso'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turma: Mapped[str] = mapped_column(String, nullable=True)
    professor: Mapped[str] = mapped_column(String, nullable=True)
    programa: Mapped[str] = mapped_column(String, nullable=True)
    data_inicio: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    quantidade_notebooks: Mapped[int] = mapped_column(Integer, nullable=True)
    observacoes: Mapped[str] = mapped_column(Text, nullable=True)
    previsao_devolucao: Mapped[str] = mapped_column(Text, nullable=True)
    usuario_movimentacao: Mapped[str] = mapped_column(String, nullable=True)

class Problema(db.Model):
    __tablename__ = 'problemas'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notebook_id: Mapped[str] = mapped_column(ForeignKey('notebooks.id', ondelete='CASCADE'), nullable=True)
    tipo_problema: Mapped[str] = mapped_column(String, nullable=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=True)
    data_registro: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    responsavel: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=True)
    prioridade: Mapped[str] = mapped_column(String, default='Normal')
    categoria: Mapped[str] = mapped_column(String, default='Hardware')
    parecer_tecnico: Mapped[str] = mapped_column(Text, nullable=True)
    local_incidente: Mapped[str] = mapped_column(String, default='NÃO INFORMADO')
    data_resolucao: Mapped[str] = mapped_column(Text, nullable=True)

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    perm_movimentacao: Mapped[bool] = mapped_column(Boolean, default=False)
    perm_cadastro: Mapped[bool] = mapped_column(Boolean, default=False)
    perm_config: Mapped[bool] = mapped_column(Boolean, default=False)
    perm_kiosk: Mapped[bool] = mapped_column(Boolean, default=False)
    perm_chamados: Mapped[bool] = mapped_column(Boolean, default=False)
    perm_ajuda: Mapped[bool] = mapped_column(Boolean, default=False)
    perm_almoxarifado: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[str] = mapped_column(Text, nullable=True)

class Historico(db.Model):
    __tablename__ = 'historico'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id_etiqueta: Mapped[str] = mapped_column(String, nullable=True)
    acao: Mapped[str] = mapped_column(String, nullable=True)
    usuario_movimentacao: Mapped[str] = mapped_column(String, nullable=True)
    responsavel: Mapped[str] = mapped_column(String, default='-') # Manter como string
    data: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    obs: Mapped[str] = mapped_column(Text, nullable=True)

class Agendamento(db.Model):
    __tablename__ = 'agendamentos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    solicitante: Mapped[str] = mapped_column(String, nullable=True)
    data_uso: Mapped[str] = mapped_column(String, nullable=True)
    periodo: Mapped[str] = mapped_column(String, nullable=True)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=True)
    finalidade: Mapped[str] = mapped_column(Text, nullable=True)
    itens_reservados: Mapped[str] = mapped_column(Text, nullable=True)
    horario_retirada: Mapped[str] = mapped_column(String, nullable=True)
    horario_devolucao: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default='Agendado')
    data_criacao: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    registrado_por: Mapped[str] = mapped_column(String, nullable=True)
    codigo_reserva: Mapped[str] = mapped_column(String, nullable=True)

class AlmoxProduto(db.Model):
    __tablename__ = 'almox_produtos'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String, unique=True)
    nome: Mapped[str] = mapped_column(String, nullable=False)
    categoria: Mapped[str] = mapped_column(String, nullable=True)
    quantidade_atual: Mapped[int] = mapped_column(Integer, default=0)
    estoque_minimo: Mapped[int] = mapped_column(Integer, default=5)
    custo_unitario: Mapped[float] = mapped_column(Float, default=0.0)

class AlmoxMovimentacao(db.Model):
    __tablename__ = 'almox_movimentacoes'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey('almox_produtos.id'))
    tipo: Mapped[str] = mapped_column(String) # 'ENTRADA' ou 'SAIDA'
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    usuario: Mapped[str] = mapped_column(String, nullable=True)
    destino_id: Mapped[str] = mapped_column(String, nullable=True)
    data_movimentacao: Mapped[str] = mapped_column(Text, default=lambda: datetime.now().isoformat())
    observacao: Mapped[str] = mapped_column(Text, nullable=True)