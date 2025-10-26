#!/usr/bin/env python3
# server.py - Flask signaling + aiortc WebRTC server using Picamera2 as video source
import os
import asyncio
import json
import threading
from flask import Flask, request, jsonify, send_from_directory, abort
from aiortc import (
    RTCPeerConnection,
    RTCSessionDescription,
    MediaStreamTrack,
    RTCConfiguration,
    RTCIceServer,
)
from aiortc.contrib.media import MediaRelay
import lgpio as GPIO
import paho.mqtt.client as mqtt

# Try import Picamera2; fallback to using v4l2 via av if necessary
try:
    from picamera2 import Picamera2

    PICAMERA2_AVAILABLE = True
except Exception:
    PICAMERA2_AVAILABLE = False

# ---------------- CONFIG ----------------
UNLOCK_GPIO = 17
UNLOCK_TIME = 3  # seg
MQTT_BROKER = "localhost"
MQTT_TOPIC_UNLOCK = "portero/unlock"
PORT = int(os.environ.get("PORT", 8080))
AUTH_TOKEN = os.environ.get("PORTERO_TOKEN", "cambia_este_token")
ICE_SERVERS = [{"urls": ["stun:stun.l.google.com:19302"]}]
# ----------------------------------------

app = Flask(__name__, static_folder="static", static_url_path="/static")

# GPIO setup
# GPIO.setmode(GPIO.BCM)
# GPIO.setup(UNLOCK_GPIO, GPIO.OUT, initial=GPIO.LOW)
#
CHIP = 0
GPIO.setmode = lambda mode: None  # no se usa en lgpio
GPIO.setup = lambda pin, mode, initial=None: GPIO.gpio_claim_output(CHIP, pin)
GPIO.output = lambda pin, value: GPIO.gpio_write(CHIP, pin, value)
GPIO.cleanup = lambda: GPIO.gpiochip_close(CHIP)


# MQTT (to notify ESP32s)
mqttc = mqtt.Client()
try:
    mqttc.connect(MQTT_BROKER, 1883, 60)
    mqttc.loop_start()
except Exception as e:
    print("MQTT connect failed:", e)

# Media relay for reuse of single camera source across multiple PCs
relay = MediaRelay()


# Picamera2 wrapper as aiortc track
class Picamera2VideoTrack(MediaStreamTrack):
    kind = "video"

    def __init__(self, picam2):
        super().__init__()
        self.picam2 = picam2

    async def recv(self):
        frame = self.picam2.capture_array()
        # convert numpy -> av.VideoFrame (aiortc will accept numpy arrays via av.VideoFrame)
        import av

        video_frame = av.VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts, video_frame.time_base = await self.next_timestamp()
        return video_frame


# If Picamera2 not available, try /dev/video0 via aiortc MediaPlayer (not implemented here)
if PICAMERA2_AVAILABLE:
    picam2 = Picamera2()
    # picam2.configure(
    #     picam2.create_preview_configuration({"main": {"size": (640, 480)}})
    # )
    # picam2.configure(
    #     picam2.create_preview_configuration(
    #         {"size": (640, 480), "format": "XBGR8888", "buffer_count": 2}
    #     )
    # )

    # config = picam2.create_preview_configuration(size=(640, 480), format="XBGR8888")
    # picam2.configure(config)

    config = picam2.create_preview_configuration(
        {"size": (640, 480), "format": "XBGR8888", "preserve_ar": True}
    )
    picam2.configure(config)

    picam2.start()
    print("Picamera2 started.")
else:
    picam2 = None
    print("Picamera2 not available; fallback not implemented in this script.")

pcs = set()


def unlock_action(reason="manual"):
    print("Unlock:", reason)
    mqttc.publish(MQTT_TOPIC_UNLOCK, payload=reason, qos=1)
    GPIO.output(UNLOCK_GPIO, GPIO.HIGH)
    asyncio.run_coroutine_threadsafe(_delayed_lock(), asyncio.get_event_loop())


async def _delayed_lock():
    await asyncio.sleep(UNLOCK_TIME)
    GPIO.output(UNLOCK_GPIO, GPIO.LOW)
    print("Lock re-armed.")


# Flask endpoints
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/offer", methods=["POST"])
def offer():
    params = request.json
    token = params.get("token", "")
    if token != AUTH_TOKEN:
        return abort(403)
    sdp = params["sdp"]
    sdp_type = params["type"]

    pc = RTCPeerConnection(
        configuration=RTCConfiguration(
            iceServers=[RTCIceServer(**s) for s in ICE_SERVERS]
        )
    )
    pcs.add(pc)
    print("Created PeerConnection:", pc)

    # Add video track (relay ensures one camera used by many)
    if picam2 is not None:
        local_track = Picamera2VideoTrack(picam2)
        pc.addTrack(relay.subscribe(local_track))

    # if we wanted to receive audio from browser (microphone) do something here:
    @pc.on("track")
    def on_track(track):
        print("Track received", track.kind)
        if track.kind == "audio":
            # optionally play or record
            pass

    # handle cleanup
    @pc.on("connectionstatechange")
    async def on_connstatechange():
        print("Connection state:", pc.connectionState)
        if pc.connectionState == "failed" or pc.connectionState == "closed":
            await pc.close()
            pcs.discard(pc)

    # set remote, create answer
    offer = RTCSessionDescription(sdp=sdp, type=sdp_type)
    loop = asyncio.get_event_loop()
    coro = pc.setRemoteDescription(offer)
    loop.run_until_complete(coro)
    coro2 = pc.createAnswer()
    answer = loop.run_until_complete(coro2)
    loop.run_until_complete(pc.setLocalDescription(answer))

    return jsonify({"sdp": pc.localDescription.sdp, "type": pc.localDescription.type})


@app.route("/unlock", methods=["POST"])
def http_unlock():
    token = request.args.get("token", "")
    if token != AUTH_TOKEN:
        return abort(403)
    reason = request.json.get("reason", "remote") if request.is_json else "remote"
    # run unlock in thread so Flask returns quickly
    threading.Thread(target=unlock_action, args=(reason,)).start()
    return jsonify({"status": "ok", "reason": reason})


# graceful shutdown
def cleanup():
    for pc in list(pcs):
        try:
            asyncio.get_event_loop().run_until_complete(pc.close())
        except Exception:
            pass
    if picam2 is not None:
        picam2.stop()
    mqttc.loop_stop()
    GPIO.cleanup()


if __name__ == "__main__":
    try:
        app.run(host="0.0.0.0", port=PORT, threaded=True)
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()
