#!/usr/bin/env python3
# version 5: video + control de cerradura magnética + configuración externa

from flask import Flask, Response, render_template, request, jsonify, abort
from picamera2 import Picamera2
import io, threading, time, logging, os, json, sys

# ------------------------------------------------------------------
# 🔧 Cargar configuración desde config.json
# ------------------------------------------------------------------
DEFAULT_CONFIG = {
    "camera": {"resolution": [640, 480], "format": "XBGR8888", "frame_interval": 0.05},
    "server": {"host": "0.0.0.0", "port": 5000, "debug": False},
    "lock": {"gpio_pin": 17, "active_high": True, "unlock_duration": 3.0},
    "security": {"api_token": "1234"},
    "logging": {"level": "INFO"},
}


def load_config(path="config.json"):
    """Carga configuración desde JSON, aplica valores por defecto si falta algo"""
    config = DEFAULT_CONFIG.copy()
    try:
        with open(path, "r") as f:
            user_cfg = json.load(f)
            # Mezclar niveles anidados (shallow merge)
            for key, val in user_cfg.items():
                if isinstance(val, dict) and key in config:
                    config[key].update(val)
                else:
                    config[key] = val
        print(f"✅ Configuración cargada desde {path}")
    except FileNotFoundError:
        print(f"⚠️ No se encontró {path}, usando configuración por defecto.")
    except Exception as e:
        print(f"⚠️ Error leyendo {path}: {e}, usando valores por defecto.")
    return config


config = load_config()

# ------------------------------------------------------------------
# 🧱 Configuración de logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"].upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 🎥 Inicializar cámara
# ------------------------------------------------------------------
picam2 = Picamera2()
try:
    cam_cfg = picam2.create_preview_configuration(
        main={
            "size": tuple(config["camera"]["resolution"]),
            "format": config["camera"]["format"],
        }
    )
    picam2.configure(cam_cfg)
    picam2.start()
    logger.info("✅ Cámara inicializada correctamente")
except Exception as e:
    logger.error(f"🚫 No se pudo inicializar la cámara: {e}")
    sys.exit(1)

frame_lock = threading.Lock()
frame = None
running = True


def capture_frames():
    """Captura continua de imágenes JPEG desde Picamera2"""
    global frame
    while running:
        try:
            buf = io.BytesIO()
            picam2.capture_file(buf, format="jpeg")
            buf.seek(0)
            with frame_lock:
                frame = buf.read()
            time.sleep(config["camera"]["frame_interval"])
        except Exception as e:
            logger.warning(f"⚠️ Error en captura: {e}")
            time.sleep(1)


threading.Thread(target=capture_frames, daemon=True).start()

# ------------------------------------------------------------------
# 🌐 Servidor Flask
# ------------------------------------------------------------------
app = Flask(__name__)


def generate_stream():
    """Genera flujo MJPEG para /video_feed"""
    global frame
    while True:
        with frame_lock:
            if frame is None:
                continue
            data = frame
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/schema1")
def schema1():
    return render_template("index1.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_stream(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# ------------------------------------------------------------------
# 🔒 CONTROL DE CERRADURA MAGNÉTICA
# ------------------------------------------------------------------
try:
    import RPi.GPIO as GPIO

    LOCK_GPIO_PIN = config["lock"]["gpio_pin"]
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(
        LOCK_GPIO_PIN,
        GPIO.OUT,
        initial=GPIO.LOW if config["lock"]["active_high"] else GPIO.HIGH,
    )
    logger.info(f"✅ GPIO listo (pin {LOCK_GPIO_PIN}) para control de cerradura")
except Exception as e:
    logger.warning(f"⚠️ No se pudo inicializar GPIO: {e}")
    GPIO = None


def activate_lock(duration=None):
    """Activa la cerradura por X segundos"""
    if GPIO is None:
        logger.warning("GPIO no disponible, cerradura ignorada.")
        return

    duration = duration or config["lock"]["unlock_duration"]
    active_high = config["lock"]["active_high"]

    try:
        GPIO.output(LOCK_GPIO_PIN, GPIO.HIGH if active_high else GPIO.LOW)
        logger.info(f"🔓 Cerradura activada ({duration}s)")
        time.sleep(duration)
    finally:
        GPIO.output(LOCK_GPIO_PIN, GPIO.LOW if active_high else GPIO.HIGH)
        logger.info("🔒 Cerradura desactivada")


@app.route("/api/unlock", methods=["POST"])
def unlock():
    """Endpoint remoto para apertura de cerradura"""
    token = request.args.get("token", "")
    if token != config["security"]["api_token"]:
        abort(403, description="Token inválido")

    data = request.get_json(silent=True) or {}
    duration = float(data.get("duration", config["lock"]["unlock_duration"]))
    reason = data.get("reason", "manual")

    threading.Thread(target=activate_lock, args=(duration,), daemon=True).start()
    logger.info(f"🔓 Apertura solicitada (razón: {reason}, duración: {duration}s)")
    return jsonify({"status": "ok", "reason": reason, "duration": duration})


# ------------------------------------------------------------------
# 🏁 Ejecución
# ------------------------------------------------------------------
if __name__ == "__main__":
    try:
        app.run(
            host=config["server"]["host"],
            port=config["server"]["port"],
            debug=config["server"]["debug"],
            threaded=True,
        )
    finally:
        running = False
        picam2.stop()
        if GPIO:
            GPIO.cleanup()
        logger.info("🧹 Servidor detenido correctamente")
