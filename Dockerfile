# Dockerfile
FROM registry.access.redhat.com/ubi9/python-311

WORKDIR /opt/app

# Requisitos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copia del código
COPY . .

# DB SQLite dentro del contenedor
RUN mkdir -p /opt/app/data

# Variables para que la app use SQLite y escuche en 8080
ENV SQLALCHEMY_DATABASE_URI=sqlite:////opt/app/data/app.db \
    FLASK_APP=app.py \
    PORT=8080

# Puerto requerido por OpenShift
EXPOSE 8080

# Ejecuta con Gunicorn apuntando al objeto Flask "app" definido en app.py
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
