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

# Valores que generan lecturas tardadas o vasura
# READ_INTERVAL = 0.1  # segundos entre lecturas
# DEBOUNCE_TIME = 2.0  # tiempo mínimo entre lecturas del mismo UID

# Valores nuevos a prueba
READ_INTERVAL = 0.05  # intervalo de lectura rápida
DEBOUNCE_TIME = 1.5  # no leer la misma tarjeta antes de 1.5s

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
    print(f"row : {row} | row[0]: {row[0]}")
    return row is not None and row[0] == 1


# --- Lectura UART (RDM6300) ---
def start_reader_(callback):
    global _last_uid, _last_time
    logging.info(f"📡 Lector NFC UART iniciado en {PORT}")

    try:
        with serial.Serial(PORT, BAUD, timeout=0.05) as ser:
            buffer = b""
            while reader_running:
                try:
                    if ser.in_waiting:
                        byte = ser.read()
                        if not byte:
                            continue

                        # Inicio de trama
                        if byte == b"\x02":
                            buffer = b"\x02"
                            continue

                        # Si ya hay buffer, agregamos bytes
                        if buffer:
                            buffer += byte

                            # Fin de trama detectado
                            if byte == b"\x03":
                                frame_len = len(buffer)

                                # Verificación de longitud esperada
                                if frame_len == 14 and isinstance(
                                    buffer, (bytes, bytearray)
                                ):
                                    try:
                                        uid_raw = buffer[3:11]
                                        if not uid_raw or len(uid_raw) != 8:
                                            logging.warning(
                                                f"⚠️ UID vacío o corrupto (raw={buffer.hex(' ')})"
                                            )
                                            buffer = b""
                                            continue

                                        # Convertir UID a texto
                                        uid = (
                                            uid_raw.decode("ascii", errors="ignore")
                                            .strip()
                                            .upper()
                                        )

                                        # Validar que sea HEX
                                        if not all(
                                            c in "0123456789ABCDEF" for c in uid
                                        ):
                                            logging.warning(
                                                f"⚠️ UID no hexadecimal: {uid} (raw={buffer.hex(' ')})"
                                            )
                                            buffer = b""
                                            continue

                                        now = time.time()
                                        if (
                                            uid != _last_uid
                                            or (now - _last_time) > DEBOUNCE_TIME
                                        ):
                                            _last_uid = uid
                                            _last_time = now
                                            logging.info(
                                                f"🎫 Tarjeta detectada UID={uid}"
                                            )
                                            buzzer.alert_pattern("success")
                                            handle_uid(uid, callback)
                                        else:
                                            logging.debug(
                                                f"⏳ UID repetido ignorado: {uid}"
                                            )

                                    except Exception as e:
                                        logging.warning(
                                            f"⚠️ Error interno decodificando UID: {e}"
                                        )
                                else:
                                    logging.debug(
                                        f"⚠️ Trama ignorada (len={frame_len}): {buffer.hex(' ')}"
                                    )

                                buffer = b""  # Limpiar para siguiente trama

                        # Limpiar buffers si se desbordan
                        if len(buffer) > 20:
                            logging.debug(
                                "🧹 Trama descartada: exceso de bytes sin fin (0x03)"
                            )
                            buffer = b""

                    else:
                        time.sleep(READ_INTERVAL)

                except Exception as e:
                    logging.error(f"⚠️ Error interno en bucle lector: {e}")
                    time.sleep(0.2)

    except Exception as e:
        logging.error(f"❌ Error crítico en lector NFC: {e}")


