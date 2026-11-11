from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from app.models import db, Cliente, Servico, Agendamento
from datetime import datetime

main = Blueprint('main', __name__)

@main.route('/')
def index():
    servicos = Servico.query.all()
    return render_template('index.html', servicos=servicos)

@main.route('/agendar', methods=['POST'])
def agendar():
    dados = request.json
    nome = dados.get('nome')
    telefone = dados.get('telefone')
    servico_id = dados.get('servico_id')
    data_hora_str = dados.get('data_hora')

    if not all([nome, telefone, servico_id, data_hora_str]):
        return jsonify({'erro': 'Todos os campos são obrigatórios!'}), 400

    data_hora = datetime.strptime(data_hora_str, '%Y-%m-%dT%H:%M')

    conflito = Agendamento.query.filter_by(data_hora=data_hora).filter(Agendamento.status != 'Cancelado').first()
    if conflito:
        return jsonify({'erro': 'Este horário já está ocupado! Por favor, escolha outro horário.'}), 400

    cliente = Cliente.query.filter_by(telefone=telefone).first()
    if not cliente:
        cliente = Cliente(nome=nome, telefone=telefone)
        db.session.add(cliente)
        db.session.commit()

    novo_agendamento = Agendamento(
        cliente_id=cliente.id,
        servico_id=servico_id,
        data_hora=data_hora
    )
    db.session.add(novo_agendamento)
    db.session.commit()

    return jsonify({'sucesso': True, 'mensagem': 'Agendamento realizado com sucesso!'})

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        
        if usuario == 'admin' and senha == 'admin123':
            session['logado'] = True
            return redirect(url_for('main.admin'))
        
        return render_template('login.html', erro='Usuário ou senha incorretos!')
    
    return render_template('login.html')

@main.route('/logout')
def logout():
    session.pop('logado', None)
    return redirect(url_for('main.login'))

@main.route('/admin')
def admin():
    if not session.get('logado'):
        return redirect(url_for('main.login'))
    
    data_filtro = request.args.get('data')
    query = Agendamento.query

    if data_filtro:
        try:
            data_obj = datetime.strptime(data_filtro, '%Y-%m-%d').date()
            start_date = datetime.combine(data_obj, datetime.min.time())
            end_date = datetime.combine(data_obj, datetime.max.time())
            query = query.filter(Agendamento.data_hora >= start_date, Agendamento.data_hora <= end_date)
        except ValueError:
            data_filtro = None

    agendamentos = query.order_by(Agendamento.data_hora.desc()).all()
    servicos = Servico.query.all()

    # Cálculo financeiro apenas de agendamentos confirmados
    total_faturado = sum(a.servico.preco for a in agendamentos if a.status != 'Cancelado')
    total_atendimentos = sum(1 for a in agendamentos if a.status != 'Cancelado')

    return render_template(
        'admin.html',
        agendamentos=agendamentos,
        servicos=servicos,
        data_filtro=data_filtro or '',
        total_faturado=total_faturado,
        total_atendimentos=total_atendimentos
    )

@main.route('/admin/cancelar/<int:id>', methods=['POST'])
def cancelar_agendamento(id):
    if not session.get('logado'):
        return jsonify({'erro': 'Não autorizado'}), 401
    agendamento = Agendamento.query.get_or_404(id)
    agendamento.status = 'Cancelado'
    db.session.commit()
    return jsonify({'sucesso': True, 'mensagem': 'Agendamento cancelado com sucesso!'})

@main.route('/admin/servico/novo', methods=['POST'])
def novo_servico():
    if not session.get('logado'):
        return jsonify({'erro': 'Não autorizado'}), 401
    dados = request.json
    nome = dados.get('nome')
    preco = dados.get('preco')
    duracao = dados.get('duracao')

    if not all([nome, preco, duracao]):
        return jsonify({'erro': 'Preencha todos os campos do serviço!'}), 400

    servico = Servico(nome=nome, preco=float(preco), duracao=int(duracao))
    db.session.add(servico)
    db.session.commit()
    return jsonify({'sucesso': True, 'mensagem': 'Serviço cadastrado com sucesso!'})

@main.route('/admin/servico/deletar/<int:id>', methods=['POST'])
def deletar_servico(id):
    if not session.get('logado'):
        return jsonify({'erro': 'Não autorizado'}), 401
    servico = Servico.query.get_or_404(id)

    if servico.agendamentos:
        return jsonify({'erro': 'Não é possível remover um serviço vinculado a agendamentos já realizados!'}), 400

    db.session.delete(servico)
    db.session.commit()
    return jsonify({'sucesso': True, 'mensagem': 'Serviço excluído com sucesso!'})