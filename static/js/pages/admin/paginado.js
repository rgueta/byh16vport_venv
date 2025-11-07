let paginaActual = 1;
let porPagina = 25;
let busquedaActual = "";
let totalPaginas = 1;

// Cargar usuarios al iniciar
document.addEventListener("DOMContentLoaded", function () {
    cargarUsuarios();
});

// Función principal para cargar usuarios
async function cargarUsuarios(pagina = 1) {
    mostrarLoading(true);

    try {
        const params = new URLSearchParams({
            pagina: pagina,
            por_pagina: porPagina,
            busqueda: busquedaActual,
        });

        console.log(`url -->  /admin/usuarios?${params}`);
        const response = await fetch(`/admin/usuarios?${params}`);
        const data = await response.json();

        if (response.ok) {
            paginaActual = data.paginacion.pagina_actual;
            totalPaginas = data.paginacion.total_paginas;

            mostrarUsuarios(data.usuarios);
            actualizarPaginacion(data.paginacion);
            actualizarInfoPaginacion(data.paginacion);
        } else {
            alert("Error: " + data.error);
        }
    } catch (error) {
        console.error("Error:", error);
        alert("Error de conexión");
    } finally {
        mostrarLoading(false);
    }
}

// Mostrar usuarios en la tabla
function mostrarUsuarios(usuarios) {
    const cuerpoTabla = document.getElementById("cuerpoTabla");
    cuerpoTabla.innerHTML = "";

    if (usuarios.length === 0) {
        cuerpoTabla.innerHTML =
            '<tr><td colspan="6" style="text-align: center;">No se encontraron usuarios</td></tr>';
        return;
    }

    usuarios.forEach((usuario) => {
        const fila = document.createElement("tr");
        fila.innerHTML = `
         <td>${usuario.id}</td>
         <td>${usuario.nombre} ${usuario.ap} ${usuario.am}</td>
         <td>${usuario.email}</td>
         <td>${usuario.tipo}</td>
         <td>${usuario.cell || ""}</td>
         <td>${usuario.activo === "1" ? "Activo" : "Inactivo"}</td>
         <td>${usuario.operador === "1" ? "Si" : "No"}</td>
     `;
        cuerpoTabla.appendChild(fila);
    });
}

// Actualizar controles de paginación
function actualizarPaginacion(paginacion) {
    const paginacionHTML = generarPaginacionHTML(paginacion);
    document.getElementById("paginacionSuperior").innerHTML = paginacionHTML;
    document.getElementById("paginacionInferior").innerHTML = paginacionHTML;
}

// Generar HTML de paginación
function generarPaginacionHTML(paginacion) {
    let html = "";

    // Botón Primera página
    if (paginacion.has_prev) {
        html += `<button onclick="irAPagina(1)">« Primera</button>`;
        html += `<button onclick="irAPagina(${paginacion.pagina_actual - 1})">‹ Anterior</button>`;
    }

    // Números de página (mostrar solo algunas páginas alrededor de la actual)
    const inicio = Math.max(1, paginacion.pagina_actual - 2);
    const fin = Math.min(
        paginacion.total_paginas,
        paginacion.pagina_actual + 2,
    );

    for (let i = inicio; i <= fin; i++) {
        if (i === paginacion.pagina_actual) {
            html += `<button disabled style="background-color: #007bff; color: white;">${i}</button>`;
        } else {
            html += `<button onclick="irAPagina(${i})">${i}</button>`;
        }
    }

    // Botón Última página
    if (paginacion.has_next) {
        html += `<button onclick="irAPagina(${paginacion.pagina_actual + 1})">Siguiente ›</button>`;
        html += `<button onclick="irAPagina(${paginacion.total_paginas})">Última »</button>`;
    }

    return html;
}

// Ir a página específica
function irAPagina(pagina) {
    if (pagina >= 1 && pagina <= totalPaginas) {
        cargarUsuarios(pagina);
    }
}

// Buscar usuarios
function buscarUsuarios() {
    busquedaActual = document.getElementById("busqueda").value;
    cargarUsuarios(1); // Volver a primera página
}

// Limpiar búsqueda
function limpiarBusqueda() {
    document.getElementById("busqueda").value = "";
    busquedaActual = "";
    cargarUsuarios(1);
}

// Actualizar información de paginación
function actualizarInfoPaginacion(paginacion) {
    const inicio = (paginacion.pagina_actual - 1) * paginacion.por_pagina + 1;
    const fin = Math.min(
        inicio + paginacion.por_pagina - 1,
        paginacion.total_usuarios,
    );

    document.getElementById("infoPaginacion").innerHTML = `
     Mostrando ${inicio} - ${fin} de ${paginacion.total_usuarios} usuarios
     | Página ${paginacion.pagina_actual} de ${paginacion.total_paginas}
     | <select onchange="cambiarRegistrosPorPagina(this.value)">
         <option value="25" ${porPagina === 25 ? "selected" : ""}>25 por página</option>
         <option value="50" ${porPagina === 50 ? "selected" : ""}>50 por página</option>
         <option value="100" ${porPagina === 100 ? "selected" : ""}>100 por página</option>
       </select>
 `;
}

// Cambiar cantidad de registros por página
function cambiarRegistrosPorPagina(cantidad) {
    porPagina = parseInt(cantidad);
    cargarUsuarios(1); // Volver a primera página
}

// Mostrar/ocultar loading
function mostrarLoading(mostrar) {
    document.getElementById("loading").style.display = mostrar
        ? "block"
        : "none";
}

// Búsqueda con Enter
document.getElementById("busqueda").addEventListener("keypress", function (e) {
    if (e.key === "Enter") {
        buscarUsuarios();
    }
});