def start_reader_(callback):
    """Inicia la lectura del módulo RDM6300 UART"""
    global reader_running, _last_uid, _last_time
    reader_running = True

    def reader():
        global _last_uid, _last_time
        logging.info(f"📡 Lector NFC UART iniciado en {PORT}")

        try:
            with serial.Serial(PORT, BAUD, timeout=0.05) as ser:
                buffer = b""

                while reader_running:
                    try:
                        if ser.in_waiting:
                            byte = ser.read()
                            if not byte:
                                continue

                            # Inicio de trama (0x02)
                            if byte == b"\x02":
                                buffer = b"\x02"
                                continue

                            # Acumulamos bytes si estamos dentro de una trama
                            if buffer:
                                buffer += byte

                                # Fin de trama detectado (0x03)
                                if byte == b"\x03":
                                    frame_len = len(buffer)

                                    # RDM6300 envía 14 bytes exactos por lectura válida
                                    if frame_len == 14 and isinstance(
                                        buffer, (bytes, bytearray)
                                    ):
                                        try:
                                            uid_raw = buffer[3:11]

                                            # Validación básica de longitud
                                            if not uid_raw or len(uid_raw) != 8:
                                                logging.warning(
                                                    f"⚠️ UID vacío o corrupto (raw={buffer.hex(' ')})"
                                                )
                                                buffer = b""
                                                continue

                                            # Convertir UID a ASCII
                                            uid = (
                                                uid_raw.decode("ascii", errors="ignore")
                                                .strip()
                                                .upper()
                                            )

                                            # Validar que sea hexadecimal (EM4100 -> HEX)
                                            if not all(
                                                c in "0123456789ABCDEF" for c in uid
                                            ):
                                                logging.warning(
                                                    f"⚠️ UID no hexadecimal: {uid} (raw={buffer.hex(' ')})"
                                                )
                                                buffer = b""
                                                continue

                                            # ⏱️ Anti-rebote
                                            now = time.time()
                                            if (
                                                uid != _last_uid
                                                or (now - _last_time) > DEBOUNCE_TIME
                                            ):
                                                _last_uid = uid
                                                _last_time = now
                                                logging.info(
                                                    f"🎫 Tarjeta detectada UID={uid}"
                                                )

                                                buzzer.alert_pattern("success")
                                                handle_uid(uid, callback)
                                            else:
                                                logging.debug(
                                                    f"⏳ UID repetido ignorado: {uid}"
                                                )

                                        except Exception as e:
                                            logging.warning(
                                                f"⚠️ Error interno decodificando UID: {e}"
                                            )
                                    else:
                                        logging.debug(
                                            f"⚠️ Trama ignorada (len={frame_len}): {buffer.hex(' ')}"
                                        )

                                    buffer = b""  # Limpiar para siguiente trama

                            # Seguridad: si hay exceso de bytes sin cierre, limpiar
                            if len(buffer) > 20:
                                logging.debug(
                                    "🧹 Trama descartada: exceso de bytes sin fin (0x03)"
                                )
                                buffer = b""

                        else:
                            time.sleep(READ_INTERVAL)

                    except Exception as e:
                        logging.error(f"⚠️ Error interno en bucle lector: {e}")
                        time.sleep(0.2)

        except Exception as e:
            logging.error(f"❌ Error crítico en lector NFC: {e}")

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    return t


def start_reader(callback):
    """Inicia el hilo de lectura NFC (por UART)."""
    global reader_running, _last_uid, _last_time
    reader_running = True
    logging.info(f"📡 Lector NFC UART iniciado en {PORT}")

    def reader_loop():
        global _last_uid, _last_time
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
                                        uid_raw = buffer[3:11]
                                        uid = (
                                            uid_raw.decode("ascii", errors="ignore")
                                            .strip()
                                            .upper()
                                        )

                                        if not all(
                                            c in "0123456789ABCDEF" for c in uid
                                        ):
                                            logging.warning(
                                                f"⚠️ UID no hexadecimal: {uid}"
                                            )
                                            buffer = b""
                                            continue

                                        now = time.time()
                                        if (
                                            uid != _last_uid
                                            or (now - _last_time) > DEBOUNCE_TIME
                                        ):
                                            _last_uid = uid
                                            _last_time = now
                                            logging.info(
                                                f"🎫 Tarjeta detectada UID={uid}"
                                            )
                                            buzzer.alert_pattern("success")
                                            handle_uid(uid, callback)
                                        else:
                                            logging.debug(
                                                f"⏳ UID repetido ignorado: {uid}"
                                            )

                                    except Exception as e:
                                        logging.warning(
                                            f"⚠️ Error decodificando UID: {e}"
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


def handle_uid_(uid, callback):
    global learn_mode
    if not uid:
        return
    logging.info(f"🎫 UID detectado: {uid}")
    # if is_card_allowed(uid):
    if 1 == 1:
        logging.info(f"Guetin entro al llamado!")
        callback(uid)
    else:
        if learn_mode:
            add_card(uid, f"Nueva tarjeta ({uid})", "user", 1)
            logging.info(f"🧠 Modo aprendizaje: tarjeta {uid} agregada automáticamente")
        callback(uid)


def handle_uid(uid, callback):
    """Ejecuta el callback que viene del servidor."""
    try:
        if callback:
            callback(uid)
        else:
            logging.warning("⚠️ No hay callback asignado para procesar el UID.")
    except Exception as e:
        logging.error(f"⚠️ Error ejecutando callback NFC: {e}")


def stop_reader():
    """Detiene la lectura del módulo NFC"""
    global reader_running
    reader_running = False
    logging.info("🛑 Lector NFC detenido")
