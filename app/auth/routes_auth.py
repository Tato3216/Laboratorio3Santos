
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from ..models import db, User

auth_bp = Blueprint("auth", __name__, template_folder="../templates")
login_manager = LoginManager()
login_manager.login_view = "auth.login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.is_active and user.check_password(password):
            login_user(user)
            flash("Sesión iniciada.", "success")
            next_url = request.args.get("next") or url_for("main.list_clients")
            return redirect(next_url)
        else:
            flash("Credenciales inválidas o usuario inactivo.", "danger")

    return render_template("login.html")

@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sesión finalizada.", "success")
    return redirect(url_for("auth.login"))
