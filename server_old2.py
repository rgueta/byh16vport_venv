# Version mejorada para evitar que la sesion de la camara
# se libere cuando haya algun Ctrl+C o Error que detenga
# la sesion

from flask import Flask, Response, render_template
from picamera2 import Picamera2
import io, time, subprocess, threading
from PIL import Image
import atexit

app = Flask(__name__)


# --- Configuración de la cámara ---
def release_camera_processes():
    """Mata procesos que bloquean la cámara."""
    print("🧹 Verificando procesos activos de cámara...")
    subprocess.run(["sudo", "pkill", "-f", "libcamera"], stderr=subprocess.DEVNULL)
    subprocess.run(["sudo", "pkill", "-f", "rpicam"], stderr=subprocess.DEVNULL)
    time.sleep(1)


def start_camera():
    try:
        release_camera_processes()
        picam = Picamera2()
        config = picam.create_preview_configuration(
            {"size": (640, 480), "format": "XBGR8888"}
        )
        picam.configure(config)
        picam.start()
        time.sleep(2)
        print("✅ Cámara inicializada correctamente")
        return picam
    except Exception as e:
        print(f"⚠️ Primer intento falló: {e}")
        release_camera_processes()
        try:
            picam = Picamera2()
            config = picam.create_preview_configuration(
                {"size": (640, 480), "format": "XBGR8888"}
            )
            picam.configure(config)
            picam.start()
            time.sleep(2)
            print("✅ Cámara recuperada tras reinicio")
            return picam
        except Exception as e2:
            print(f"❌ Error definitivo: {e2}")
            return None


# --- Función para generar el flujo MJPEG ---
def generate_frames():
    while True:
        frame = picam2.capture_array()
        # Convertir a JPEG
        image = Image.fromarray(frame[..., :3])
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG")
        frame_bytes = buffer.getvalue()

        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")


# --- Rutas Flask ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/schema1")
def schema1():
    return render_template("index1.html")


@app.route("/schema2")
def schema2():
    return render_template("index2.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


picam2 = start_camera()

if not picam2:
    print("🚫 No se pudo acceder a la cámara. Intenta desconectar otros procesos.")
    exit(1)

# --- Cierre limpio al terminar -----------------------------
import atexit


def cleanup_camera():
    try:
        print("🧹 Liberando cámara y hilos...")
        picam2.stop()
        time.sleep(0.5)
        release_camera_processes()
    except Exception as e:
        print(f"⚠️ Error al limpiar cámara: {e}")


# atexit.register(cleanup_camera)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000, use_reloader=False, threaded=True)
