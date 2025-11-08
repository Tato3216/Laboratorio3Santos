
import os
from urllib.parse import quote_plus
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")

    user = os.getenv("MYSQL_USER", "app_user")
    password = quote_plus(os.getenv("MYSQL_PASSWORD", ""))  # codifica @, !, etc.
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    dbname = os.getenv("MYSQL_DB", "clientes_db")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "SQLALCHEMY_DATABASE_URI",
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}",
    )
    SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO", "False") == "True"
    SQLALCHEMY_TRACK_MODIFICATIONS = os.getenv("SQLALCHEMY_TRACK_MODIFICATIONS", "False") == "True"
