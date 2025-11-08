# app/quotes_routes.py
from flask import (
    Blueprint, render_template, request, redirect, url_for, flash,
    send_file, current_app
)
from flask_login import login_required
from sqlalchemy import asc, desc
from datetime import datetime
from io import BytesIO
import os
from decimal import Decimal

from .models import db, Client, Product, Quote, QuoteItem, Order, OrderItem

# PDF (ReportLab)
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

quotes_bp = Blueprint("quotes", __name__)

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def _iter_items_from_form():
    """Lee arrays del form sin perder filas, aunque vengan desalineados."""
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
        yield d, q, p, pid

def _valid_items_present():
    """Retorna True si hay al menos un ítem con descripción no vacía."""
    for d, q, p, pid in _iter_items_from_form():
        if d:
            return True
    return False

def _parse_date_yyyy_mm_dd(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).date()
    except ValueError:
        return None

def _to_decimal(x):
    """Convierte cualquier entrada a Decimal(2) de forma segura."""
    try:
        return Decimal(str(x)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")

# ---------------------------------------------------------
# Listado de cotizaciones
# ---------------------------------------------------------
@quotes_bp.route("/quotes")
@login_required
def list_quotes():
    status = (request.args.get("status") or "").strip()
    q      = (request.args.get("q") or "").strip()
    page   = request.args.get("page", 1, type=int)
    per_page = 10

    query = Quote.query.join(Client)
    if status:
        query = query.filter(Quote.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            (Client.first_name.ilike(like)) |
            (Client.last_name.ilike(like)) |
            (Client.email.ilike(like))
        )

    pagination = (query
                  .order_by(desc(Quote.created_at))
                  .paginate(page=page, per_page=per_page))

    return render_template("quotes_list.html",
                           pagination=pagination,
                           q=q, status=status)

# ---------------------------------------------------------
# Crear cotización
# ---------------------------------------------------------
@quotes_bp.route("/quotes/new", methods=["GET", "POST"])
@login_required
def create_quote():
    clients  = Client.query.filter_by(is_deleted=False).order_by(asc(Client.first_name)).all()
    products = Product.query.order_by(Product.name.asc()).all()
    default_client_id = request.args.get("client_id", type=int)

    if request.method == "POST":
        client_id   = request.form.get("client_id", type=int)
        status      = (request.form.get("status") or "borrador").strip()
        notes       = (request.form.get("notes")  or "").strip()
        valid_until = _parse_date_yyyy_mm_dd(request.form.get("valid_until"))

        if not client_id:
            flash("El cliente es obligatorio.", "danger")
            return render_template("quote_form.html", quote=None,
                                   clients=clients, products=products,
                                   default_client_id=default_client_id)

        if not _valid_items_present():
            flash("Agrega al menos un ítem con descripción.", "warning")
            return render_template("quote_form.html", quote=None,
                                   clients=clients, products=products,
                                   default_client_id=default_client_id)

        q = Quote(client_id=client_id, status=status, notes=notes, valid_until=valid_until)
        db.session.add(q)
        db.session.flush()  # conseguir q.id

        # items
        for d, qty, price, pid in _iter_items_from_form():
            if not d:
                continue
            qv = _to_decimal(qty)
            pv = _to_decimal(price)
            it = QuoteItem(quote_id=q.id, description=d, quantity=qv, unit_price=pv)
            if pid:
                try:
                    it.product_id = int(pid)
                except ValueError:
                    pass
            db.session.add(it)

        db.session.flush()
        q.recompute_total()
        db.session.commit()

        flash("Cotización creada.", "success")
        return redirect(url_for("quotes.list_quotes"))

    return render_template("quote_form.html",
                           quote=None, clients=clients, products=products,
                           default_client_id=default_client_id)

# ---------------------------------------------------------
# Editar cotización
# ---------------------------------------------------------
@quotes_bp.route("/quotes/<int:quote_id>/edit", methods=["GET", "POST"])
@login_required
def edit_quote(quote_id):
    quote    = Quote.query.get_or_404(quote_id)
    clients  = Client.query.filter_by(is_deleted=False).order_by(asc(Client.first_name)).all()
    products = Product.query.order_by(Product.name.asc()).all()

    if request.method == "POST":
        quote.client_id   = request.form.get("client_id", type=int)
        quote.status      = (request.form.get("status") or "borrador").strip()
        quote.notes       = (request.form.get("notes")  or "").strip()
        quote.valid_until = _parse_date_yyyy_mm_dd(request.form.get("valid_until"))

        # Validación: al menos un ítem
        if not _valid_items_present():
            flash("Agrega al menos un ítem con descripción.", "warning")
            return render_template("quote_form.html",
                                   quote=quote, clients=clients, products=products)

        # sustituimos items actuales por los nuevos (simple + robusto)
        for it in list(quote.items):
            db.session.delete(it)

        for d, qty, price, pid in _iter_items_from_form():
            if not d:
                continue
            qv = _to_decimal(qty)
            pv = _to_decimal(price)
            it = QuoteItem(quote_id=quote.id, description=d, quantity=qv, unit_price=pv)
            if pid:
                try:
                    it.product_id = int(pid)
                except ValueError:
                    pass
            db.session.add(it)

        db.session.flush()
        quote.recompute_total()
        db.session.commit()

        flash("Cotización actualizada.", "success")
        return redirect(url_for("quotes.list_quotes"))

    return render_template("quote_form.html",
                           quote=quote, clients=clients, products=products)

# ---------------------------------------------------------
# Eliminar cotización
# ---------------------------------------------------------
@quotes_bp.route("/quotes/<int:quote_id>/delete", methods=["POST"])
@login_required
def delete_quote(quote_id):
    q = Quote.query.get_or_404(quote_id)
    db.session.delete(q)
    db.session.commit()
    flash("Cotización eliminada.", "success")
    return redirect(url_for("quotes.list_quotes"))

# ---------------------------------------------------------
# Convertir cotización -> Pedido
# ---------------------------------------------------------
@quotes_bp.route("/quotes/<int:quote_id>/to-order", methods=["POST"])
@login_required
def quote_to_order(quote_id):
    q = Quote.query.get_or_404(quote_id)

    # Validación: que tenga items
    if not q.items:
        flash("La cotización no tiene ítems, no se puede convertir.", "warning")
        return redirect(url_for("quotes.edit_quote", quote_id=q.id))

    # Snapshot de ítems para evitar sorpresas si se toca la relación
    items_snapshot = list(q.items)

    # Crear Order a partir de la cotización
    order = Order(client_id=q.client_id, status="pendiente", notes=q.notes)
    for qi in items_snapshot:
        oi = OrderItem(
            description=qi.description,
            quantity=qi.quantity,
            unit_price=qi.unit_price
        )
        if qi.product_id:
            oi.product_id = qi.product_id
        order.items.append(oi)

    order.recompute_total()
    db.session.add(order)
    db.session.flush()  # para order.id

    # (opcional) marcar cotización como aceptada
    if q.status != "aceptada":
        q.status = "aceptada"

    db.session.commit()

    flash(f"Pedido #{order.id} creado desde la cotización.", "success")
    return redirect(url_for("orders.edit_order", order_id=order.id))

# ---------------------------------------------------------
# PDF de cotización (con manejo de textos largos)
# ---------------------------------------------------------
@quotes_bp.route("/quotes/<int:quote_id>/pdf")
@login_required
def quote_pdf(quote_id):
    q = Quote.query.get_or_404(quote_id)
    client = q.client

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    width, height = LETTER

    margin_x = 20 * mm
    y = height - 20 * mm

    # Logo
    logo_path = os.path.join(current_app.static_folder, "img", "logo.png")
    if os.path.exists(logo_path):
        try:
            c.drawImage(
                logo_path, margin_x, y - 22 * mm,
                width=35 * mm, height=22 * mm,
                preserveAspectRatio=True, mask='auto'
            )
        except Exception:
            pass

    # Encabezado
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(width - margin_x, y, "Cotización")
    c.setFont("Helvetica", 10)
    y -= 14
    c.drawRightString(width - margin_x, y, f"Número: Q-{q.id}")
    y -= 12
    fecha = q.created_at.strftime('%Y-%m-%d %H:%M') if q.created_at else datetime.utcnow().strftime('%Y-%m-%d %H:%M')
    c.drawRightString(width - margin_x, y, f"Fecha: {fecha}")
    if q.valid_until:
        y -= 12
        c.drawRightString(width - margin_x, y, f"Válida hasta: {q.valid_until.isoformat()}")

    # Tu empresa (ajústalo)
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

    # Items
    y -= 20
    c.setFont("Helvetica-Bold", 11); c.drawString(margin_x, y, "Detalle")
    y -= 12

    # Estilos de párrafo para ajustar texto
    p_desc = ParagraphStyle(
        "desc",
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        alignment=TA_LEFT,
        wordWrap="CJK",
    )
    p_num = ParagraphStyle(
        "num",
        fontName="Helvetica",
        fontSize=10,
        leading=12,
        alignment=TA_RIGHT,
    )

    # Anchos de columnas
    col_w_qty   = 20 * mm
    col_w_unit  = 30 * mm
    col_w_total = 30 * mm
    col_w_desc  = (width - 2 * margin_x) - (col_w_qty + col_w_unit + col_w_total)

    # Construcción de la tabla
    data = [[
        Paragraph("<b>Descripción</b>", p_desc),
        Paragraph("<b>Cant.</b>", p_num),
        Paragraph("<b>P. Unitario (Q)</b>", p_num),
        Paragraph("<b>Importe (Q)</b>", p_num),
    ]]

    for it in q.items:
        qty = float(it.quantity or 0)
        price = float(it.unit_price or 0)
        imp = qty * price
        desc_paragraph = Paragraph((it.description or "").replace("\n", "<br/>"), p_desc)
        data.append([
            desc_paragraph,
            Paragraph(f"{qty:.2f}", p_num),
            Paragraph(f"{price:.2f}", p_num),
            Paragraph(f"{imp:.2f}", p_num),
        ])

    if len(data) == 1:
        data.append([
            Paragraph(f"Cotización Q-{q.id}", p_desc),
            Paragraph("1.00", p_num),
            Paragraph(f"{float(q.total):.2f}", p_num),
            Paragraph(f"{float(q.total):.2f}", p_num),
        ])

    table = Table(
        data,
        colWidths=[col_w_desc, col_w_qty, col_w_unit, col_w_total],
        repeatRows=1
    )
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#f1f3f5")),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
    ]))

    # Pintar tabla
    w, h = table.wrapOn(c, width - 2 * margin_x, y)
    table.drawOn(c, margin_x, y - h)
    y = y - h - 10

    # Notas
    if q.notes:
        c.setFont("Helvetica-Oblique", 9)
        txt = c.beginText(margin_x, y)
        txt.textLines(f"Notas:\n{q.notes}")
        c.drawText(txt)
        y = txt.getY() - 10

    # Total
    c.line(margin_x, y, width - margin_x, y); y -= 14
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - margin_x, y, f"TOTAL Q {float(q.total):.2f}")

    # Pie
    y -= 24
    c.setFont("Helvetica", 9)
    c.drawString(margin_x, y, "Gracias por su preferencia. Esta cotización no constituye factura.")
    c.showPage(); c.save()
    buffer.seek(0)

    filename = f"cotizacion_{q.id}.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")