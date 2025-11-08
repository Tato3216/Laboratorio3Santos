# app/dashboard_routes.py
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func, extract, desc
from .models import db, Client, Order, OrderItem, Product
import json

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    # === Métricas rápidas ===
    total_clientes = db.session.scalar(
        db.select(func.count(Client.id)).where(Client.is_deleted == False)
    )
    total_pedidos = db.session.scalar(db.select(func.count(Order.id)))
    total_pendientes = db.session.scalar(
        db.select(func.count(Order.id)).where(Order.status == "pendiente")
    )
    total_ingresos = db.session.scalar(
        db.select(func.coalesce(func.sum(Order.total), 0))
    )

    # === Ingresos últimos 30 días (por día) ===
    hoy = datetime.utcnow().date()
    hace_30 = hoy - timedelta(days=29)

    ingresos_30 = (
        db.session.query(
            func.date(Order.created_at).label("fecha"),
            func.coalesce(func.sum(Order.total), 0).label("monto"),
        )
        .filter(func.date(Order.created_at) >= hace_30)
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
        .all()
    )

    labels_30 = []
    data_30 = []
    for i in range(30):
        d = hace_30 + timedelta(days=i)
        labels_30.append(d.strftime("%Y-%m-%d"))
        found = next((float(r.monto) for r in ingresos_30 if r.fecha == d), 0.0)
        data_30.append(found)

    # === Ingresos últimos 6 meses (por mes) ===
    six_months_ago = (hoy.replace(day=1) - timedelta(days=150))  # ~5 meses + buffer
    ingresos_mes = (
        db.session.query(
            extract("year", Order.created_at).label("y"),
            extract("month", Order.created_at).label("m"),
            func.coalesce(func.sum(Order.total), 0).label("monto"),
        )
        .filter(Order.created_at >= six_months_ago)
        .group_by("y", "m")
        .order_by("y", "m")
        .all()
    )
    labels_mes = [f"{int(y):04d}-{int(m):02d}" for y, m, _ in ingresos_mes]
    data_mes = [float(monto) for _, _, monto in ingresos_mes]

    # === Top clientes por ingresos (Top 5) ===
    top_clientes = (
        db.session.query(
            Client.id,
            Client.first_name,
            Client.last_name,
            func.coalesce(func.sum(Order.total), 0).label("monto"),
        )
        .join(Order, Order.client_id == Client.id)
        .group_by(Client.id, Client.first_name, Client.last_name)
        .order_by(desc("monto"))
        .limit(5)
        .all()
    )

    # === Top productos más vendidos (por cantidad) ===
    TOP_N = 5
    top_products_rows = (
        db.session.query(
            OrderItem.product_id,
            Product.name.label("product_name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("qty"),
            func.coalesce(func.sum(OrderItem.quantity * OrderItem.unit_price), 0).label(
                "revenue"
            ),
        )
        .outerjoin(Product, Product.id == OrderItem.product_id)
        .group_by(OrderItem.product_id, Product.name)
        .order_by(desc("qty"))
        .limit(TOP_N)
        .all()
    )

    labels_top = []
    data_qty_top = []
    data_rev_top = []
    for row in top_products_rows:
        labels_top.append(row.product_name or "Sin catálogo")
        data_qty_top.append(float(row.qty or 0))
        data_rev_top.append(float(row.revenue or 0))

    # Pasar todo al template
    return render_template(
        "dashboard.html",
        total_clientes=total_clientes or 0,
        total_pedidos=total_pedidos or 0,
        total_pendientes=total_pendientes or 0,
        total_ingresos=float(total_ingresos or 0),
        labels_30=labels_30,
        data_30=data_30,
        labels_mes=labels_mes,
        data_mes=data_mes,
        top_clientes=top_clientes,
        # nuevos datasets para el gráfico Top Productos
        labels_top=labels_top,
        data_qty_top=data_qty_top,
        data_rev_top=data_rev_top,
    )