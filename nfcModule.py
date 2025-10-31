import serial
import sqlite3
import threading
import time
import logging
import os
from buzzer import BuzzerManager

# --- Configuración general ---
DB_PATH = "/home/bytheg/vport/nfc_cards.db"
PORT = "/dev/serial0"
BAUD = 9600
READ_INTERVAL = 0.1  # segundos entre lecturas
DEBOUNCE_TIME = 2.0  # tiempo mínimo entre lecturas del mismo UID
learn_mode = False  # modo aprendizaje activable desde el panel
reader_running = True

_last_uid = None
_last_time = 0

buzzer = BuzzerManager()


# --- Inicialización DB ---
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


# --- CRUD básico ---
def add_card(uid, name="Nueva tarjeta", level="user", enabled=1):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO cards (uid, name, level, enabled) VALUES (?, ?, ?, ?)",
        (uid, name, level, enabled),
    )
    conn.commit()
    conn.close()
    logging.info(f"🆕 Tarjeta agregada: {uid}")


def update_card(uid, name, level, enabled):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE cards SET name=?, level=?, enabled=? WHERE uid=?",
        (name, level, enabled, uid),
    )
    conn.commit()
    conn.close()


def remove_card(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cards WHERE uid=?", (uid,))
    conn.commit()
    conn.close()


def list_cards():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT uid, name, level, enabled, timestamp FROM cards")
    cards = c.fetchall()
    conn.close()
    return cards


def is_card_allowed(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT enabled FROM cards WHERE uid=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == 1


# --- Lectura UART (RDM6300) ---
def start_reader(callback):
    def reader():
        global _last_uid, _last_time
        logging.info(f"📡 Lector NFC UART iniciado en {PORT}")
        try:
            with serial.Serial(PORT, BAUD, timeout=0.2) as ser:
                buffer = b""
                while reader_running:
                    if ser.in_waiting:
                        byte = ser.read()
                        if byte == b"\x02":  # inicio del frame
                            buffer = b""
                        buffer += byte
                        if byte == b"\x03":  # fin del frame
                            if len(buffer) >= 14:
                                try:
                                    uid = buffer[3:11].decode("ascii").strip().upper()
                                    now = time.time()
                                    if (
                                        uid != _last_uid
                                        or (now - _last_time) > DEBOUNCE_TIME
                                    ):
                                        _last_uid = uid
                                        _last_time = now
                                        handle_uid(uid, callback)
                                    else:
                                        logging.debug(
                                            f"⏳ UID repetido ignorado: {uid}"
                                        )
                                except Exception as e:
                                    logging.warning(f"Error decodificando UID: {e}")
                            buffer = b""
                    time.sleep(READ_INTERVAL)
        except Exception as e:
            logging.error(f"❌ Error en lector NFC: {e}")

    threading.Thread(target=reader, daemon=True).start()


def handle_uid(uid, callback):
    global learn_mode
    if not uid:
        return
    # 🔊 Sonido al abrir puerta
    buzzer.alert_pattern("success")
    logging.info(f"🎫 UID detectado: {uid}")
    if is_card_allowed(uid):
        callback(uid)
    else:
        if learn_mode:
            add_card(uid, f"Nueva tarjeta ({uid})", "user", 1)
            logging.info(f"🧠 Modo aprendizaje: tarjeta {uid} agregada automáticamente")
        callback(uid)
