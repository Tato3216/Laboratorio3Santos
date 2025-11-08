from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import desc
from datetime import datetime
from .models import db, Order, Payment

payments_bp = Blueprint("payments", __name__)

# Lista de pagos + formulario de alta por pedido
@payments_bp.route("/orders/<int:order_id>/payments", methods=["GET", "POST"])
@login_required
def order_payments(order_id):
    order = Order.query.get_or_404(order_id)

    if request.method == "POST":
        try:
            amount = request.form.get("amount", type=float)
            if amount is None or amount <= 0:
                raise ValueError("El monto debe ser positivo.")
            method = request.form.get("method", "efectivo")
            reference = (request.form.get("reference") or "").strip()
            notes = (request.form.get("notes") or "").strip()
            paid_at_s = request.form.get("paid_at")
            paid_at = datetime.fromisoformat(paid_at_s) if paid_at_s else datetime.utcnow()

            p = Payment(order_id=order.id, amount=amount, method=method,
                        reference=reference, notes=notes, paid_at=paid_at)
            db.session.add(p)
            db.session.commit()
            flash("Pago registrado.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"No se pudo registrar el pago: {e}", "danger")

        return redirect(url_for("payments.order_payments", order_id=order.id))

    payments = Payment.query.filter_by(order_id=order.id) \
                            .order_by(desc(Payment.paid_at)).all()
    return render_template("payments_by_order.html", order=order, payments=payments)

# Eliminar pago
@payments_bp.route("/payments/<int:payment_id>/delete", methods=["POST"])
@login_required
def delete_payment(payment_id):
    p = Payment.query.get_or_404(payment_id)
    order_id = p.order_id
    db.session.delete(p)
    db.session.commit()
    flash("Pago eliminado.", "success")
    return redirect(url_for("payments.order_payments", order_id=order_id))