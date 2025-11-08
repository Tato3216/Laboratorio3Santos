
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required
from .models import db, Client
import io
from openpyxl import Workbook

bp = Blueprint("main", __name__)

@bp.route("/")
def index():
    return redirect(url_for("main.list_clients"))

@bp.route("/clients")
@login_required
def list_clients():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Client.query.filter_by(is_deleted=False)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Client.first_name.ilike(like)) |
            (Client.last_name.ilike(like)) |
            (Client.email.ilike(like)) |
            (Client.phone.ilike(like)) |
            (Client.company.ilike(like))
        )

    pagination = query.order_by(Client.created_at.desc()).paginate(page=page, per_page=per_page)
    return render_template("clients_list.html", pagination=pagination, q=q)

@bp.route("/clients/new", methods=["GET", "POST"])
@login_required
def create_client():
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        company = request.form.get("company", "").strip()
        address = request.form.get("address", "").strip()
        notes = request.form.get("notes", "").strip()

        if not first_name or not last_name or not email:
            flash("Nombre, Apellido y Email son obligatorios.", "danger")
            return render_template("client_form.html", client=None)

        if Client.query.filter_by(email=email).first():
            flash("Ese correo ya existe. Usa otro.", "danger")
            return render_template("client_form.html", client=None)

        client = Client(
            first_name=first_name, last_name=last_name, email=email,
            phone=phone, company=company, address=address, notes=notes
        )
        db.session.add(client)
        db.session.commit()
        flash("Cliente creado.", "success")
        return redirect(url_for("main.list_clients"))

    return render_template("client_form.html", client=None)

@bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
def edit_client(client_id):
    client = Client.query.get_or_404(client_id)

    if request.method == "POST":
        client.first_name = request.form.get("first_name", "").strip()
        client.last_name = request.form.get("last_name", "").strip()
        client.email = request.form.get("email", "").strip()
        client.phone = request.form.get("phone", "").strip()
        client.company = request.form.get("company", "").strip()
        client.address = request.form.get("address", "").strip()
        client.notes = request.form.get("notes", "").strip()

        db.session.commit()
        flash("Cliente actualizado.", "success")
        return redirect(url_for("main.list_clients"))

    return render_template("client_form.html", client=client)

@bp.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    client.is_deleted = True
    db.session.commit()
    flash("Cliente desactivado (borrado lógico).", "success")
    return redirect(url_for("main.list_clients"))

@bp.route("/clients/export")
@login_required
def export_clients():
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    ws.append(["ID", "Nombre", "Apellido", "Email", "Teléfono", "Empresa", "Dirección", "Notas", "Creado"])

    for c in Client.query.filter_by(is_deleted=False).order_by(Client.id):
        ws.append([c.id, c.first_name, c.last_name, c.email, c.phone or "", c.company or "", c.address or "", c.notes or "", c.created_at.strftime("%Y-%m-%d %H:%M:%S")])

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name="clientes.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
