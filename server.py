#!/usr/bin/env python3
# version 3 con image capture

from flask import Flask, Response, render_template_string, render_template
from picamera2 import Picamera2
import io, threading, time

app = Flask(__name__)

# --- Configurar cámara ---
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "XBGR8888"}
)
picam2.configure(config)
picam2.start()

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
            time.sleep(0.05)
        except Exception as e:
            print(f"⚠️ Error en captura: {e}")
            time.sleep(1)


threading.Thread(target=capture_frames, daemon=True).start()


def generate_stream():
    global frame
    while True:
        with frame_lock:
            if frame is None:
                continue
            data = frame
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")


# --- HTML minimalista ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Videoportero</title>
<style>
body {
  margin:0; background:#111; color:white; font-family:sans-serif;
  display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh;
}
img {
  width:100%; max-width:640px; border-radius:10px;
  box-shadow:0 0 10px rgba(0,0,0,0.6);
}
button {
  margin-top:10px; padding:10px 20px; border:none; border-radius:6px;
  background:#2196F3; color:white; cursor:pointer;
}
button:hover { background:#0b7dda; }
</style>
</head>
<body>
<h2>📷 Videoportero</h2>
<img id="stream" src="/video_feed">
<canvas id="canvas" width="640" height="480" style="display:none;"></canvas>
<button onclick="capturar()">📸 Capturar Foto</button>
<script>
function capturar() {
  const video = document.getElementById('stream');
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  const enlace = document.createElement('a');
  enlace.download = 'captura_' + new Date().toISOString().replace(/[:.]/g,'_') + '.jpg';
  enlace.href = canvas.toDataURL('image/jpeg');
  enlace.click();
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_PAGE)


@app.route("/schema1")
def schema1():
    return render_template("index.html")


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_stream(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=5000, threaded=True)
    finally:
        running = False
        picam2.stop()
