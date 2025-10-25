from flask import Flask, Response, render_template_string
from picamera2 import Picamera2
import io
import time
from PIL import Image

app = Flask(__name__)

# --- Configuración de la cámara ---
picam2 = Picamera2()
config = picam2.create_preview_configuration({"size": (640, 480), "format": "XBGR8888"})
picam2.configure(config)
picam2.start()
time.sleep(2)  # pequeño retardo para estabilizar


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
    return render_template_string("""
        <html>
        <head>
          <title>Video Portero</title>
          <style>
            body { background-color: #111; color: #fff; text-align: center; font-family: sans-serif; }
            img { border: 3px solid #333; border-radius: 10px; margin-top: 20px; }
            button { margin: 10px; padding: 10px 20px; font-size: 18px; border-radius: 10px; border: none; }
            .btn-open { background: #28a745; color: white; }
            .btn-nfc { background: #007bff; color: white; }
          </style>
        </head>
        <body>
          <h1>🔔 Video Portero Raspberry Pi</h1>
          <img src="{{ url_for('video_feed') }}" width="640" height="480">
          <div>
            <button class="btn-nfc">Leer Tarjeta NFC</button>
            <button class="btn-open">Abrir Cerradura</button>
          </div>
        </body>
        </html>
    """)


@app.route("/video_feed")
def video_feed():
    return Response(
        generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, threaded=True)
