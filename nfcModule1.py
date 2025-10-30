#!/usr/bin/env python3
import sqlite3
import threading
import time
import logging
import serial
import binascii

DB_PATH = "/home/bytheg/vport/nfc_cards.db"


# ---------------------------------------------------------------------
# 🗃️ Inicialización de la base de datos
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# ✏️ Funciones CRUD
# ---------------------------------------------------------------------
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


# ---------------------------------------------------------------------
# 🔍 Lector NFC vía UART (GPIO14 TX / GPIO15 RX)
# ---------------------------------------------------------------------
# Requiere que habilites UART en Raspberry Pi:
#   sudo raspi-config → Interface Options → Serial Port → disable login shell → enable hardware serial

UART_PORT = "/dev/serial0"  # o "/dev/ttyAMA0"
UART_BAUD = 115200  # puede variar: PN532=115200, MFRC522=9600


def start_reader(callback):
    """Inicia el lector NFC conectado por UART"""
    logging.info("📡 Iniciando lector NFC por UART...")
    try:
        ser = serial.Serial(UART_PORT, UART_BAUD, timeout=0.1)
    except serial.SerialException as e:
        logging.error(f"❌ Error al abrir puerto serial {UART_PORT}: {e}")
        return

    while True:
        try:
            data = ser.read(16)
            if data:
                uid = binascii.hexlify(data).decode().upper()
                # Si el lector entrega datos con encabezados o ruido,
                # podrías filtrar el UID real aquí.
                logging.info(f"🎫 Tarjeta detectada UID={uid}")
                callback(uid)
            time.sleep(0.2)
        except Exception as e:
            logging.error(f"⚠️ Error en lectura NFC: {e}")
            time.sleep(1)


# ---------------------------------------------------------------------
# 🧠 Ejemplo de uso (solo para prueba directa)
# ---------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )
    init_db()

    def test_callback(uid):
        if is_card_allowed(uid):
            logging.info(f"✅ Acceso permitido: {uid}")
        else:
            logging.warning(f"🚫 Acceso denegado: {uid}")

    start_reader(test_callback)
