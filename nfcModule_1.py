import serial
import sqlite3
import threading
import time
import logging

DB_PATH = "/home/bytheg/vport/nfc_cards.db"
SERIAL_PORT = "/dev/serial0"  # UART principal del Pi (GPIO14/15)
BAUDRATE = 9600
READ_INTERVAL = 0.1  # segundos entre lecturas
DEBOUNCE_TIME = 2.0  # no repetir la misma tarjeta antes de 2s


# --- Inicialización base de datos ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            uid TEXT PRIMARY KEY,
            name TEXT,
            level TEXT,
            enabled INTEGER DEFAULT 1,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# --- CRUD ---
def add_card(uid, name="", level="user"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO cards (uid, name, level, enabled) VALUES (?, ?, ?, 1)",
        (uid, name, level),
    )
    conn.commit()
    conn.close()
    logging.info(f"🆕 Tarjeta agregada: {uid} ({name})")


def remove_card(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cards WHERE uid = ?", (uid,))
    conn.commit()
    conn.close()
    logging.info(f"❌ Tarjeta eliminada: {uid}")


def update_card(uid, name=None, level=None, enabled=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fields, values = [], []
    if name:
        fields.append("name = ?")
        values.append(name)
    if level:
        fields.append("level = ?")
        values.append(level)
    if enabled is not None:
        fields.append("enabled = ?")
        values.append(int(enabled))
    values.append(uid)
    c.execute(f"UPDATE cards SET {', '.join(fields)} WHERE uid = ?", values)
    conn.commit()
    conn.close()
    logging.info(f"✏️ Tarjeta actualizada: {uid}")


def list_cards():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM cards")
    cards = c.fetchall()
    conn.close()
    return cards


def is_card_allowed(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT enabled FROM cards WHERE uid = ?", (uid,))
    result = c.fetchone()
    conn.close()
    return result is not None and result[0] == 1


# --- Lector UART RDM6300 ---
def read_uid_from_serial(ser):
    """Lee 14 bytes del lector RDM6300 y devuelve el UID hexadecimal."""
    data = ser.read(14)  # RDM6300 siempre manda 14 bytes por lectura
    if len(data) == 14 and data[0] == 0x02 and data[-1] == 0x03:
        uid_hex = data[1:11].decode("ascii")  # bytes 1-10 son el UID ASCII HEX
        return uid_hex
    return None


def start_reader(callback):
    """Inicia lectura continua desde el lector RDM6300 UART"""
    init_db()
    last_uid = None
    last_time = 0

    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.2)
        logging.info(
            f"📡 Lector RDM6300 inicializado en {SERIAL_PORT} @ {BAUDRATE} bps"
        )
    except Exception as e:
        logging.error(f"🚫 No se pudo abrir el puerto serial: {e}")
        return

    while True:
        try:
            uid = read_uid_from_serial(ser)
            if uid:
                now = time.time()
                if uid != last_uid or (now - last_time) > DEBOUNCE_TIME:
                    last_uid = uid
                    last_time = now
                    logging.info(f"🎫 Tarjeta detectada UID={uid}")
                    callback(uid)
            time.sleep(READ_INTERVAL)
        except Exception as e:
            logging.error(f"⚠️ Error en lectura RDM6300: {e}")
            time.sleep(1)
