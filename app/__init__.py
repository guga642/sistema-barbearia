import os
from flask import Flask
from app.models import db, Servico

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'barbearia-estilo-chave-secreta-dev'
    
    db_path = os.path.join(app.root_path, 'database', 'barbearia.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()
        
        # Popula serviços padrão se a tabela estiver vazia
        if Servico.query.count() == 0:
            servicos_iniciais = [
                Servico(nome='Corte de Cabelo', preco=40.0, duracao=30),
                Servico(nome='Barba Completa', preco=30.0, duracao=20),
                Servico(nome='Combo (Cabelo + Barba)', preco=65.0, duracao=50),
                Servico(nome='Pézinho / Sobrancelha', preco=15.0, duracao=15)
            ]
            db.session.add_all(servicos_iniciais)
            db.session.commit()

    from app.routes import main
    app.register_blueprint(main)

    return app