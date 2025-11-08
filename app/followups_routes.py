# app/followups_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy import asc, desc
from datetime import datetime, timedelta
from .models import db, Client, Order, FollowUp

followups_bp = Blueprint("followups", __name__)

# Vista del calendario
@followups_bp.route("/calendar")
@login_required
def calendar_view():
    return render_template("calendar.html")

# Feed JSON para FullCalendar (rango opcional)
@followups_bp.route("/api/followups")
@login_required
def api_followups():
    # FullCalendar suele mandar ?start=YYYY-MM-DD&end=YYYY-MM-DD
    def parse_date(s: str):
        if not s:
            return None
        try:
            # nos quedamos con YYYY-MM-DD
            return datetime.fromisoformat(s[:10])
        except Exception:
            return None

    start = parse_date(request.args.get("start"))
    end = parse_date(request.args.get("end"))

    try:
        q = FollowUp.query
        if start:
            q = q.filter(FollowUp.when_at >= start)
        if end:
            # incluir todo el día 'end'
            q = q.filter(FollowUp.when_at < (end + timedelta(days=1)))

        items = q.order_by(asc(FollowUp.when_at)).all()

        def color_for(kind, done):
            if done:
                return "#9AA0A6"  # gris para completados
            return {"seguimiento": "#0d6efd", "entrega": "#28a745", "cobro": "#fd7e14"}.get(kind, "#0d6efd")

        events = []
        for f in items:
            title = f.title
            if f.order_id:
                title = f"[Pedido #{f.order_id}] " + title
            events.append({
                "id": f.id,
                "title": title,
                "start": f.when_at.isoformat(),
                "allDay": False,
                "backgroundColor": color_for(f.kind, f.done),
                "borderColor": color_for(f.kind, f.done),
                "url": url_for("followups.edit_followup", followup_id=f.id),
            })
        return jsonify(events), 200
    except Exception as e:
        # Log mínimo y lista vacía para no romper el calendario
        print("ERROR /api/followups:", repr(e))
        return jsonify([]), 200

# Crear seguimiento (desde pedido o cliente)
@followups_bp.route("/followups/new", methods=["GET", "POST"])
@login_required
def new_followup():
    client_id = request.args.get("client_id", type=int)
    order_id  = request.args.get("order_id", type=int)
    clients = Client.query.filter_by(is_deleted=False).order_by(asc(Client.first_name)).all()
    orders  = Order.query.order_by(desc(Order.created_at)).limit(50).all()

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        order_id  = request.form.get("order_id", type=int)
        kind      = request.form.get("kind", "seguimiento")
        title     = (request.form.get("title") or "").strip()
        notes     = (request.form.get("notes") or "").strip()
        when_at_s = request.form.get("when_at")

        if not client_id or not title or not when_at_s:
            flash("Cliente, título y fecha/hora son obligatorios.", "danger")
            return render_template("followup_form.html", followup=None, clients=clients, orders=orders, client_id=client_id, order_id=order_id)

        when_at = datetime.fromisoformat(when_at_s)
        f = FollowUp(client_id=client_id, order_id=order_id, kind=kind, title=title, notes=notes, when_at=when_at)
        db.session.add(f)
        db.session.commit()
        flash("Seguimiento creado.", "success")
        return redirect(url_for("followups.calendar_view"))

    return render_template("followup_form.html", followup=None, clients=clients, orders=orders, client_id=client_id, order_id=order_id)

# Editar / marcar hecho / eliminar
@followups_bp.route("/followups/<int:followup_id>/edit", methods=["GET", "POST"])
@login_required
def edit_followup(followup_id):
    f = FollowUp.query.get_or_404(followup_id)
    clients = Client.query.filter_by(is_deleted=False).order_by(asc(Client.first_name)).all()
    orders  = Order.query.order_by(desc(Order.created_at)).limit(50).all()

    if request.method == "POST":
        action = request.form.get("action")
        if action == "delete":
            db.session.delete(f)
            db.session.commit()
            flash("Seguimiento eliminado.", "success")
            return redirect(url_for("followups.calendar_view"))
        elif action == "toggle_done":
            f.done = not f.done
            db.session.commit()
            return redirect(url_for("followups.edit_followup", followup_id=f.id))
        else:
            f.client_id = request.form.get("client_id", type=int)
            f.order_id  = request.form.get("order_id", type=int)
            f.kind      = request.form.get("kind", "seguimiento")
            f.title     = (request.form.get("title") or "").strip()
            f.notes     = (request.form.get("notes") or "").strip()
            when_at_s   = request.form.get("when_at")
            f.when_at   = datetime.fromisoformat(when_at_s) if when_at_s else f.when_at
            db.session.commit()
            flash("Seguimiento actualizado.", "success")
            return redirect(url_for("followups.edit_followup", followup_id=f.id))

    return render_template("followup_form.html", followup=f, clients=clients, orders=orders)