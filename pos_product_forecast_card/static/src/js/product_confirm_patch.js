


import { openQtyModalWithWarehouses } from "@pos_product_forecast_card/js/custom_qty_modal_loader";



export function ConfirmAndPropagate(ev, popup, originalOnClick, almacenesArg) {
    // Usar el servicio popup OWL si está disponible
    if (popup) {
        popup.add({
            title: "Agregar producto",
            body: "¿Cuántas unidades deseas agregar?",
            confirmText: "Agregar",
            cancelText: "Cancelar",
            inputType: "number",
            inputDefault: "1",
            inputLabel: "Cantidad",
            onConfirm: (qtyStr) => {
                const qty = parseFloat(qtyStr);
                if (isNaN(qty) || qty <= 0) return;
                const parent = ev.currentTarget.parentElement;
                if (parent && parent.tagName === 'ARTICLE') {
                    parent.setAttribute('data-jem-qty', qty);
                    parent.click();
                }
                // Llamar el onClick original si existe
                if (typeof originalOnClick === 'function') {
                    originalOnClick.call(this, ev);
                }
            },
        });
        return;
    }
    // Si no hay popup OWL, usar modal propio y pasar el target
    const target = ev.currentTarget;
    // Validar contexto OWL y servicio rpc
    console.log('[POS][DEBUG] this.env:', this.env);
    if (this.pos && this.pos.env) {
        console.log('[POS][DEBUG] this.pos.env:', this.pos.env);
    }
    if (!this.env) {
        console.error('[POS] No se encontró this.env en el contexto OWL. El componente no está correctamente inicializado.');
        return;
    }
    let envForRpc = this.env;
    let rpcService = null;
    // Buscar servicios en this.env.services o this.pos.env.services
    const tryServices = [
        this.env && this.env.services,
        this.pos && this.pos.env && this.pos.env.services
    ];
    for (const services of tryServices) {
        if (!services) continue;
        if (services.rpc) {
            rpcService = services.rpc;
            break;
        }
        if (services.fetch) {
            rpcService = services.fetch;
            break;
        }
        if (services.orm) {
            rpcService = services.orm;
            break;
        }
    }
    if (!rpcService) {
        console.error('[POS] No se encontró ningún servicio de red (rpc, fetch, orm) en this.env.services ni en this.pos.env.services.');
        return;
    }
    // Crear un envForRpc falso con solo el servicio encontrado
    envForRpc = { services: { rpc: rpcService } };
    // Obtener lotes y caducidades del producto seleccionado
    const product = this && this.props && this.props.product;
    const prodName = product && (product.display_name || product.name) || "Producto";
    const lots = (this && this.pos && this.pos.lots) ? this.pos.lots.filter(l => l.product_id && l.product_id[0] === product.id) : [];
    console.log('[POS] Producto seleccionado:', product);
    console.log('[POS] Lotes encontrados para el producto:', lots);
    // Usar almacenes pasados desde el patch si existen
    let almacenes = Array.isArray(almacenesArg) && almacenesArg.length ? almacenesArg : [];
    console.log('[PATCH] Almacenes que se pasan al modal:', almacenes);
    const productos = lots.length ? lots.map(lot => ({
        id: product.id,
        prod: prodName,
        lote: lot.name,
        caducidad: lot.life_date || lot.expiration_date || '-',
        cantidad: 1
    })) : [{ id: product.id, prod: prodName, lote: '-', caducidad: '-', cantidad: 1 }];
    console.log('[POS] Datos para la tabla del modal:', productos);
    openQtyModalWithWarehouses({
        productos,
        almacenes, // pasar almacenes con forecasted_quantity
        defaultValue: "1",
        onConfirm: ({ cantidades }) => {
            // Suma todas las cantidades ingresadas (puedes cambiar la lógica si solo quieres la primera)
            const qty = cantidades && cantidades.length ? cantidades.reduce((a, b) => a + b, 0) : 1;
            if (isNaN(qty) || qty <= 0) return;
            const parent = target && target.parentElement;
            if (parent && parent.tagName === 'ARTICLE') {
                parent.setAttribute('data-jem-qty', qty);
                parent.click();
            }
            // Llamar el onClick original si existe
            if (typeof originalOnClick === 'function') {
                originalOnClick.call(this, ev);
            }
        },
        onCancel: () => {},
    }, envForRpc);
}

// Esta función debe ser usada en el patch principal para interceptar el click y agregar el producto con la cantidad indicada
