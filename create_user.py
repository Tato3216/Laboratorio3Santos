
import argparse
from app import create_app
from app.models import db, User

def main():
    parser = argparse.ArgumentParser(description="Crear usuario para el sistema")
    parser.add_argument("--email", required=True, help="Email del usuario (único)")
    parser.add_argument("--password", required=True, help="Contraseña en texto plano (se guardará hasheada)")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if User.query.filter_by(email=args.email.lower()).first():
            print("❌ Ya existe un usuario con ese email.")
            return
        u = User(email=args.email.lower())
        u.set_password(args.password)
        db.session.add(u)
        db.session.commit()
        print("✅ Usuario creado:", args.email)

if __name__ == "__main__":
    main()
