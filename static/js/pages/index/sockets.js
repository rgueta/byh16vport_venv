const socket = io();

// 🟢 Escuchar evento de timbre físico
socket.on("alert_request", (data) => {
    // 🔊 Reproducir sonido
    const audio = document.getElementById("doorbell");
    audio.currentTime = 0;
    audio
        .play()
        .catch((err) => console.warn("No se pudo reproducir sonido:", err));

    const alertDiv = document.createElement("div");
    alertDiv.textContent = data.message || "🚨 Alerta";
    alertDiv.style.position = "fixed";
    alertDiv.style.top = "20px";
    alertDiv.style.right = "20px";
    alertDiv.style.background = "#ff9800";
    alertDiv.style.color = "#000";
    alertDiv.style.padding = "12px 18px";
    alertDiv.style.borderRadius = "8px";
    alertDiv.style.fontWeight = "bold";
    alertDiv.style.zIndex = "9999";
    document.body.appendChild(alertDiv);
    setTimeout(() => alertDiv.remove(), 6000);
});

//============== Inicializar audio una vez el usuario interactúe (para evitar bloqueo de autoplay)
let audioReady = false;
document.body.addEventListener("click", () => {
    if (!audioReady) {
        const audio = document.getElementById("doorbell");
        audio
            .play()
            .then(() => {
                audio.pause();
                audio.currentTime = 0;
                console.log(
                    "🔈 Audio listo para reproducir en eventos futuros",
                );
            })
            .catch((err) => {
                console.warn("⚠️ El navegador bloqueó el audio:", err);
            });
        audioReady = true;
    }
});

//==================== Cuando llegue el evento de timbre desde el servidor
function playDoorbell() {
    const audio = document.getElementById("doorbell");
    audio.currentTime = 0;
    audio
        .play()
        .catch((err) => console.warn("Error al reproducir doorbell:", err));
}

// ==================== NFC lecturas  ===============================
socket.on("nfc_access", (data) => {
    console.log("Tarjeta detectada:", data);
    const status = data.activo ? "✅ Acceso permitido" : "🚫 Acceso denegado";
    const color = data.activo ? "green" : "red";
    const cardInfo = `
                <div style="padding:10px;margin-top:10px;border:2px solid ${color};border-radius:8px">
                  <b>${status}  </b>
                   ID: ${data.id}   <br>
                  Nombre: ${data.nombre || "Desconocido"}
                </div>`;
    document.getElementById("nfc-status").innerHTML = cardInfo;
    if (!data.activo) {
        addElement(data);
    }
});

//  ================   Accordion para las lecturas  ======================
let isAccordionOpen = false;
let elementCount = 0;

// Función para alternar el accordion principal
function toggleMainAccordion() {
    const content = document.getElementById("mainAccordionContent");
    const icon = document.getElementById("mainAccordionIcon");

    isAccordionOpen = !isAccordionOpen;
    content.classList.toggle("open");
    icon.classList.toggle("open");
}

// Función para agregar nuevo elemento a la tabla
function addElement(item) {
    // Incrementar contador
    elementCount++;

    // Asegurar que el accordion esté abierto
    if (!isAccordionOpen) {
        toggleMainAccordion();
    }

    // Ocultar estado vacío si existe
    const emptyState = document.getElementById("emptyState");
    if (emptyState && emptyState.parentElement.parentElement) {
        emptyState.parentElement.parentElement.remove();
    }

    // Crear nueva fila en la tabla
    const tableBody = document.getElementById("elementsTableBody");
    const newRow = document.createElement("tr");
    newRow.className = "fade-in";

    const now = new Date();
    const dateString =
        now.toLocaleDateString("es-ES", {
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
        }) +
        " " +
        now.toLocaleTimeString("es-ES", {
            hour: "2-digit",
            minute: "2-digit",
        });

    newRow.innerHTML = `
                <td class="uid-cell">${item.id}</td>
                <td class="name-cell">${item.nombre}</td>
                <td class="date-cell">${dateString}</td>
            `;

    // Agregar a la tabla
    tableBody.appendChild(newRow);

    // Actualizar contador
    updateElementCounter();
}

// Función para actualizar contador
function updateElementCounter() {
    const countElement = document.getElementById("elementCount");
    const rows = document.querySelectorAll("#elementsTableBody tr");
    const validRows = Array.from(rows).filter(
        (row) => !row.querySelector(".empty-state"),
    );
    countElement.textContent = validRows.length;
}
