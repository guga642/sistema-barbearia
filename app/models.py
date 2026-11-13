from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Lista de profissionais atualizada
BARBEIROS = ["Lucas", "Carlos", "Diego", "Mateus"]

class Servico(db.Model):
    __tablename__ = "servicos"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(255), default="")
    preco = db.Column(db.Float, nullable=False)
    duracao_min = db.Column(db.Integer, default=30)
    destaque = db.Column(db.Boolean, default=False)
    ativo = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nome": self.nome,
            "descricao": self.descricao,
            "preco": self.preco,
            "duracao_min": self.duracao_min,
            "destaque": self.destaque,
            "ativo": self.ativo,
        }

class Agendamento(db.Model):
    __tablename__ = "agendamentos"

    id = db.Column(db.Integer, primary_key=True)
    cliente_nome = db.Column(db.String(120), nullable=False)
    cliente_telefone = db.Column(db.String(25), nullable=False)
    servico_id = db.Column(db.Integer, db.ForeignKey("servicos.id"), nullable=True)
    servico_nome = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    barbeiro = db.Column(db.String(60), nullable=False, default="Qualquer profissional")
    data = db.Column(db.String(10), nullable=False)
    horario = db.Column(db.String(5), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="confirmed")
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "cliente_nome": self.cliente_nome,
            "cliente_telefone": self.cliente_telefone,
            "servico_nome": self.servico_nome,
            "valor": self.valor,
            "barbeiro": self.barbeiro,
            "data": self.data,
            "horario": self.horario,
            "status": self.status,
        }