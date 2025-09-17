import { showCustomQtyModal } from "@pos_product_forecast_card/js/custom_qty_modal";

export function openQtyModalWithWarehouses(args, env) {
    // Obtener el product_id desde args.productos[0] si existe
    const productId = args && args.productos && args.productos[0] && args.productos[0].id;
    if (!productId) {
        alert('No se encontró el id del producto para consultar stock por almacén.');
        return;
    }
    if (env && env.services && env.services.rpc) {
        const rpc = env.services.rpc;
        if (typeof rpc === 'function') {
            rpc('pos.warehouse.api', 'get_warehouses_with_stock', [productId]).then(function(warehouses) {
                console.log('[LOADER] almacenes recibidos del modelo:', warehouses);
                showCustomQtyModal({...args, almacenes: warehouses});
            });
        } else if (typeof rpc === 'object' && typeof rpc.call === 'function') {
            rpc.call('pos.warehouse.api', 'get_warehouses_with_stock', [productId]).then(function(warehouses) {
                console.log('[LOADER] almacenes recibidos del modelo:', warehouses);
                showCustomQtyModal({...args, almacenes: warehouses});
            });
        } else if (typeof rpc === 'object' && typeof rpc.fetch === 'function') {
            rpc.fetch('/pos_product_forecast_card/get_warehouses_with_stock', {
                method: 'POST',
                body: JSON.stringify({ product_id: productId })
            })
                .then(response => response.json ? response.json() : response)
                .then(function(warehouses) {
                    console.log('[LOADER] almacenes recibidos del endpoint:', warehouses);
                    showCustomQtyModal({...args, almacenes: warehouses});
                });
        } else {
            alert('El servicio de red encontrado no es compatible.');
        }
    } else {
        alert('No se encontró el servicio de red (rpc, fetch, orm) en el contexto POS.');
    }
}
