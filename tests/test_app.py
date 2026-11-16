import importlib.util
import os
import sys
import pytest
from flask import Flask

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

spec = importlib.util.spec_from_file_location("barbearia_app", os.path.join(ROOT_DIR, "app.py"))
flask_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flask_app_module)

from app.models import db, Servico, Agendamento, Bloqueio


@pytest.fixture
def client(tmp_path):
    """Cria uma aplicação Flask e um banco SQLite temporário isolados por teste."""
    db_file = tmp_path / "test_barbearia.db"
    test_app = Flask(
        __name__,
        template_folder=os.path.join(ROOT_DIR, "app", "templates"),
        static_folder=os.path.join(ROOT_DIR, "app", "static"),
    )
    test_app.config["TESTING"] = True
    test_app.config["SECRET_KEY"] = "chave-teste-barbearia"
    test_app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{db_file}"
    test_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(test_app)
    test_app.register_blueprint(flask_app_module.main_bp)

    with test_app.app_context():
        db.create_all()

    with test_app.test_client() as test_client:
        yield test_client

    with test_app.app_context():
        db.session.remove()
        db.engine.dispose()
    if hasattr(db, "_app_engines"):
        db._app_engines.pop(test_app, None)


# ==========================================
# TESTES UNITÁRIOS (Funções e Modelos)
# ==========================================

def test_unitario_normalizar_telefone():
    assert flask_app_module.normalizar_telefone("(61) 99999-8888") == "61999998888"
    assert flask_app_module.normalizar_telefone("61 9 8888-7777") == "61988887777"
    assert flask_app_module.normalizar_telefone(None) == ""


def test_unitario_barbeiro_esta_bloqueado():
    bloqueio_pontual = Bloqueio(barbeiro="Lucas", data="2026-11-20", horario="14:00", motivo="Consulta")
    bloqueio_geral = Bloqueio(barbeiro="Todos", data="2026-11-21", horario="Dia inteiro", motivo="Feriado")

    assert flask_app_module.barbeiro_esta_bloqueado([bloqueio_pontual], "Lucas", "14:00") is True
    assert flask_app_module.barbeiro_esta_bloqueado([bloqueio_pontual], "Carlos", "14:00") is False
    assert flask_app_module.barbeiro_esta_bloqueado([bloqueio_geral], "Diego", "09:00") is True


def test_unitario_serializacao_modelos():
    servico = Servico(id=1, nome="Corte", descricao="Social", preco=45.0, duracao_min=30, destaque=False, ativo=True)
    bloqueio = Bloqueio(id=2, barbeiro="Mateus", data="2026-11-22", horario="12:00", motivo="Almoço")
    agendamento = Agendamento(
        id=3,
        cliente_nome="João",
        cliente_telefone="61999990000",
        servico_nome="Corte",
        valor=45.0,
        barbeiro="Lucas",
        data="2026-11-22",
        horario="10:00",
        status="confirmed",
    )

    assert servico.to_dict()["nome"] == "Corte"
    assert bloqueio.to_dict()["motivo"] == "Almoço"
    assert agendamento.to_dict()["status"] == "confirmed"


# ==========================================
# TESTES DE INTEGRAÇÃO (Rotas, API e Banco)
# ==========================================

def test_integracao_pagina_inicial_e_catalogo(client):
    resposta = client.get("/")
    assert resposta.status_code == 200
    assert b"Barbearia" in resposta.data


