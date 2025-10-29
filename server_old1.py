#!/usr/bin/env python3
# version mejorada del server1.py
#
#
from flask import Flask, Response, render_template
from picamera2 import Picamera2
import io
import threading
import time

app = Flask(__name__)

# --- Configurar cámara ---
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "XBGR8888"}
)
picam2.configure(config)
picam2.start()

# --- Variables globales ---
frame_lock = threading.Lock()
frame = None
running = True


# --- Captura continua en segundo plano ---
def capture_frames():
    global frame
    while running:
        try:
            buf = io.BytesIO()
            picam2.capture_file(buf, format="jpeg")
            buf.seek(0)
            with frame_lock:
                frame = buf.read()
            time.sleep(0.05)  # 20 FPS aprox.
        except Exception as e:
            print(f"⚠️ Error en captura: {e}")
            time.sleep(1)


threading.Thread(target=capture_frames, daemon=True).start()


# --- Stream MJPEG ---
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


@app.route("/schema1")
def schema1():
    return render_template("index1.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_stream(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


# --- Limpieza al salir ---
@app.route("/shutdown")
def shutdown():
    global running
    running = False
    picam2.stop()
    return "Cámara detenida."


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        running = False
        picam2.stop()
