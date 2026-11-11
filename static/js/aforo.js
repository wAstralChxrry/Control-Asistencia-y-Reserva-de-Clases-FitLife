const contador = document.getElementById("aforo");
const estadoAforo = document.getElementById("aforo-estado");

if (contador && estadoAforo) {
    async function actualizarAforo() {
        const controlador = new AbortController();
        const limite = setTimeout(() => controlador.abort(), 8000);

        try {
            const respuesta = await fetch(contador.dataset.url, {
                signal: controlador.signal,
                cache: "no-store",
            });
            if (!respuesta.ok) {
                throw new Error("No se pudo actualizar el aforo");
            }
            const datos = await respuesta.json();
            if (!Number.isInteger(datos.aforo) || datos.aforo < 0) {
                throw new Error("La respuesta del aforo no es válida");
            }
            contador.textContent = datos.aforo;
            estadoAforo.textContent = "Aforo actualizado";
        } catch (error) {
            estadoAforo.textContent = "Sin conexión: aforo posiblemente desactualizado";
        } finally {
            clearTimeout(limite);
            setTimeout(actualizarAforo, 2000);
        }
    }

    setTimeout(actualizarAforo, 2000);
}
