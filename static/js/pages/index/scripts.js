const STREAM_MJPEG = "/live.m3u8";
const STREAM_HLS = "{{video_url}}"; // si no hay HLS, no es necesario
const API_BASE = "/api"; // ejemplo: POST /api/open, /api/unlock, /api/snapshot, /api/talk

var video = document.getElementById("videoStream");
var videoSrc = "{{ video_url }}"; // Nombre de tu archivo M3U8

if (Hls.isSupported()) {
    var hls = new Hls({
        // Ajustes para baja latencia (corta la lista de reproducción)
        startPosition: -1,
        liveSyncDurationCount: 2,
        liveMaxLatencyDurationCount: 3,
    });
    hls.loadSource(videoSrc);
    hls.attachMedia(video);
    hls.on(Hls.Events.MANIFEST_PARSED, function () {
        video.play();
    });
} else if (video.canPlayType("application/vnd.apple.mpegurl")) {
    // Soporte nativo de HLS (para Safari)
    video.src = videoSrc;
    video.addEventListener("loadedmetadata", function () {
        setTimeout(() => {
            video.play();
            showNotification("Video recargado", "success");
        }, 100);
    });
}

// Try to detect if MJPEG fails — then fallback to HLS/video
let lastFrameTime = performance.now();
let frames = 0;
let fpsInterval = null;

// Capture image--------
function capturar() {
    const video = document.getElementById("stream");
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const enlace = document.createElement("a");
    enlace.download =
        "captura_" + new Date().toISOString().replace(/[:.]/g, "_") + ".jpg";
    enlace.href = canvas.toDataURL("image/jpeg");
    enlace.click();
}

// ⚙️ Token de seguridad (debe coincidir con config.json)
const API_TOKEN = "1234";

async function abrirPuerta() {
    const status = document.getElementById("nfc-status");
    const beep = document.getElementById("dooropen");

    status.textContent = "⏳ Enviando señal...";
    status.style.color = "#cccccc";

    console.log(`open url: ${API_BASE}/open?token=${API_TOKEN}`);
    try {
        const response = await fetch(`${API_BASE}/open?token=${API_TOKEN}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                reason: "web_button",
            }),
        });

        if (response.ok) {
            const data = await response.json();
            status.textContent = "✅ Puerta abierta correctamente";
            status.style.color = "#4caf50";

            // 🔊 Reproducir beep de confirmación
            beep.currentTime = 0;
            beep.play().catch((err) =>
                console.warn("No se pudo reproducir beep:", err),
            );
        } else {
            status.textContent = "❌ Error al abrir puerta";
            status.style.color = "#f44336";
        }
    } catch (err) {
        status.textContent = "⚠️ Error de conexión con el servidor";
        status.style.color = "#ff9800";
    } finally {
        setTimeout(() => {
            status.textContent = "";
        }, 4000);
    }
}

//Revisar si se queda la funcion !!!
// Fallback function — shows <video> and hides <img>
function tryFallbackToVideo() {
    // Only attempt if hls URL likely available
    if (!STREAM_HLS) {
        return;
    }
    mjpeg.style.display = "none";
    hlsVideo.style.display = "block";
    // If the browser supports HLS natively (Safari) it will play. For others you'd need hls.js:
    // We don't include hls.js here; if needed, add it and attach to hlsVideo.
    hlsVideo.src = STREAM_HLS;
    hlsVideo.play().catch(() => {
        /* ignore autoplay block */
    });
}
// Button actions
async function postAction(action, body = {}) {
    const url = `${API_BASE}/${action}`;
    try {
        const r = await fetch(url, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        });
        if (!r.ok) throw new Error("HTTP " + r.status);
        const json = await r.json().catch(() => ({ ok: true }));
        return { ok: true, data: json };
    } catch (err) {
        console.error("postAction", action, err);
        return { ok: false, err: err };
    }
}

document.getElementById("snapshotBtn").addEventListener("click", async () => {
    // If server supports snapshot endpoint that returns image bytes/base64
    const resp = await postAction("snapshot");
    if (resp.ok && resp.data && resp.data.image_base64) {
        displayThumbnail(resp.data.image_base64);
    } else if (resp.ok && resp.data && resp.data.url) {
        displayThumbnailFromUrl(resp.data.url);
    } else {
        alert(
            "Captura solicitada. Si no ves imagen, asegúrate que /api/snapshot devuelve base64 o url.",
        );
    }
});

document.getElementById("talkBtn").addEventListener("click", async () => {
    // Simple toggle: start/stop talk. Could be long-press for PTT in the future.
    const resp = await postAction("talk_toggle");
    if (resp.ok) alert("Toggle talk enviado.");
    else alert("Error en talk.");
});

// Fullscreen
document.getElementById("adminBtn").addEventListener("click", () => {
    window.location.href = "/admin";
});

// Thumbnail display helpers
function displayThumbnail(base64) {
    thumb.innerHTML = "";
    const img = document.createElement("img");
    img.src = "data:image/jpeg;base64," + base64;
    thumb.appendChild(img);
}

function displayThumbnailFromUrl(url) {
    thumb.innerHTML = "";
    const img = document.createElement("img");
    img.src = url;
    thumb.appendChild(img);
}

// --- 🔔 Eventos del servidor (SSE) ------------------------
const evtSource = new EventSource("/events");

evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log("Evento recibido:", data);

    if (data.type === "nfc_access") {
        const msg = data.activo
            ? `✅ Tarjeta ${data.id} autorizada — puerta abierta`
            : `🚫 Tarjeta ${data.id} no autorizada`;
        showNotification(msg, data.activo ? "success" : "error");
        if (data.activo) {
            const audio = new Audio("/static/sounds/open.mp3");
            audio.play();
        } else {
            const audio = new Audio("/static/sounds/failed.mp3");
            audio.play();
        }
    }
};

// Simple helper para mostrar notificaciones
function showNotification(msg, type = "info") {
    const el = document.createElement("div");
    el.textContent = msg;
    el.className = `notif ${type}`;
    Object.assign(el.style, {
        position: "fixed",
        bottom: "10px",
        right: "10px",
        background:
            type === "error"
                ? "#f44336"
                : type === "success"
                  ? "#4caf50"
                  : "#333",
        color: "#fff",
        padding: "10px 15px",
        borderRadius: "8px",
        zIndex: 9999,
        fontSize: "0.9rem",
        transition: "opacity 0.5s",
        opacity: 0.95,
    });
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 4000);
}