def test_integracao_agendamento_e_conflito_horario(client):
    client.get("/")
    with client.application.app_context():
        servico_id = Servico.query.first().id

    payload = {
        "cliente_nome": "Carlos Eduardo",
        "cliente_telefone": "(61) 98888-7777",
        "servico_id": servico_id,
        "barbeiro": "Lucas",
        "data": "2026-11-25",
        "horario": "10:00",
    }

    # 1. Criação com sucesso (201 Created)
    res_ok = client.post("/api/agendar", json=payload)
    assert res_ok.status_code == 201

    # 2. Consulta de horários ocupados
    res_ocupados = client.get("/api/horarios-ocupados?data=2026-11-25&barbeiro=Lucas")
    assert "10:00" in res_ocupados.get_json()["ocupados"]
    assert client.get("/api/horarios-ocupados?data=2026-11-25").status_code == 200

    # 3. Tentativa duplicada no mesmo horário deve retornar 409 Conflict
    res_conflito = client.post("/api/agendar", json=payload)
    assert res_conflito.status_code == 409

    # 4. Dados incompletos ou serviço inexistente retornam 400 Bad Request
    assert client.post("/api/agendar", json={"cliente_nome": ""}).status_code == 400
    assert client.post("/api/agendar", json=dict(payload, servico_id=9999)).status_code == 400

    # 5. Escolha automática ("Qualquer profissional") aloca outro barbeiro livre
    payload_auto = dict(payload, barbeiro="Qualquer profissional")
    res_auto = client.post("/api/agendar", json=payload_auto)
    assert res_auto.status_code == 201
    assert res_auto.get_json()["agendamento"]["barbeiro"] != "Lucas"


def test_integracao_consulta_e_cancelamento_cliente(client):
    client.get("/")
    with client.application.app_context():
        servico_id = Servico.query.first().id

    res_criacao = client.post("/api/agendar", json={
        "cliente_nome": "Rafael Souza",
        "cliente_telefone": "(61) 97777-6666",
        "servico_id": servico_id,
        "barbeiro": "Diego",
        "data": "2026-11-26",
        "horario": "16:00",
    })
    ag_id = res_criacao.get_json()["agendamento"]["id"]

    # Consulta por telefone
    res_lista = client.get("/api/meus-agendamentos?telefone=61977776666")
    assert len(res_lista.get_json()["agendamentos"]) == 1

    # Cancelamento com telefone incorreto (403 Forbidden)
    res_negado = client.post(f"/api/agendamentos/{ag_id}/cancelar", json={"telefone": "61900000000"})
    assert res_negado.status_code == 403

    # Cancelamento com telefone correto (200 OK)
    res_cancelado = client.post(f"/api/agendamentos/{ag_id}/cancelar", json={"telefone": "61977776666"})
    assert res_cancelado.status_code == 200


def test_integracao_painel_admin_bloqueios_e_csv(client):
    # Acesso sem autenticação redireciona para /login
    assert client.get("/admin").status_code == 302

    # Login inválido mantém na tela de login
    assert client.post("/login", data={"usuario": "admin", "senha": "errada"}).status_code == 200

    # Login válido autentica e redireciona
    assert client.post("/login", data={"usuario": "admin", "senha": "1234"}).status_code == 302
    assert client.get("/admin").status_code == 200
    assert client.get("/admin?data_inicio=2026-01-01&data_fim=2026-12-31&barbeiro=Carlos&status=confirmed").status_code == 200

    # Cria bloqueio de horário para Carlos
    res_bloq = client.post("/admin/bloqueios/novo", data={
        "barbeiro": "Carlos",
        "data": "2026-11-27",
        "horario": "15:00",
        "motivo": "Almoço",
    })
    assert res_bloq.status_code == 302

    # Cliente não consegue agendar no horário bloqueado (409)
    with client.application.app_context():
        servico_id = Servico.query.first().id

    res_ag_bloq = client.post("/api/agendar", json={
        "cliente_nome": "Pedro Lima",
        "cliente_telefone": "(61) 96666-5555",
        "servico_id": servico_id,
        "barbeiro": "Carlos",
        "data": "2026-11-27",
        "horario": "15:00",
    })
    assert res_ag_bloq.status_code == 409

    # Cadastra novo serviço, alterna status e exporta CSV
    assert client.post("/admin/servicos/novo", data={
        "nome": "Hidratação Capilar",
        "preco": "30.00",
        "duracao_min": "20",
        "descricao": "Tratamento completo",
    }).status_code == 302

    assert client.post(f"/admin/servicos/{servico_id}/toggle").status_code == 302
    assert client.get("/admin/exportar-csv?data_inicio=2026-01-01&data_fim=2026-12-31").status_code == 200

    # Remove bloqueio e encerra sessão
    with client.application.app_context():
        bloq_id = Bloqueio.query.first().id
    assert client.post(f"/admin/bloqueios/{bloq_id}/excluir").status_code == 302
    assert client.get("/logout").status_code == 302