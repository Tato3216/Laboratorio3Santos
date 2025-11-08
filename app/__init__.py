
from flask import Flask
from .config import Config
from .models import db
from .routes import bp as main_bp
from .auth.routes_auth import auth_bp, login_manager
from .orders_routes import orders_bp 
from .dashboard_routes import dashboard_bp
from .followups_routes import followups_bp
from .payments_routes import payments_bp
from .products_routes import products_bp
from .quotes_routes import quotes_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(orders_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(followups_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(quotes_bp)

    return app
