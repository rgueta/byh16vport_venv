import serial
import sqlite3
import threading
import time
import logging
import os
from buzzer import BuzzerManager

# --- Configuración general ---
DB_PATH = "/home/bytheg/vport/vport.db"
PORT = "/dev/serial0"
BAUD = 9600

# Valores que generan lecturas tardadas o vasura
# READ_INTERVAL = 0.1  # segundos entre lecturas
# DEBOUNCE_TIME = 2.0  # tiempo mínimo entre lecturas del mismo ID

# Valores nuevos a prueba
READ_INTERVAL = 0.05  # intervalo de lectura rápida
DEBOUNCE_TIME = 1.5  # no leer la misma tarjeta antes de 1.5s

learn_mode = False  # modo aprendizaje activable desde el panel
reader_running = True

_last_id = None
_last_time = 0

buzzer = BuzzerManager()


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


# --- Lectura UART (RDM6300) ---
def start_reader(callback):
    """Inicia el hilo de lectura NFC (por UART)."""
    global reader_running, _last_id, _last_time
    reader_running = True
    logging.info(f"📡 Lector NFC UART iniciado en {PORT}")

    def reader_loop():
        global _last_id, _last_time
        try:
            with serial.Serial(PORT, BAUD, timeout=0.05) as ser:
                buffer = b""
                while reader_running:
                    if ser.in_waiting:
                        byte = ser.read()
                        if not byte:
                            continue

                        # Inicio de trama
                        if byte == b"\x02":
                            buffer = b"\x02"
                            continue

                        # Acumulación
                        if buffer:
                            buffer += byte

                            # Fin de trama
                            if byte == b"\x03":
                                frame_len = len(buffer)

                                if frame_len == 14:
                                    try:
                                        id_raw = buffer[3:11]
                                        id = (
                                            id_raw.decode("ascii", errors="ignore")
                                            .strip()
                                            .upper()
                                        )

                                        if not all(c in "0123456789ABCDEF" for c in id):
                                            logging.warning(
                                                f"⚠️ ID no hexadecimal: {id}"
                                            )
                                            buffer = b""
                                            continue

                                        now = time.time()
                                        if (
                                            id != _last_id
                                            or (now - _last_time) > DEBOUNCE_TIME
                                        ):
                                            _last_id = id
                                            _last_time = now
                                            logging.info(
                                                f"🎫 Tarjeta detectada ID={id}"
                                            )
                                            buzzer.alert_pattern("success")
                                            handle_id(id, callback)
                                        else:
                                            logging.debug(
                                                f"⏳ ID repetido ignorado: {id}"
                                            )

                                    except Exception as e:
                                        logging.warning(
                                            f"⚠️ Error decodificando ID: {e}"
                                        )
                                else:
                                    logging.debug(
                                        f"⚠️ Trama ignorada (len={frame_len}): {buffer.hex(' ')}"
                                    )

                                buffer = b""

                        if len(buffer) > 20:
                            buffer = b""

                    else:
                        time.sleep(READ_INTERVAL)
        except serial.SerialException as e:
            logging.error(f"❌ Error abriendo puerto serial {PORT}: {e}")
        except Exception as e:
            logging.error(f"❌ Error crítico en lector NFC: {e}")

    threading.Thread(target=reader_loop, daemon=True).start()


def handle_id(id, callback):
    global learn_mode
    """Ejecuta el callback que viene del servidor."""
    try:
        # if is_usuario_activo(id):
        if learn_mode:
            add_usuario(id, f"Nueva tarjeta ({id})", "usuario", 1)
            logging.info(f"🧠 Modo aprendizaje: tarjeta {id} agregada automáticamente")
        if callback:
            callback(id)
        else:
            logging.warning("⚠️ No hay callback asignado para procesar el ID.")
    except Exception as e:
        logging.error(f"⚠️ Error ejecutando callback NFC: {e}")


def stop_reader():
    """Detiene la lectura del módulo NFC"""
    global reader_running
    reader_running = False
    logging.info("🛑 Lector NFC detenido")
