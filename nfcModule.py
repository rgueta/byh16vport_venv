import serial
import threading
import time
import logging
from buzzer import BuzzerManager
import db

# --- Configuración general ---

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
            db.add_usuario(id, f"Nueva tarjeta ({id})", "usuario", 1)
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
