//------------    Guardar nuevo Usuario   ------>
document
    .getElementById("userForm")
    .addEventListener("submit", function (event) {
        event.preventDefault(); // Prevenir envío tradicional del formulario
        if (confirmarProceso("Deseas aplicar los cambios?")) {
            // Recopilar datos del formulario
            const formData = new FormData(this);

            // Convertir FormData a objeto JSON
            const jsonData = {
                id: document.getElementById("inputId").value,
                nombre: document.getElementById("inputNombre").value,
                ap: document.getElementById("inputAPaterno").value,
                am: document.getElementById("inputAMaterno").value,
                email: document.getElementById("inputEmail").value,
                pwd: document.getElementById("inputPwd").value,
                cell: document.getElementById("inputCell").value,
                tipoId: document.getElementById("selectTipo").value,
                // Checkboxes manejados directamente
                operador: document.getElementById("checkOperador").checked
                    ? "1"
                    : "0",
                activo: document.getElementById("checkActivo").checked
                    ? "1"
                    : "0",
            };

            // Mostrar loading en el botón
            const saveButton = document.getElementById("saveButton");
            const originalText = saveButton.innerHTML;
            saveButton.innerHTML = "⏳ Guardando...";
            saveButton.disabled = true;
            console.log("jsonData: ", jsonData);

            // Enviar datos al servidor Flask
            fetch("/guardar-usuario", {
                // Cambia esta URL por tu endpoint de Flask
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(jsonData),
            })
                .then((response) => {
                    if (!response.ok) {
                        throw new Error("Error en la respuesta del servidor");
                    }
                    return response.json();
                })
                .then((data) => {
                    // Manejar respuesta exitosa
                    console.log("Usuario guardado:", data);
                    alert("✅ Usuario guardado exitosamente");

                    // Resetear formulario si es necesario
                    this.reset();

                    // Aquí puedes agregar más lógica según la respuesta
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    }

                    cargarUsuarios();
                })
                .catch((error) => {
                    console.error("Error:", error);
                    alert("❌ Error al guardar el usuario: " + error.message);
                })
                .finally(() => {
                    // Restaurar botón
                    saveButton.innerHTML = originalText;
                    saveButton.disabled = false;
                });
        }
    });

// Manejar el botón cancelar si es necesario
document.getElementById("cancelButton").addEventListener("click", function () {
    document.getElementById("userForm").reset();
    this.style.display = "none";
    // Aquí puedes agregar más lógica para cancelar edición
});
