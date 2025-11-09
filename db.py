import sqlite3
import logging


DB_PATH = "/home/bytheg/vport/vport.db"


# --- Inicialización DB ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
           	"id"	TEXT NOT NULL,
           	"nombre"	TEXT,
           	"ap"	TEXT,
           	"am"	TEXT,
            "pwd"	TEXT,
           	"email"	TEXT,
           	"cell"	TEXT,
           	"tipoId"	INTEGER NOT NULL,
           	"fecha"	DATETIME DEFAULT CURRENT_TIMESTAMP,
           	"activo"	INTEGER NOT NULL DEFAULT 1,
           	"Operador"	INTEGER NOT NULL DEFAULT 0,
           	PRIMARY KEY("id"),
           	FOREIGN KEY("tipoId") REFERENCES "tipoUsuario"("id")
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tipoUsuario (
            "id"	INTEGER,
           	"tipo"	TEXT,
           	PRIMARY KEY("id")
        )
        """)
    conn.commit()
    conn.close()


# --- CRUD básico ---
def add_usuario(
    id, nombre, ap, am, pwd, email, cell="", tipoId=2, activo=1, operador=0
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        INSERT OR REPLACE INTO usuarios (id, nombre, ap, am, pwd, email,
        cell, tipoId, activo, operador) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (id, nombre, ap, am, pwd, email, cell, tipoId, activo, operador),
    )
    conn.commit()
    conn.close()
    logging.info(f"🆕 Usuario agregado: {id}, {nombre}")


def update_usuario(id, nombre, tipoId, activo):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE usuarios SET nombre=?, tipoId=?, activo=? WHERE id=?",
        (nombre, tipoId, activo, id),
    )
    conn.commit()
    conn.close()


def remove_usuario(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM usuarios WHERE id=?", (id,))
    conn.commit()
    conn.close()


def list_usuarios():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
                SELECT usr.id, usr.nombre, usr.ap, usr.am, tu.tipo,
                                usr.activo, usr.email,usr.pwd FROM usuarios AS usr
                INNER JOIN tipoUsuario AS tu
                ON usr.tipoId = tu.id
                """)
    usuarios = c.fetchall()
    conn.close()
    return usuarios


def tabla_tipoUsuario():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT * FROM tipoUsuario")
        tipoUsuario = c.fetchall()
        conn.close()
        return tipoUsuario

    except Exception as e:
        logging.error(f"⚠️ Error en tabla_tipoUsuarios: {e}")


def usuario_byId(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE id=?", (id,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == 1


def is_usuario_activo(id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT activo FROM usuarios WHERE id=?", (id,))
    row = c.fetchone()
    conn.close()
    print(f"row : {row} | row[0]: {row[0]}")
    return row is not None and row[0] == 1
