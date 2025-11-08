const Id = document.getElementById("inputId");
const Nombre = document.getElementById("nombre");
const tipoUsuario = document.getElementById("tipoUsuario");

const socket = io();
socket.on("nfc_access", (data) => {
    Id.value = data.id;
    console.log("Tarjeta detectada:", data);
    const status = data.activo ? "✅ Acceso permitido" : "🚫 Acceso denegado";
    const color = data.activo ? "green" : "red";
    const cardInfo = `
     <div style="padding:10px;margin-top:10px;border:2px solid ${color};border-radius:8px">
     <b>${status}</b><br>
     UID: ${data.id}<br>
     Nombre: ${data.nombre || "Desconocido"}
     </div>`;
    document.getElementById("nfc-status").innerHTML = cardInfo;
});

tablaUsuarios.addEventListener("click", (e) => {
    if (e.target.classList.contains("edit-btn")) {
        // ... (Tu código para cargar los datos en el formulario) ...
        console.log("le di click al edit-btn!");
        // 💡 Abrir la sección colapsable al hacer clic en Editar
        document.querySelector(".form-container").open = true;

        saveButton.textContent = "💾 Actualizar Usuario";
        // ...
    }
});

async function LeerTarjetas() {
    try {
        const response = await fetch("/admin/add", {
            method: "POST", // Usamos el método POST para enviar datos
            headers: {
                "Content-Type": "application/json", // Indicamos que el cuerpo es JSON
            },
            body: JSON.stringify(tagData), // Convertimos el objeto a cadena JSON
        });

        // 4. Procesar la respuesta del servidor
        if (response.ok) {
            const result = await response.json();
            alert(
                `✅ Tarjeta agregada con éxito! Mensaje: ${result.message || "OK"}`,
            );

            // Opcional: Recargar la página para ver la tarjeta en la tabla
            window.location.reload();
        } else {
            const errorResult = await response.json();
            alert(
                `❌ Error al agregar tarjeta: ${errorResult.error || response.statusText}`,
            );
        }
    } catch (error) {
        console.error("Error de red o del servidor:", error);
        alert("❌ Fallo la comunicación con el servidor.");
    }
}

async function agregarTag(event) {
    if (event) {
        event.preventDefault();
    }
    console.log(
        "se agregara: " +
            JSON.stringify({
                uid: Id.value,
                name: Nombre.value,
                tipoId: tipoUsuario.value,
            }),
    );

    // 2. Validación de Inputs
    if (Id.value == "" || Nombre.value == "") {
        alert("⚠️ El campo UID y Nombre son obligatorios.");
        Id.focus();
        return; // Detiene la función si el UID está vacío
    }

    // El campo 'Nombre' y 'Nivel' siempre tendrán un valor (el nombre puede estar vacío, pero no es requerido por HTML)

    const tagData = {
        id: Id.value,
        nombre: Nombre.value,
        level: tipoUsuario.value,
    };
    console.log("Datos a enviar: ", JSON.stringify(tagData));

    // 3. Envío del objeto JSON a /admin/add
    try {
        const response = await fetch("/admin/add", {
            method: "POST", // Usamos el método POST para enviar datos
            headers: {
                "Content-Type": "application/json", // Indicamos que el cuerpo es JSON
            },
            body: JSON.stringify(tagData), // Convertimos el objeto a cadena JSON
        });

        // 4. Procesar la respuesta del servidor
        if (response.ok) {
            const result = await response.json();
            alert(
                `✅ Tarjeta agregada con éxito! Mensaje: ${result.message || "OK"}`,
            );

            // Opcional: Recargar la página para ver la tarjeta en la tabla
            window.location.reload();
        } else {
            const errorResult = await response.json();
            alert(
                `❌ Error al agregar tarjeta: ${errorResult.error || response.statusText}`,
            );
        }
    } catch (error) {
        console.error("Error de red o del servidor:", error);
        alert("❌ Fallo la comunicación con el servidor.");
    }
}
