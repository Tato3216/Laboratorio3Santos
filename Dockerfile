FROM registry.access.redhat.com/ubi9/python-311
WORKDIR /opt/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

# ✅ SQLite en /tmp, siempre escribible en OpenShift
ENV SQLALCHEMY_DATABASE_URI=sqlite:////tmp/app.db \
    FLASK_APP=app.py \
    PORT=8080

EXPOSE 8080
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
