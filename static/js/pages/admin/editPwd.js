let modal = document.getElementById("editPasswordModal");

function openModal() {
    modal.classList.add("active");
    clearMessages();
    document.getElementById("passwordMatchError").style.display = "none";
    document.getElementById("passwordStrength").style.width = "0%";
}

function closeModal() {
    modal.classList.remove("active");
    document.getElementById("editPasswordForm").reset();
}

// Cerrar modal al hacer clic fuera del contenido
modal.addEventListener("click", function (event) {
    if (event.target === modal) {
        closeModal();
    }
});

function togglePassword(fieldId) {
    const field = document.getElementById(fieldId);
    const button = field.parentElement.querySelector(".btn-toggle-password");

    if (field.type === "password") {
        field.type = "text";
        button.textContent = "🙈";
    } else {
        field.type = "password";
        button.textContent = "👁️";
    }
}

function validatePasswords() {
    const password = document.getElementById("editPassword").value;
    const confirm = document.getElementById("confirmPassword").value;
    const errorDiv = document.getElementById("passwordMatchError");

    if (password && confirm && password !== confirm) {
        errorDiv.style.display = "block";
        return false;
    } else {
        errorDiv.style.display = "none";
        return true;
    }
}

function checkPasswordStrength() {
    const password = document.getElementById("editPassword").value;
    const strengthBar = document.getElementById("passwordStrength");

    let strength = 0;

    if (password.length >= 8) strength += 25;
    if (/[A-Z]/.test(password)) strength += 25;
    if (/[0-9]/.test(password)) strength += 25;
    if (/[^A-Za-z0-9]/.test(password)) strength += 25;

    strengthBar.style.width = strength + "%";

    if (strength < 50) {
        strengthBar.style.backgroundColor = "#dc3545";
    } else if (strength < 75) {
        strengthBar.style.backgroundColor = "#ffc107";
    } else {
        strengthBar.style.backgroundColor = "#28a745";
    }
}

function clearMessages() {
    document.getElementById("successMessage").style.display = "none";
    document.getElementById("errorMessage").style.display = "none";
    document.getElementById("successMessage").textContent = "";
    document.getElementById("errorMessage").textContent = "";
}

function showMessage(type, message) {
    const successDiv = document.getElementById("successMessage");
    const errorDiv = document.getElementById("errorMessage");

    if (type === "success") {
        successDiv.textContent = message;
        successDiv.style.display = "block";
        errorDiv.style.display = "none";
    } else {
        errorDiv.textContent = message;
        errorDiv.style.display = "block";
        successDiv.style.display = "none";
    }
}

async function updatePassword() {
    // Validar campos requeridos
    const password = document.getElementById("editPassword").value;
    const confirm = document.getElementById("confirmPassword").value;

    if (!password || !confirm) {
        showMessage("error", "❌ Todos los campos son requeridos");
        return;
    }

    if (!validatePasswords()) {
        showMessage("error", "❌ Las contraseñas no coinciden");
        return;
    }

    // Mostrar loading
    const submitBtn = document.getElementById("submitBtn");
    const originalText = submitBtn.textContent;
    submitBtn.textContent = "Guardando...";
    submitBtn.disabled = true;

    const jsonData = { new_pwd: password };

    console.log("jsonData: ", jsonData);

    try {
        const response = await fetch("/upd-pwd", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(jsonData),
        });

        const result = await response.json(jsonData);

        if (result.success) {
            showMessage("success", "✅ " + result.message);
            // Limpiar formulario después de éxito
            setTimeout(() => {
                document.getElementById("editPasswordForm").reset();
                closeModal();
            }, 2000);
        } else {
            showMessage("error", "❌ " + result.error);
        }
    } catch (error) {
        console.error("Error:", error);
        showMessage("error", "❌ Error de conexión");
    } finally {
        // Restaurar botón
        submitBtn.textContent = originalText;
        submitBtn.disabled = false;
    }
}

// Event listeners
document
    .getElementById("confirmPassword")
    .addEventListener("input", validatePasswords);
document.getElementById("editPassword").addEventListener("input", function () {
    validatePasswords();
    checkPasswordStrength();
});

// Permitir enviar con Enter
document
    .getElementById("editPasswordForm")
    .addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            updatePassword();
        }
    });

// Cerrar modal con Escape
document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && modal.classList.contains("active")) {
        closeModal();
    }
});
