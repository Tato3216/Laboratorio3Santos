
# Proyecto 3 – Gestor de Clientes (Flask + MySQL) con Login

Este proyecto añade **autenticación** (login/logout) al gestor de clientes.
Se protege todo el CRUD: solo usuarios autenticados pueden acceder.

## Novedades
- Modelo `User` con email único y password hasheado (Werkzeug).
- Rutas de autenticación: `/auth/login`, `/auth/logout`.
- Protección con `@login_required` en vistas del módulo de clientes.
- Script `create_user.py` para crear usuarios desde consola.
- Navbar con sesión activa y botón de salir.

## Instalación rápida
1) Crear venv e instalar dependencias:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2) Configurar `.env` (ver `.env.example`).
3) Inicializar tablas:
```bash
python init_db.py
```
4) Crear usuario administrador:
```bash
python create_user.py --email admin@example.com --password Secret123!
```
5) Ejecutar la app:
```bash
flask --app app run --debug
```
Ir a: http://127.0.0.1:5000

## Exportar a Excel (opcional extra incluido)
Se añadió la ruta `/clients/export` que exporta a Excel (`.xlsx`) la lista de clientes activos.
