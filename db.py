import sqlite3
import logging, bcrypt, json, os


DB_PATH = "/home/bytheg/vport/vport.db"
CONFIG_FILE = "config.json"


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


def hash_password(password):
    """Encriptar contraseña"""
    # Generar salt y hash la contraseña
    salt = bcrypt.gensalt()
    password_hash = bcrypt.hashpw(password.encode("utf-8"), salt)
    return password_hash.decode("utf-8")


def verify_password(password, password_hash):
    """Verificar contraseña encriptada"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception as e:
        logger.error(f"Error al verificar contraseña: {e}")
        return False


def verificar_usuario(username, password):
    """Verificar credenciales de usuario"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT usr.*, tu.tipo
            FROM usuarios AS usr
            INNER JOIN tipoUsuario AS tu ON usr.tipoId = tu.id
            WHERE usr.nombre = ?""",
            (username,),
        )
        usuario = c.fetchone()
        conn.close()

        if usuario and verify_password(password, usuario["pwd"]):
            return usuario
        return None

    except Exception as e:
        logger.error(f"Error al verificar usuario: {e}")
        return None


# --- CRUD básico ---
def add_usuario(
    id, nombre, ap, am, pwd, email, cell="", tipoId=2, activo=1, operador=0
):
    try:
        pwd_hash = hash_password(pwd)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            """
            INSERT OR REPLACE INTO usuarios (id, nombre, ap, am, pwd, email,
            cell, tipoId, activo, operador) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (id, nombre, ap, am, pwd_hash, email, cell, tipoId, activo, operador),
        )
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        logging.info(f"🆕 Usuario agregado: {id}, {nombre}")

        return user_id
    except sqlite3.IntegrityError:
        raise ValueError("El usuario ya existe")
    except Exception as e:
        logger.error(f"Error al crear usuario: {e}")
        raise


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
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
                SELECT usr.*, tu.tipo FROM usuarios AS usr
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
    conn.row_factory = sqlite3.Row
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


# ==========  Configuracion ============================


def load_config():
    """Cargar configuración desde el archivo JSON"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}


def save_config(config_dict):
    """Guardar configuración en el archivo JSON"""
    with open(CONFIG_FILE, "w") as f:
        json.dump(config_dict, f, indent=4)


def verificarUsuarioCfg(username, pwd):
    try:
        # Leer el archivo JSON existente
        with open("config.json", "r", encoding="utf-8") as f:
            datos = json.load(f)

        if datos["admin"]["username"] == username and datos["admin"]["password"] == pwd:
            return {
                "id": datos["admin"]["username"],
                "nombre": datos["admin"]["username"],
                "tipo": datos["admin"]["username"],
            }
        else:
            return None

    except FileNotFoundError:
        print(f"El archivo config.json no existe")
    except json.JSONDecodeError:
        print("Error al decodificar el JSON")
    except Exception as e:
        print(f"Error inesperado: {e}")
