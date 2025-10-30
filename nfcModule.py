import serial
import time
import logging
import sqlite3

DB_PATH = "/home/bytheg/vport/nfc_cards.db"
SERIAL_PORT = "/dev/serial0"
BAUDRATE = 9600

# --- Control de rebote NFC ---
last_uid = None
last_time = 0
DEBOUNCE_TIME = 3  # segundos


# --- Inicialización de DB ---
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


# --- CRUD simplificado (sin cambios) ---
def is_card_allowed(uid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT enabled FROM cards WHERE uid = ?", (uid,))
    result = c.fetchone()
    conn.close()
    return result is not None and result[0] == 1


# --- Lector RDM6300 ---
def start_reader(callback):
    global last_uid, last_time
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.5)
        logging.info(f"📡 Lector RDM6300 activo en {SERIAL_PORT}")
        buffer = ""
        while True:
            data = ser.read().decode(errors="ignore")
            if data == "\x02":  # inicio
                buffer = ""
            elif data == "\x03":  # fin
                if len(buffer) >= 10:
                    uid = buffer[:10]
                    now = time.time()

                    # --- Anti-rebote ---
                    if uid != last_uid or (now - last_time) > DEBOUNCE_TIME:
                        last_uid = uid
                        last_time = now
                        logging.info(f"🎫 Tarjeta detectada UID={uid}")
                        callback(uid)
                    else:
                        logging.debug(f"↩️ Lectura ignorada (duplicada): {uid}")
            else:
                buffer += data
    except Exception as e:
        logging.error(f"⚠️ Error en lectura RDM6300: {e}")
        time.sleep(1)
