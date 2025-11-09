#!/usr/bin/env python3
# version 6: video + cerradura + config externa + alerta botón físico

from flask import (
    Flask,
    Response,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    session,
    stream_with_context,
    g,
)
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from picamera2 import Picamera2
import io, threading, time, logging, json, sys, math
import queue, nfcModule, db


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
last_usuario = {"id": None, "nombre": None, "activo": False, "timestamp": None}

ADMIN_USER = config.get("admin", {}).get("username", "admin")
ADMIN_PASS = config.get("admin", {}).get("password", "1234")


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
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")
app.secret_key = "supersecretkey"  # cambia esta cadena


def generate_stream():
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


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_stream(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        user = request.form.get("username")
        pw = request.form.get("password")
        if user == ADMIN_USER and pw == ADMIN_PASS:
            session["logged_in"] = True
            return redirect(url_for("admin_page"))
        return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))


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


@app.route("/api/open", methods=["POST"])
def open():
    token = request.args.get("token", "")
    logger.info(f"🔒 Token recibido: {token}")
    # if token != config["security"]["api_token"]:
    #     abort(403, description="Token inválido")

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


# ------------------------------------------------------------------
# 📢 EVENTOS EN TIEMPO REAL (SSE)
# ------------------------------------------------------------------
event_queue = queue.Queue()


@app.route("/events")
def events():
    def event_stream():
        while True:
            event = event_queue.get()
            yield f"data: {json.dumps(event)}\n\n"

    return Response(stream_with_context(event_stream()), mimetype="text/event-stream")


def broadcast_event(event, data):
    """Envía eventos NFC al panel /admin usando SocketIO"""
    try:
        socketio.emit(event, data)
    except Exception as e:
        logger.error(f"Error en broadcast_event: {e}")


# --------------------------------------------
# 🎫 CALLBACK PARA TARJETAS NFC
# ------------------------------------------------------------------


def on_usuario_detected(id):
    try:
        conn = db.sqlite3.connect(db.DB_PATH)
        conn.row_factory = db.sqlite3.Row
        c = conn.cursor()
        c.execute(
            "SELECT nombre, ap, am, pwd, email, cell, tipoId, fecha, activo, operador FROM usuarios WHERE id=?",
            (id,),
        )
        row = c.fetchone()
        conn.close()
        if row:
            nombre = row["nombre"]
            ap = row["ap"]
            am = row["am"]
            pwd = row["pwd"]
            email = row["email"]
            cell = row["cell"]
            tipoId = row["tipoId"]
            fecha = row["fecha"]
            activo = row["activo"]
            operador = row["operador"]
        else:
            nombre = "Desconocido"
            ap = ""
            am = ""
            pwd = ""
            email = ""
            cell = ""
            tipoId = 0
            fecha = (time.strftime("%Y-%m-%d %H:%M:%S"),)
            activo = 0
            operador = 0

        last_usuario = {
            "id": id,
            "nombre": nombre,
            "ap": ap,
            "am": am,
            "pwd": pwd,
            "email": email,
            "cell": cell,
            "tipoId": tipoId,
            "fecha": fecha,
            "activo": bool(activo),
            "operador": bool(operador),
        }

        logging.info(
            f"🎫 Tarjeta ID={id} | {'✅ Autorizada' if activo else '❌ Denegada'} | {nombre}"
        )

        broadcast_event("nfc_access", last_usuario)

        if activo:
            threading.Thread(target=activate_lock, daemon=True).start()
        else:
            logging.warning(f"🚫 Acceso denegado para ID={id}")

    except Exception as e:
        logging.error(f"⚠️ Error en on_usuario_detected: {e}")


threading.Thread(target=listen_button, daemon=True).start()


# =========================
#  PANEL DE ADMINISTRACIÓN
# ==========================
@app.route("/admin")
def admin():
    idx = 1
    if "idx" in request.args:
        idx = request.args["idx"]

    logging.warn(f"idx: {idx}")

    usuarios = db.list_usuarios()
    tipoUsuario = db.tabla_tipoUsuario()

    return render_template(
        "admin.html", usuarios=usuarios, tipoUsuario=tipoUsuario, nfcModule=nfcModule
    )


@app.route("/admin/add", methods=["POST"])
def admin_add():
    data = request.get_json()
    id = data.get("id", "").strip().upper()
    nombre = data.get("nombre", "").strip()
    tipoId = data.get("tipoId", 2)  # Valor por defecto 'user' si no se envía
    logger.info(f"datos recibidos:  {data}")
    if not id:
        return {"error": "El campo ID es obligatorio."}, 400
    db.add_usuario(id, nombre, tipoId)
    return {"message": "Tarjeta agregada exitosamente."}, 201


