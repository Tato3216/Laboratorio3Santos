# app/products_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from sqlalchemy import asc, desc, func
from sqlalchemy.exc import IntegrityError
from .models import db, Product

products_bp = Blueprint("products", __name__)

def _read_form():
    # Permitimos SKU vacío (None) si quieres opcional
    sku = (request.form.get("sku") or "").strip()
    sku = sku or None
    name = (request.form.get("name") or "").strip()
    price = request.form.get("price", type=float) or 0.0
    desc = (request.form.get("description") or "").strip()
    return sku, name, price, desc


@products_bp.route("/products")
@login_required
def list_products():
    q = (request.args.get("q") or "").strip()
    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter((Product.name.ilike(like)) | (Product.sku.ilike(like)))
    items = query.order_by(asc(Product.name)).all()
    return render_template("products_list.html", products=items, q=q)


@products_bp.route("/products/new", methods=["GET", "POST"])
@login_required
def create_product():
    if request.method == "POST":
        sku, name, price, desc = _read_form()

        if not name:
            flash("El nombre es obligatorio.", "danger")
            # re-render conservando valores escritos
            fake = type("P", (), {"sku": sku, "name": name, "price": price, "description": desc})
            return render_template("product_form.html", product=fake)

        # Validación de SKU duplicado (case-insensitive)
        if sku:
            dup = Product.query.filter(func.lower(Product.sku) == sku.lower()).first()
            if dup:
                flash(f"El SKU '{sku}' ya existe en otro producto.", "danger")
                fake = type("P", (), {"sku": sku, "name": name, "price": price, "description": desc})
                return render_template("product_form.html", product=fake)

        try:
            p = Product(sku=sku, name=name, price=price, description=desc, is_active=True)
            db.session.add(p)
            db.session.commit()
            flash("Producto creado.", "success")
            return redirect(url_for("products.list_products"))
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo guardar: SKU duplicado.", "danger")
            fake = type("P", (), {"sku": sku, "name": name, "price": price, "description": desc})
            return render_template("product_form.html", product=fake)

    return render_template("product_form.html", product=None)


@products_bp.route("/products/<int:pid>/edit", methods=["GET", "POST"])
@login_required
def edit_product(pid):
    p = Product.query.get_or_404(pid)

    if request.method == "POST":
        sku, name, price, desc = _read_form()

        if not name:
            flash("El nombre es obligatorio.", "danger")
            # reflejar lo intentado
            p.sku, p.name, p.price, p.description = sku, name, price, desc
            return render_template("product_form.html", product=p)

        # Validación de colisión de SKU con OTRO producto
        if sku:
            dup = (Product.query
                   .filter(func.lower(Product.sku) == sku.lower(), Product.id != p.id)
                   .first())
            if dup:
                flash(f"El SKU '{sku}' ya está usado por otro producto.", "danger")
                p.sku, p.name, p.price, p.description = sku, name, price, desc
                return render_template("product_form.html", product=p)

        try:
            p.sku = sku
            p.name = name
            p.price = price
            p.description = desc
            db.session.commit()
            flash("Producto actualizado.", "success")
            return redirect(url_for("products.list_products"))
        except IntegrityError:
            db.session.rollback()
            flash("No se pudo guardar: SKU duplicado.", "danger")
            p.sku, p.name, p.price, p.description = sku, name, price, desc
            return render_template("product_form.html", product=p)

    return render_template("product_form.html", product=p)


# API simple para autocompletar/buscar
@products_bp.route("/api/products")
@login_required
def api_products():
    q = (request.args.get("q") or "").strip()
    query = Product.query
    if q:
        like = f"%{q}%"
        query = query.filter((Product.name.ilike(like)) | (Product.sku.ilike(like)))
    res = [
        {"id": p.id, "sku": p.sku, "name": p.name, "price": float(p.price)}
        for p in query.order_by(asc(Product.name)).limit(50)
    ]
    return jsonify(res)


@products_bp.route("/api/products/<int:pid>")
@login_required
def api_product_detail(pid):
    p = Product.query.get_or_404(pid)
    return jsonify({"id": p.id, "sku": p.sku, "name": p.name, "price": float(p.price)})