# app/orders_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app
from flask_login import login_required
from sqlalchemy import asc, desc
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph   # <- ya tienes Table, TableStyle
import os
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from .models import db, Client, Order, OrderItem, Product  # incluye Product

orders_bp = Blueprint("orders", __name__)

# -----------------------------
# LISTADO DE PEDIDOS
# -----------------------------
@orders_bp.route("/orders")
@login_required
def list_orders():
    status = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = 10

    query = Order.query.join(Client)
    if status:
        query = query.filter(Order.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Client.first_name.ilike(like)) |
            (Client.last_name.ilike(like)) |
            (Client.email.ilike(like))
        )

    pagination = query.order_by(desc(Order.created_at)).paginate(page=page, per_page=per_page)
    return render_template("orders_list.html", pagination=pagination, q=q, status=status)


# -------- util para leer filas de ítems sin perder ninguna --------
def _iter_items_from_form():
    descs  = request.form.getlist("item_description[]")
    qtys   = request.form.getlist("item_qty[]")
    prices = request.form.getlist("item_price[]")
    prods  = request.form.getlist("item_product_id[]")

    n = max(len(descs), len(qtys), len(prices), len(prods))
    for i in range(n):
        d   = (descs[i]  if i < len(descs)  else "").strip()
        q   = (qtys[i]   if i < len(qtys)   else "0")
        p   = (prices[i] if i < len(prices) else "0")
        pid = (prods[i]  if i < len(prods)  else "")
        # si la fila viene totalmente vacía, saltar
        if not d and not (pid and (q or p)):
            continue
        yield d, q, p, pid


# -----------------------------
# CREAR PEDIDO (con ítems)
# -----------------------------
@orders_bp.route("/orders/new", methods=["GET", "POST"])
@login_required
def create_order():
    clients  = Client.query.filter_by(is_deleted=False).order_by(asc(Client.first_name)).all()
    products = Product.query.order_by(Product.name.asc()).all()
    default_client_id = request.args.get("client_id", type=int)

    if request.method == "POST":
        client_id = request.form.get("client_id", type=int)
        status    = (request.form.get("status") or "pendiente").strip()
        notes     = (request.form.get("notes")  or "").strip()

        if not client_id:
            flash("Cliente e ítems son obligatorios.", "danger")
            return render_template("order_form.html", order=None, clients=clients, products=products, default_client_id=default_client_id)

        order = Order(client_id=client_id, status=status, notes=notes)
        db.session.add(order)
        db.session.flush()  # tener order.id

        # crear ítems
        for d, q, p, pid in _iter_items_from_form():
            try:
                qv = float(q or 0); pv = float(p or 0)
            except ValueError:
                qv = 0; pv = 0
            item = OrderItem(order_id=order.id, description=d or "", quantity=qv, unit_price=pv)
            if pid:
                try:
                    item.product_id = int(pid)
                except ValueError:
                    pass
            db.session.add(item)

        db.session.flush()
        order.recompute_total()
        db.session.commit()

        flash("Pedido creado.", "success")
        return redirect(url_for("orders.list_orders"))

    return render_template("order_form.html", order=None, clients=clients, products=products, default_client_id=default_client_id)


# -----------------------------
# EDITAR PEDIDO (con ítems)
# -----------------------------
@orders_bp.route("/orders/<int:order_id>/edit", methods=["GET", "POST"])
@login_required
def edit_order(order_id):
    order    = Order.query.get_or_404(order_id)
    clients  = Client.query.filter_by(is_deleted=False).order_by(asc(Client.first_name)).all()
    products = Product.query.order_by(Product.name.asc()).all()

    if request.method == "POST":
        order.client_id = request.form.get("client_id", type=int)
        order.status    = (request.form.get("status") or "pendiente").strip()
        order.notes     = (request.form.get("notes")  or "").strip()

        # borrar items actuales y recrear
        for it in list(order.items):
            db.session.delete(it)

        for d, q, p, pid in _iter_items_from_form():
            try:
                qv = float(q or 0); pv = float(p or 0)
            except ValueError:
                qv = 0; pv = 0
            it = OrderItem(order_id=order.id, description=d or "", quantity=qv, unit_price=pv)
            if pid:
                try:
                    it.product_id = int(pid)
                except ValueError:
                    pass
            db.session.add(it)

        db.session.flush()
        order.recompute_total()
        db.session.commit()

        flash("Pedido actualizado.", "success")
        return redirect(url_for("orders.list_orders"))

    return render_template("order_form.html", order=order, clients=clients, products=products)


# -----------------------------
# ELIMINAR PEDIDO (y todo lo relacionado)
# -----------------------------
@orders_bp.route("/orders/<int:order_id>/delete", methods=["POST"])
@login_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)  # items/pagos/seguimientos se eliminan por cascade
    db.session.commit()
    flash(f"Pedido #{order_id} eliminado.", "success")
    return redirect(url_for("orders.list_orders"))


# -----------------------------
# PEDIDOS POR CLIENTE
# -----------------------------
@orders_bp.route("/clients/<int:client_id>/orders")
@login_required
def client_orders(client_id):
    client = Client.query.get_or_404(client_id)
    page = request.args.get("page", 1, type=int)
    per_page = 10

    pagination = (Order.query
                  .filter(Order.client_id == client.id)
                  .order_by(Order.created_at.desc())
                  .paginate(page=page, per_page=per_page))

    return render_template("orders_by_client.html", client=client, pagination=pagination)