# version para recibir como form
def admin_add_():
    id = request.form["id"].strip().upper()
    nombre = request.form["nombre"].strip()
    tipoId = request.form["tipoId"]
    db.add_usuario(id, nombre, tipoId)
    return redirect(url_for("admin"))


@app.route("/admin/update/<id>", methods=["POST"])
def admin_update(id):
    nombre = request.form.get("nombre", "")
    tipoId = request.form.get("tipoId", 2)
    activo = int(request.form.get("activo", 1))
    db.usuario(id, nombre, tipoId, activo)
    return redirect(url_for("admin"))


@app.route("/admin/delete/<uid>", methods=["POST"])
def admin_delete(id):
    db.remove_usuario(id)
    return redirect(url_for("admin"))


@app.route("/guardar-usuario", methods=["POST"])
def guardar_usuario():
    usuario = request.get_json()
    # logging.info(f"usuario --> {usuario}")
    db.add_usuario(
        usuario.get("id"),
        usuario.get("nombre"),
        usuario.get("ap"),
        usuario.get("am"),
        usuario.get("pwd"),
        usuario.get("email"),
        usuario.get("cell"),
        usuario.get("tipoId"),
        int(usuario.get("activo")),
        int(usuario.get("operador")),
    )
    usuarios = db.list_usuarios()
    return jsonify({"mensaje": "Usuario guardado correctamente"}), 200


# ===========   Paginado  =================================
@app.route("/admin/usuarios", methods=["GET"])
def obtener_usuarios():
    try:
        # Obtener parámetros de paginación
        pagina = request.args.get("pagina", 1, type=int)
        por_pagina = request.args.get(
            "por_pagina", 50, type=int
        )  # 50 registros por página
        busqueda = request.args.get("busqueda", "", type=str)

        # Validar parámetros
        if pagina < 1:
            pagina = 1
        if por_pagina > 100:  # Límite máximo
            por_pagina = 100

        # Calcular offset
        offset = (pagina - 1) * por_pagina

        g.db = db.sqlite3.connect(db.DB_PATH)
        g.db.row_factory = db.sqlite3.Row

        dbase = g.db

        # Construir consulta base con búsqueda
        query_base = """
            SELECT u.*, t.tipo
            FROM usuarios u
            LEFT JOIN tipoUsuario t ON u.tipoId = t.id
        """

        query_contar = "SELECT COUNT(*) as total FROM usuarios u"

        params = []
        where_conditions = []

        if busqueda:
            where_conditions.append("""
                (u.nombre LIKE ? OR u.ap LIKE ? OR u.email LIKE ? OR u.id LIKE ?)
            """)
            param_busqueda = f"%{busqueda}%"
            params.extend(
                [param_busqueda, param_busqueda, param_busqueda, param_busqueda]
            )

        # Aplicar WHERE si hay condiciones
        if where_conditions:
            where_clause = " WHERE " + " AND ".join(where_conditions)
            query_base += where_clause
            query_contar += where_clause

        # Ordenar y paginar
        query_base += " ORDER BY u.fecha DESC LIMIT ? OFFSET ?"
        params.extend([por_pagina, offset])

        # Ejecutar consulta para obtener usuarios
        usuarios = dbase.execute(query_base, params).fetchall()

        # Ejecutar consulta para contar total
        total_result = dbase.execute(
            query_contar, params[:-2] if busqueda else []
        ).fetchone()
        total_usuarios = total_result["total"]

        # Calcular total de páginas
        total_paginas = math.ceil(total_usuarios / por_pagina)

        # Convertir a lista de diccionarios
        usuarios_list = [dict(usuario) for usuario in usuarios]

        return jsonify(
            {
                "usuarios": usuarios_list,
                "paginacion": {
                    "pagina_actual": pagina,
                    "por_pagina": por_pagina,
                    "total_usuarios": total_usuarios,
                    "total_paginas": total_paginas,
                    "has_prev": pagina > 1,
                    "has_next": pagina < total_paginas,
                },
            }
        ), 200

    except Exception as e:
        logging.error(f"Error al obtener usuarios: {str(e)}")
        return jsonify({"error": "Error al obtener usuarios"}), 500


# ------------------------------------------------------------------
# 🏁 Main Prog section
# ------------------------------------------------------------------
if __name__ == "__main__":
    try:
        # Iniciar lector NFC en segundo plano
        db.init_db()
        threading.Thread(
            target=nfcModule.start_reader, args=(on_usuario_detected,), daemon=True
        ).start()
        logger.info(
            "📡 Lector NFC (RDM6300) iniciado        # nfcModule.start_reader(on_usuario_detected) en hilo de fondo"
        )

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
        nfcModule.reader_running = False
        logger.info("🧹 Servidor detenido correctamente")
