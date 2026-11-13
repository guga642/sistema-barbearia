import os
import csv
import io
import re
from functools import wraps
from flask import Flask, Blueprint, Response, flash, jsonify, redirect, render_template, request, session, url_for
from app.models import db, Servico, Agendamento, BARBEIROS

app = Flask(__name__, template_folder="app/templates", static_folder="app/static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "barbearia-santos-chave-secreta")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///barbearia.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

main_bp = Blueprint("main", __name__)

HORARIOS_PADRAO = [
    "09:00", "09:30", "10:00", "10:30", "11:00", "11:30",
    "13:00", "13:30", "14:00", "14:30", "15:00", "15:30",
    "16:00", "16:30", "17:00", "17:30", "18:00", "18:30", "19:00"
]

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "1234")
WHATSAPP_BARBEARIA = os.getenv("WHATSAPP_BARBEARIA", "5561999999999")


def normalizar_telefone(telefone: str) -> str:
    return re.sub(r"\D", "", telefone or "")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logado"):
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated


def garantir_servicos_iniciais():
    if Servico.query.count() == 0:
        iniciais = [
            Servico(
                nome="Corte + Barba",
                descricao="Corte na tesoura ou máquina + alinhamento completo de barba com toalha quente.",
                preco=70.0,
                duracao_min=50,
                destaque=True,
            ),
            Servico(
                nome="Corte Masculino",
                descricao="Degradê, social ou tesoura com acabamento na navalha.",
                preco=45.0,
                duracao_min=30,
                destaque=False,
            ),
            Servico(
                nome="Barba Terapia",
                descricao="Modelagem, hidratação com óleo essencial e toalha quente.",
                preco=35.0,
                duracao_min=25,
                destaque=False,
            ),
            Servico(
                nome="Sobrancelha",
                descricao="Alinhamento natural na pinça ou navalha.",
                preco=15.0,
                duracao_min=15,
                destaque=False,
            ),
            Servico(
                nome="Pigmentação / Camuflagem",
                descricao="Disfarce natural de falhas na barba ou cabelo.",
                preco=40.0,
                duracao_min=30,
                destaque=False,
            ),
        ]
        db.session.add_all(iniciais)
        db.session.commit()


@main_bp.route("/")
def index():
    garantir_servicos_iniciais()
    servicos = Servico.query.filter_by(ativo=True).order_by(Servico.destaque.desc(), Servico.id.asc()).all()
    return render_template(
        "index.html",
        servicos=servicos,
        barbeiros=BARBEIROS,
        horarios=HORARIOS_PADRAO,
        whatsapp_barbearia=WHATSAPP_BARBEARIA,
    )


@main_bp.route("/api/horarios-ocupados")
def horarios_ocupados():
    data = request.args.get("data", "")
    barbeiro = request.args.get("barbeiro", "Qualquer profissional")
    if not data:
        return jsonify({"ocupados": []})

    ativos = Agendamento.query.filter(
        Agendamento.data == data,
        Agendamento.status != "cancelled",
    ).all()

    ocupados = set()
    for horario in HORARIOS_PADRAO:
        no_horario = [a for a in ativos if a.horario == horario]
        if barbeiro != "Qualquer profissional":
            barbeiros_ocupados = {a.barbeiro for a in no_horario if a.barbeiro in BARBEIROS}
            if barbeiro in barbeiros_ocupados or len(no_horario) >= len(BARBEIROS):
                ocupados.add(horario)
        else:
            if len(no_horario) >= len(BARBEIROS):
                ocupados.add(horario)

    return jsonify({"ocupados": sorted(ocupados)})


@main_bp.route("/api/agendar", methods=["POST"])
def agendar():
    dados = request.get_json() or {}
    cliente_nome = (dados.get("cliente_nome") or "").strip()
    cliente_telefone = normalizar_telefone(dados.get("cliente_telefone"))
    servico_id = dados.get("servico_id")
    barbeiro = (dados.get("barbeiro") or "Qualquer profissional").strip()
    data = (dados.get("data") or "").strip()
    horario = (dados.get("horario") or "").strip()

    if not cliente_nome or len(cliente_telefone) < 10 or not servico_id or not data or not horario:
        return jsonify({"erro": "Preencha todos os campos obrigatórios corretamente."}), 400

    servico = Servico.query.get(servico_id)
    if not servico or not servico.ativo:
        return jsonify({"erro": "Serviço inválido ou indisponível."}), 400

    no_horario = Agendamento.query.filter(
        Agendamento.data == data,
        Agendamento.horario == horario,
        Agendamento.status != "cancelled",
    ).all()

    if len(no_horario) >= len(BARBEIROS):
        return jsonify({"erro": "Todos os barbeiros já estão ocupados nesse horário."}), 409

    if barbeiro != "Qualquer profissional":
        if any(a.barbeiro == barbeiro for a in no_horario):
            return jsonify({"erro": f"O barbeiro {barbeiro} já possui um agendamento às {horario}."}), 409
    else:
        ocupados_nomes = {a.barbeiro for a in no_horario}
        livres = [b for b in BARBEIROS if b not in ocupados_nomes]
        barbeiro = livres[0] if livres else BARBEIROS[0]

    novo = Agendamento(
        cliente_nome=cliente_nome,
        cliente_telefone=cliente_telefone,
        servico_id=servico.id,
        servico_nome=servico.nome,
        valor=servico.preco,
        barbeiro=barbeiro,
        data=data,
        horario=horario,
        status="confirmed",
    )
    db.session.add(novo)
    db.session.commit()

    return jsonify({"mensagem": "Agendamento confirmado!", "agendamento": novo.to_dict()}), 201