# -----------------------------
# FACTURA / COTIZACIÓN EN PDF
# -----------------------------
@orders_bp.route("/orders/<int:order_id>/invoice.pdf")
@login_required
def order_invoice_pdf(order_id):
    order = Order.query.get_or_404(order_id)
    client = order.client

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    margin_x = 20 * mm
    y = height - 20 * mm

    # Logo
    logo_path = os.path.join(current_app.static_folder, "img", "logo.png")
    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, margin_x, y - 22*mm, width=35*mm, height=22*mm,
                        preserveAspectRatio=True, mask='auto')
        except Exception:
            pass

    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - margin_x, y, "Pedido")
    c.setFont("Helvetica", 10)
    y -= 14
    c.drawRightString(width - margin_x, y, f"Número: #{order.id}")
    y -= 12
    c.drawRightString(
        width - margin_x, y,
        f"Fecha: {order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"
    )

    # Empresa
    y -= 10
    c.setFont("Helvetica-Bold", 11); c.drawString(margin_x, y, "Mobtech S.A.")
    c.setFont("Helvetica", 10)
    y -= 12; c.drawString(margin_x, y, "NIT: 1000030342")
    y -= 12; c.drawString(margin_x, y, "Dirección: Zona 10, Guatemala")
    y -= 12; c.drawString(margin_x, y, "Tel: +502 53623228  Email: ventas@mobtechgt.com")

    # Cliente
    y -= 20
    c.setFont("Helvetica-Bold", 11); c.drawString(margin_x, y, "Cliente")
    c.setFont("Helvetica", 10)
    y -= 12; c.drawString(margin_x, y, f"Nombre: {client.full_name()}")
    y -= 12; c.drawString(margin_x, y, f"Email: {client.email}")
    if client.phone:
        y -= 12; c.drawString(margin_x, y, f"Teléfono: {client.phone}")
    if client.address:
        y -= 12; c.drawString(margin_x, y, f"Dirección: {client.address}")

    # Título detalle
    y -= 20
    c.setFont("Helvetica-Bold", 11); c.drawString(margin_x, y, "Detalle")
    y -= 12

    # ===== Tabla con wrapping en descripción =====
    # Estilos de párrafo
    p_desc = ParagraphStyle(
        "desc", fontName="Helvetica", fontSize=10, leading=12,
        alignment=TA_LEFT, wordWrap="CJK"
    )
    p_num = ParagraphStyle(
        "num", fontName="Helvetica", fontSize=10, leading=12,
        alignment=TA_RIGHT
    )

    # Anchos de columnas
    col_w_qty   = 20 * mm
    col_w_unit  = 30 * mm
    col_w_total = 30 * mm
    col_w_desc  = (width - 2 * margin_x) - (col_w_qty + col_w_unit + col_w_total)

    # Encabezados
    data = [[
        Paragraph("<b>Descripción</b>", p_desc),
        Paragraph("<b>Cant.</b>", p_num),
        Paragraph("<b>P. Unitario (Q)</b>", p_num),
        Paragraph("<b>Importe (Q)</b>", p_num),
    ]]

    # Filas
    for it in order.items:
        qty   = float(it.quantity or 0)
        price = float(it.unit_price or 0)
        amount = qty * price
        desc_par = Paragraph((it.description or "").replace("\n", "<br/>"), p_desc)
        data.append([
            desc_par,
            Paragraph(f"{qty:.2f}", p_num),
            Paragraph(f"{price:.2f}", p_num),
            Paragraph(f"{amount:.2f}", p_num),
        ])

    if len(data) == 1:
        data.append([
            Paragraph(f"Pedido #{order.id} - Estado: {order.status}", p_desc),
            Paragraph("1.00", p_num),
            Paragraph(f"{float(order.total):.2f}", p_num),
            Paragraph(f"{float(order.total):.2f}", p_num),
        ])

    table = Table(
        data,
        colWidths=[col_w_desc, col_w_qty, col_w_unit, col_w_total],
        repeatRows=1
    )
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f3f5")),
        ('GRID',       (0,0), (-1,-1), 0.25, colors.grey),
        ('VALIGN',     (0,0), (-1,-1), 'TOP'),
        ('ALIGN',      (1,1), (-1,-1), 'RIGHT'),
    ]))

    # Pintar tabla
    w, h = table.wrapOn(c, width - 2*margin_x, y)
    table.drawOn(c, margin_x, y - h)
    y = y - h - 10

    # Notas
    if order.notes:
        c.setFont("Helvetica-Oblique", 9)
        txt = c.beginText(margin_x, y)
        txt.textLines(f"Notas:\n{order.notes}")
        c.drawText(txt)
        y = txt.getY() - 10

    # Totales
    c.line(margin_x, y, width - margin_x, y); y -= 14
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - margin_x, y, f"SUBTOTAL Q {float(order.total):.2f}")
    y -= 14
    paid = float(getattr(order, "paid_total", 0.0))
    c.setFont("Helvetica", 10)
    c.drawRightString(width - margin_x, y, f"Pagado     Q {paid:.2f}")
    y -= 14
    balance = float(getattr(order, "balance", float(order.total) - paid))
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(width - margin_x, y, f"SALDO      Q {balance:.2f}")

    # Pie
    y -= 24
    c.setFont("Helvetica", 9)
    c.drawString(margin_x, y, "Gracias por su compra.")
    c.showPage(); c.save()
    buffer.seek(0)

    filename = f"Pedido_{order.id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")