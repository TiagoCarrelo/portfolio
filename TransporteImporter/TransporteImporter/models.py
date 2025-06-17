from datetime import datetime
from app import db

class Cliente(db.Model):
    """Modelo para armazenar informações dos clientes"""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    horario = db.Column(db.String(50))  # Horário preferencial do cliente
    destino = db.Column(db.String(200))  # Destino do transporte
    nome_seguro = db.Column(db.String(100))  # Nome da empresa de seguro
    morada = db.Column(db.Text)  # Morada/endereço do cliente
    contacto = db.Column(db.String(50))  # Contacto telefónico
    regiao = db.Column(db.String(50), nullable=False)  # Região detectada automaticamente
    dados_originais = db.Column(db.Text)  # Para armazenar os dados como vieram da mensagem
    status_cliente = db.Column(db.String(20), default='Importado')  # Importado, Transportado, Removido
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relacionamento com agendamentos
    agendamentos = db.relationship('Agendamento', backref='cliente', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Cliente {self.nome}>'

class Agendamento(db.Model):
    """Modelo para armazenar agendamentos dos clientes"""
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=False)
    data_agendamento = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='Agendado')  # Agendado, Concluído, Cancelado
    observacoes = db.Column(db.Text)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
    
    def __repr__(self):
        return f'<Agendamento {self.id} - {self.data_agendamento}>'
