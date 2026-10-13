import os
import shutil
import sqlite3
from flask import current_app, g
from werkzeug.security import generate_password_hash

CUENTAS_FICTICIAS = [
    ("S01", "S01", "Dra. Ana María Gómez (Solicitante 1)", "ClaveSegura123!", "SOLICITANTE", 1),
    ("S02", "S02", "Ing. Carlos Andrés Pérez (Solicitante 2)", "ClaveSegura123!", "SOLICITANTE", 1),
    ("C01", "C01", "Ing. Laura Sofía Martínez (Coordinadora)", "CoordSegura123!", "COORDINADOR", 1),
    ("T01", "T01", "Téc. Miguel Ángel Torres (Técnico 1)", "TecSegura123!", "TECNICO", 1),
    ("T02", "T02", "Téc. Jorge Luis Ramírez (Técnico 2)", "TecSegura123!", "TECNICO", 1),
]

def _resolve_sqlite_path(db_path: str) -> str:
    abs_p = os.path.abspath(db_path)
    if abs_p.startswith("/working_dir/"):
        tmp_p = "/tmp/" + os.path.basename(abs_p)
        if os.path.exists(abs_p) and not os.path.exists(tmp_p):
            shutil.copy2(abs_p, tmp_p)
        return tmp_p
    return abs_p

def get_db() -> sqlite3.Connection:
    if "db" not in g:
        raw_path = current_app.config["DATABASE"]
        os.makedirs(os.path.dirname(os.path.abspath(raw_path)), exist_ok=True)
        work_path = _resolve_sqlite_path(raw_path)
        conn = sqlite3.connect(work_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        g.db = conn
        g.db_raw_path = os.path.abspath(raw_path)
        g.db_work_path = work_path
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    raw_p = g.pop("db_raw_path", None)
    work_p = g.pop("db_work_path", None)
    if db is not None:
        db.close()
        if raw_p and work_p and raw_p != work_p and os.path.exists(work_p):
            shutil.copy2(work_p, raw_p)

def init_db(seed_users: bool = True):
    db = get_db()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    if seed_users:
        with db:
            for uid, uname, nombre, raw_pw, rol, activo in CUENTAS_FICTICIAS:
                existing = db.execute("SELECT id FROM usuarios WHERE id = ?", (uid,)).fetchone()
                if not existing:
                    pw_hash = generate_password_hash(raw_pw)
                    db.execute(
                        "INSERT INTO usuarios (id, username, nombre, password_hash, rol, activo) VALUES (?, ?, ?, ?, ?, ?)",
                        (uid, uname, nombre, pw_hash, rol, activo),
                    )
