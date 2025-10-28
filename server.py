#!/usr/bin/env python3
# version 6: video + cerradura + config externa + alerta botón físico

from flask import Flask, Response, render_template, request, jsonify, abort
from flask_socketio import SocketIO, emit
from picamera2 import Picamera2
import io, threading, time, logging, json, sys

# ------------------------------------------------------------------
# 🔧 Configuración
# ------------------------------------------------------------------
DEFAULT_CONFIG = {
    "camera": {"resolution": [640, 480], "format": "XBGR8888", "frame_interval": 0.05},
    "server": {"host": "0.0.0.0", "port": 5000, "debug": False},
    "lock": {"gpio_pin": 17, "active_high": True, "unlock_duration": 3.0},
    "button": {"gpio_pin": 27, "pullup": True},
    "security": {"api_token": "1234"},
    "logging": {"level": "INFO"},
}


def load_config(path="config.json"):
    config = DEFAULT_CONFIG.copy()
    try:
        with open(path, "r") as f:
            user_cfg = json.load(f)
            for key, val in user_cfg.items():
                if isinstance(val, dict) and key in config:
                    config[key].update(val)
                else:
                    config[key] = val
        print(f"✅ Configuración cargada desde {path}")
    except FileNotFoundError:
        print(f"⚠️ No se encontró {path}, usando configuración por defecto.")
    except Exception as e:
        print(f"⚠️ Error leyendo {path}: {e}")
    return config


config = load_config()

# ------------------------------------------------------------------
# 🧱 Logging
# ------------------------------------------------------------------
logging.basicConfig(
    level=getattr(logging, config["logging"]["level"].upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 🎥 Cámara
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
# 🌐 Flask + SocketIO
# ------------------------------------------------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


def generate_stream():
    global frame
    while True:
        with frame_lock:
            if frame is None:
                continue
            data = frame
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n"


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
# 🔒 Cerradura magnética
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
    logger.info(f"✅ GPIO listo (pin {LOCK_GPIO_PIN}) para cerradura")

    # Botón físico
    BTN_GPIO_PIN = config["button"]["gpio_pin"]
    GPIO.setup(
        BTN_GPIO_PIN,
        GPIO.IN,
        pull_up_down=GPIO.PUD_UP
        if config["button"].get("pullup", True)
        else GPIO.PUD_DOWN,
    )
    logger.info(f"✅ GPIO pin {BTN_GPIO_PIN} configurado como botón de solicitud")
except Exception as e:
    logger.warning(f"⚠️ No se pudo inicializar GPIO: {e}")
    GPIO = None

# --- Buzzer opcional ---
try:
    BUZ_GPIO_PIN = config.get("buzzer", {}).get("gpio_pin")
    if BUZ_GPIO_PIN:
        GPIO.setup(BUZ_GPIO_PIN, GPIO.OUT, initial=GPIO.LOW)
        logger.info(f"✅ GPIO pin {BUZ_GPIO_PIN} configurado para buzzer")
except Exception as e:
    logger.warning(f"⚠️ No se pudo inicializar buzzer: {e}")
    BUZ_GPIO_PIN = None


def activate_lock(duration=None):
    if GPIO is None:
        logger.warning("GPIO no disponible, cerradura ignorada.")
        return

    duration = duration or config["lock"]["unlock_duration"]
    active_high = config["lock"]["active_high"]

    try:
        GPIO.output(LOCK_GPIO_PIN, GPIO.HIGH if active_high else GPIO.LOW)
        logger.info(f"🔓 Cerradura activada ({duration}s)")
        socketio.emit("door_status", {"status": "open"})
        time.sleep(duration)
    finally:
        GPIO.output(LOCK_GPIO_PIN, GPIO.LOW if active_high else GPIO.HIGH)
        logger.info("🔒 Cerradura desactivada")
        socketio.emit("door_status", {"status": "closed"})


@app.route("/api/unlock", methods=["POST"])
def unlock():
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
# 🛎️ Escucha del botón físico
# ------------------------------------------------------------------
def listen_button():
    """Escucha el botón y notifica a los clientes web."""
    if GPIO is None:
        return
    last_press = 0
    while running:
        if GPIO.input(BTN_GPIO_PIN) == (
            GPIO.LOW if config["button"].get("pullup", True) else GPIO.HIGH
        ):
            now = time.time()
            if now - last_press > 2:  # anti-rebote
                logger.info("🚨 Botón físico presionado: solicitud de apertura")
                buzz(0.4)
                socketio.emit(
                    "alert_request", {"message": "🔔 Alguien presionó el timbre"}
                )
                last_press = now
        time.sleep(0.1)


def buzz(duration=0.3):
    """Emite un pitido corto."""
    if BUZ_GPIO_PIN is None or GPIO is None:
        return
    GPIO.output(BUZ_GPIO_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(BUZ_GPIO_PIN, GPIO.LOW)


threading.Thread(target=listen_button, daemon=True).start()

# ------------------------------------------------------------------
# 🏁 Main
# ------------------------------------------------------------------
if __name__ == "__main__":
    try:
        socketio.run(
            app,
            host=config["server"]["host"],
            port=config["server"]["port"],
            debug=config["server"]["debug"],
            allow_unsafe_werkzeug=True,
        )
    finally:
        running = False
        picam2.stop()
        if GPIO:
            GPIO.cleanup()
        logger.info("🧹 Servidor detenido correctamente")