@main_bp.route("/api/meus-agendamentos")
def meus_agendamentos():
    telefone = normalizar_telefone(request.args.get("telefone", ""))
    if len(telefone) < 10:
        return jsonify({"agendamentos": []})

    lista = Agendamento.query.filter_by(cliente_telefone=telefone).order_by(
        Agendamento.data.desc(), Agendamento.horario.desc()
    ).all()
    return jsonify({"agendamentos": [a.to_dict() for a in lista]})


@main_bp.route("/api/agendamentos/<int:agendamento_id>/cancelar", methods=["POST"])
def cancelar_cliente(agendamento_id):
    dados = request.get_json() or {}
    telefone = normalizar_telefone(dados.get("telefone", ""))
    agendamento = Agendamento.query.get_or_404(agendamento_id)

    if agendamento.cliente_telefone != telefone:
        return jsonify({"erro": "Telefone não corresponde ao agendamento."}), 403

    agendamento.status = "cancelled"
    db.session.commit()
    return jsonify({"mensagem": "Agendamento cancelado com sucesso."})


@main_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        senha = request.form.get("senha", "").strip()
        if usuario == ADMIN_USER and senha == ADMIN_PASS:
            session["admin_logado"] = True
            return redirect(url_for("main.admin"))
        flash("Usuário ou senha inválidos.", "erro")
    return render_template("login.html")


@main_bp.route("/logout")
def logout():
    session.pop("admin_logado", None)
    return redirect(url_for("main.index"))


@main_bp.route("/admin")
@login_required
def admin():
    garantir_servicos_iniciais()
    data_inicio = request.args.get("data_inicio", "")
    data_fim = request.args.get("data_fim", "")
    barbeiro_filtro = request.args.get("barbeiro", "")
    status_filtro = request.args.get("status", "")

    query = Agendamento.query
    if data_inicio:
        query = query.filter(Agendamento.data >= data_inicio)
    if data_fim:
        query = query.filter(Agendamento.data <= data_fim)
    if barbeiro_filtro:
        query = query.filter(Agendamento.barbeiro == barbeiro_filtro)
    if status_filtro:
        query = query.filter(Agendamento.status == status_filtro)

    agendamentos = query.order_by(Agendamento.data.desc(), Agendamento.horario.asc()).all()
    validos = [a for a in agendamentos if a.status != "cancelled"]

    faturamento_bruto = sum(a.valor for a in validos)
    recebido = sum(a.valor for a in agendamentos if a.status == "completed")
    a_receber = sum(a.valor for a in agendamentos if a.status == "confirmed")

    resumo_barbeiros = []
    for b in BARBEIROS:
        itens_b = [a for a in validos if a.barbeiro == b]
        resumo_barbeiros.append({
            "nome": b,
            "atendimentos": len(itens_b),
            "faturamento": sum(a.valor for a in itens_b),
        })
    resumo_barbeiros.sort(key=lambda x: x["faturamento"], reverse=True)

    servicos = Servico.query.order_by(Servico.ativo.desc(), Servico.id.asc()).all()

    return render_template(
        "admin.html",
        agendamentos=agendamentos,
        servicos=servicos,
        barbeiros=BARBEIROS,
        resumo_barbeiros=resumo_barbeiros,
        faturamento_bruto=faturamento_bruto,
        recebido=recebido,
        a_receber=a_receber,
        filtros={
            "data_inicio": data_inicio,
            "data_fim": data_fim,
            "barbeiro": barbeiro_filtro,
            "status": status_filtro,
        },
    )


@main_bp.route("/admin/agendamentos/<int:agendamento_id>/status", methods=["POST"])
@login_required
def atualizar_status_agendamento(agendamento_id):
    novo_status = request.form.get("status")
    if novo_status in {"confirmed", "completed", "cancelled"}:
        ag = Agendamento.query.get_or_404(agendamento_id)
        ag.status = novo_status
        db.session.commit()
    return redirect(request.referrer or url_for("main.admin"))


@main_bp.route("/admin/servicos/novo", methods=["POST"])
@login_required
def novo_servico():
    db.session.add(Servico(
        nome=request.form.get("nome", "").strip(),
        descricao=request.form.get("descricao", "").strip(),
        preco=float(request.form.get("preco", 0) or 0),
        duracao_min=int(request.form.get("duracao_min", 30) or 30),
        destaque=bool(request.form.get("destaque")),
        ativo=True,
    ))
    db.session.commit()
    return redirect(url_for("main.admin"))


@main_bp.route("/admin/servicos/<int:servico_id>/toggle", methods=["POST"])
@login_required
def toggle_servico(servico_id):
    servico = Servico.query.get_or_404(servico_id)
    servico.ativo = not servico.ativo
    db.session.commit()
    return redirect(url_for("main.admin"))


@main_bp.route("/admin/exportar-csv")
@login_required
def exportar_csv():
    query = Agendamento.query
    if request.args.get("data_inicio"):
        query = query.filter(Agendamento.data >= request.args.get("data_inicio"))
    if request.args.get("data_fim"):
        query = query.filter(Agendamento.data <= request.args.get("data_fim"))
    agendamentos = query.order_by(Agendamento.data.asc(), Agendamento.horario.asc()).all()

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Data", "Horario", "Cliente", "Telefone", "Servico", "Barbeiro", "Valor (R$)", "Status"])

    for a in agendamentos:
        writer.writerow([
            a.id,
            a.data,
            a.horario,
            a.cliente_nome,
            a.cliente_telefone,
            a.servico_nome,
            a.barbeiro,
            f"{a.valor:.2f}".replace(".", ","),
            a.status,
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=relatorio_barbearia_santos.csv"},
    )


app.register_blueprint(main_bp)

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(host="0.0.0.0", port=5000, debug=True)