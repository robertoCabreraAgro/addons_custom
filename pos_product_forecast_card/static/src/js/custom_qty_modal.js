// Simple reusable modal for quantity input in Odoo POS (no OWL service required)
// Usage: showCustomQtyModal({ title, message, defaultValue, onConfirm, onCancel })

export function showCustomQtyModal({
    title = "Producto total:",
    almacenes = ["Principal", "Secundario"], 
  productos = [
    { prod: "Producto A", lote: "L001", caducidad: "2025-12-31", cantidad: 5 },
    { prod: "Producto B", lote: "L002", caducidad: "2026-01-15", cantidad: 2 },
  ], // Cada producto debe tener: prod, lote, caducidad, cantidad
    defaultValue = "1",
    onConfirm = () => {},
    onCancel = () => {},
} = {}) {

    const old = document.getElementById("qty-modal");
    if (old) old.remove();

    // Modal HTML
    const modal = document.createElement("div");
    modal.id = "qty-modal";
    // Generar opciones almacén
    const options = almacenes.map((a, i) => `<option value="${i}">${a.name || a}</option>`).join("");
    // Generar filas de productos con lote y caducidad

    const rows = productos.map((p, i) => `
      <tr>
        <td>${p.prod}</td>
        <td>${p.lote || "-"}</td>
        <td>${p.caducidad || "-"}</td>
        <td><input class="qty-table-input" type="number" min="0" value="${p.cantidad}" data-row="${i}" style="width:60px;text-align:center;"></td>
      </tr>
    `).join("");

    modal.innerHTML = `
      <div class="modal-overlay"></div>
      <div class="modal-box minimal">
        <div class="modal-header-row">
          <label for="almacen-select" class="modal-label">Location</label>
          <select id="almacen-select" class="modal-select">${options}</select>
          <label for="ubicacion-select" class="modal-label" style="margin-left:1em;">Ubicación</label>
          <select id="ubicacion-select" class="modal-select"></select>
        </div>
        <h3 class="modal-title" id="modal-title-dynamic"></h3>
        <table class="modal-table">
          <thead>
            <tr><th>Prod</th><th>Lote</th><th>Caducidad</th><th>Cantidad</th></tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
        <div class="modal-actions">
          <button id="qty-ok">Aceptar</button>
          <button id="qty-cancel">Cancelar</button>
        </div>
      </div>
      <style>
        #qty-modal { position: fixed; z-index: 99999; left: 0; top: 0; width: 100vw; height: 100vh; font-family: 'Inter', Arial, sans-serif; }
        .modal-overlay { position: absolute; left: 0; top: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.18); }
        .modal-box.minimal { position: absolute; left: 50%; top: 50%; transform: translate(-50%,-50%); background: #fff; border-radius: 10px; padding: 1.5em 2em 1.5em 2em; box-shadow: 0 2px 24px #0002; min-width: 340px; max-width: 95vw; text-align: left; }
        .modal-header-row { display: flex; align-items: center; gap: 1em; margin-bottom: 1em; }
        .modal-label { font-size: 1em; color: #444; }
        .modal-select { font-size: 1em; padding: 0.2em 0.8em; border-radius: 5px; border: 1px solid #bbb; background: #fafbfc; }
        .modal-title { font-size: 1.1em; font-weight: 600; margin: 0.5em 0 1em 0; color: #222; }
        .modal-table { width: 100%; border-collapse: collapse; margin-bottom: 1em; }
        .modal-table th, .modal-table td { border-bottom: 1px solid #eee; padding: 0.4em 0.3em; text-align: center; font-size: 0.98em; }
        .modal-table th { color: #666; font-weight: 500; background: #fafbfc; }
        .qty-table-input { border: 1px solid #bbb; border-radius: 4px; padding: 0.2em 0.4em; font-size: 1em; width: 60px; }
        .modal-actions { margin-top: 1.2em; display: flex; gap: 1em; justify-content: flex-end; }
        .modal-actions button { font-size: 1em; padding: 0.4em 1.2em; border-radius: 5px; border: none; background: #2d8cf0; color: #fff; cursor: pointer; transition: background 0.2s; }
        .modal-actions button#qty-cancel { background: #eee; color: #444; }
        .modal-actions button:hover { filter: brightness(0.95); }
      </style>
    `;

    // Lógica para actualizar ubicaciones al cambiar almacén
    async function updateUbicaciones() {
      const selectAlmacen = document.getElementById("almacen-select");
      const selectUbicacion = document.getElementById("ubicacion-select");
      if (!selectAlmacen || !selectUbicacion) return;
      const almacenIdx = parseInt(selectAlmacen.value, 10);
      const almacenObj = almacenes[almacenIdx];
      // Obtener product_id del primer producto (ajusta si tienes varios)
      const productId = productos && productos[0] && productos[0].id;
      if (!almacenObj || !almacenObj.id || !productId) return;
      // Llamada al endpoint para ubicaciones
      let ubicaciones = [];
      try {
        const resp = await fetch('/pos_product_forecast_card/get_locations_with_stock', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ warehouse_id: almacenObj.id, product_id: productId })
        });
        ubicaciones = await resp.json();
      } catch (e) {
        ubicaciones = [];
      }
      // Llenar el select de ubicaciones
      selectUbicacion.innerHTML = ubicaciones.map((u, i) => `<option value="${i}">${u.name} (${u.forecasted_quantity})</option>`).join("");
    }

    function updateTitle() {
      const select = document.getElementById("almacen-select");
      const selectUbicacion = document.getElementById("ubicacion-select");
      const titleEl = document.getElementById("modal-title-dynamic");
      if (!select || !titleEl) return;
      const almacenIdx = parseInt(select.value, 10);
      const almacenObj = almacenes[almacenIdx];
      let total = 0;
      let ubicacionLabel = '';
      // Si hay select de ubicaciones y una seleccionada, muestra su stock
      if (selectUbicacion && selectUbicacion.options.length) {
        const ubicacionIdx = parseInt(selectUbicacion.value, 10);
        const ubicacionObj = selectUbicacion.options[ubicacionIdx];
        if (ubicacionObj && ubicacionObj.text) {
          // Extraer el stock de la opción (formato: Nombre (stock))
          const match = ubicacionObj.text.match(/\(([-\d\.]+)\)$/);
          if (match) {
            total = parseFloat(match[1]);
          }
          ubicacionLabel = ubicacionObj.text;
        }
      } else if (typeof almacenObj === 'object' && 'forecasted_quantity' in almacenObj) {
        total = almacenObj.forecasted_quantity;
      } else if (productos && productos.length) {
        total = productos.reduce((acc, p) => acc + (p.cantidad || 0), 0);
      }
      let almacenLabel = almacenObj && (almacenObj.name || almacenObj) || '';
      titleEl.innerText = ubicacionLabel
        ? `${title} (${almacenLabel} - ${ubicacionLabel}): ${total}`
        : `${title} (${almacenLabel}): ${total}`;
    }

    // Inicializar título y event listener cuando el DOM esté listo
    updateTitle();
    updateUbicaciones();
    const select = document.getElementById("almacen-select");
    const selectUbicacion = document.getElementById("ubicacion-select");
    if (select) {
      select.addEventListener('change', () => {
        updateTitle();
        updateUbicaciones();
      });
    }
    if (selectUbicacion) {
      selectUbicacion.addEventListener('change', updateTitle);
    }
    document.body.appendChild(modal);

    // Focus primer input de cantidad
    setTimeout(() => {
      const firstInput = modal.querySelector(".qty-table-input");
      if (firstInput) firstInput.focus();
    }, 100);

    // Handlers
    function close() {
      modal.remove();
    }
    document.getElementById("qty-ok").onclick = () => {
      // Recoger cantidades editadas
      const cantidades = Array.from(modal.querySelectorAll('.qty-table-input')).map(input => parseFloat(input.value) || 0);
      const almacenIdx = parseInt(document.getElementById("almacen-select").value, 10);
      const almacenObj = almacenes[almacenIdx];
      close();
      onConfirm({ almacen: almacenObj, cantidades });
    };
    document.getElementById("qty-cancel").onclick = () => {
      close();
      onCancel();
    };
    // Enter/Escape en inputs
    modal.querySelectorAll('.qty-table-input').forEach(input => {
      input.onkeydown = (e) => {
        if (e.key === "Enter") document.getElementById("qty-ok").click();
        if (e.key === "Escape") document.getElementById("qty-cancel").click();
      };
    });

    modal.querySelector(".modal-overlay").onclick = () => {
      close();
      onCancel();
    };

  return modal;
}
