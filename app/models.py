from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, Index
from werkzeug.security import generate_password_hash, check_password_hash
from decimal import Decimal

db = SQLAlchemy()

# Helper para normalizar a Decimal
def _D(val):
    """Convierte val a Decimal de forma segura."""
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    try:
        return Decimal(str(val))
    except Exception:
        return Decimal("0.00")

# =========================
# Usuarios
# =========================
class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)

    # Flask-Login
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)


# =========================
# Clientes
# =========================
class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name  = db.Column(db.String(100), nullable=False)
    email      = db.Column(db.String(255), nullable=False, unique=True)
    phone      = db.Column(db.String(30))
    company    = db.Column(db.String(150))
    address    = db.Column(db.String(255))
    notes      = db.Column(db.Text)
    is_deleted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_clients_search", "first_name", "last_name", "email", "phone", "company"),
    )

    orders = db.relationship("Order", backref="client", lazy=True)

    def full_name(self):
        return f"{self.first_name} {self.last_name}"


# =========================
# Pedidos
# =========================
class Order(db.Model):
    __tablename__ = "orders"

    id        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    status    = db.Column(db.Enum(
        "pendiente", "en_proceso", "enviado", "entregado", "cancelado",
        name="order_status"
    ), nullable=False, default="pendiente")
    total     = db.Column(db.Numeric(10, 2), nullable=False, default=0)  # caché
    notes     = db.Column(db.Text)

    created_at= db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at= db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    items    = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)
    payments = db.relationship("Payment",  backref="order", cascade="all, delete-orphan", lazy=True)

    def recompute_total(self):
        # Usa siempre Decimal para evitar mezclar con float
        self.total = sum(_D(it.quantity) * _D(it.unit_price) for it in self.items)

    @property
    def paid_total(self):
        total = Decimal("0.00")
        for p in self.payments:
            total += _D(p.amount)
        return total

    @property
    def balance(self):
        t = _D(self.total)
        return t - self.paid_total


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id    = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id  = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True, index=True)  # opcional
    description = db.Column(db.String(255), nullable=False)
    quantity    = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price  = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at  = db.Column(db.DateTime, server_default=func.now(), nullable=False)

    product = db.relationship("Product", backref="order_items")


# =========================
# Seguimientos (Calendar)
# =========================
class FollowUp(db.Model):
    __tablename__ = "followups"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id   = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    order_id    = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=True, index=True)
    kind        = db.Column(db.Enum("seguimiento", "entrega", "cobro", name="followup_kind"),
                            nullable=False, default="seguimiento")
    title       = db.Column(db.String(200), nullable=False)
    notes       = db.Column(db.Text)
    when_at     = db.Column(db.DateTime, nullable=False)
    done        = db.Column(db.Boolean, nullable=False, default=False)
    created_at  = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at  = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

Client.followups = db.relationship("FollowUp", backref="client", lazy=True, cascade="all, delete-orphan")
Order.followups  = db.relationship("FollowUp", backref="order",  lazy=True, cascade="all, delete-orphan")


# =========================
# Pagos
# =========================
class Payment(db.Model):
    __tablename__ = "payments"

    id        = db.Column(db.Integer, primary_key=True, autoincrement=True)
    order_id  = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    amount    = db.Column(db.Numeric(10, 2), nullable=False)
    method    = db.Column(db.Enum("efectivo", "transferencia", "tarjeta", "otro",
                                  name="payment_method"),
                          nullable=False, default="efectivo")
    reference = db.Column(db.String(120))
    notes     = db.Column(db.Text)
    paid_at   = db.Column(db.DateTime, nullable=False, server_default=func.now())
    created_at= db.Column(db.DateTime, nullable=False, server_default=func.now())


# =========================
# Productos
# =========================
class Product(db.Model):
    __tablename__ = "products"
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sku         = db.Column(db.String(60), unique=True, index=True)
    name        = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price       = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    is_active   = db.Column(db.Boolean, nullable=False, default=True)
    created_at  = db.Column(db.DateTime, server_default=func.now(), nullable=False)


# =========================
# Cotizaciones
# =========================
class Quote(db.Model):
    __tablename__ = "quotes"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    client_id   = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    status      = db.Column(db.Enum("borrador", "enviada", "aceptada", "rechazada", "vencida",
                                    name="quote_status"),
                            nullable=False, default="borrador")
    valid_until = db.Column(db.Date)
    total       = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    notes       = db.Column(db.Text)

    created_at  = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at  = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    items = db.relationship("QuoteItem", backref="quote", cascade="all, delete-orphan", lazy=True)

    def recompute_total(self):
        # Igual que en Order: todo con Decimal
        self.total = sum(_D(it.quantity) * _D(it.unit_price) for it in self.items)

    def to_order(self):
        """Construye un Order a partir de la cotización (no hace commit)."""
        order = Order(client_id=self.client_id, status="pendiente", notes=self.notes)
        for qi in self.items:
            oi = OrderItem(
                description=qi.description,
                quantity=qi.quantity,
                unit_price=qi.unit_price
            )
            if qi.product_id:
                oi.product_id = qi.product_id
            order.items.append(oi)
        order.recompute_total()
        return order


class QuoteItem(db.Model):
    __tablename__ = "quote_items"

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quote_id    = db.Column(db.Integer, db.ForeignKey("quotes.id"), nullable=False, index=True)
    product_id  = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True, index=True)  # opcional
    description = db.Column(db.String(255), nullable=False)
    quantity    = db.Column(db.Numeric(10, 2), nullable=False, default=1)
    unit_price  = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    created_at  = db.Column(db.DateTime, server_default=func.now(), nullable=False)

Client.quotes = db.relationship("Quote", backref="client", lazy=True, cascade="all, delete-orphan")