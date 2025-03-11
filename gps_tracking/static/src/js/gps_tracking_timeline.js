/** @odoo-module **/

import { GpsTrackingDashboard } from "./gps_tracking_dashboard";
import { registry } from "@web/core/registry";

export class GpsTrackingTimeline extends GpsTrackingDashboard {
    static template = "gps_tracking.gps_tracking_timeline_template";

    setup() {
        super.setup();
        this.state.liveMode = false;
        this.state.pathPoints = [];
        this.state.deviceLayers = {};

        // 🟢 NUEVO: Estado separado para el dispositivo seleccionado en el Kanban
        this.state.selectedDevice = null;

        // 🔴 Definir fecha actual con hora 00:00
        const today = new Date();
        today.setHours(0, 0, 0, 0); // 🔥 Establece la hora en 00:00:00

        const formattedDate = today.toISOString().slice(0, 16); // Formato YYYY-MM-DDTHH:mm

        this.state.startDate = formattedDate;
        this.state.endDate = formattedDate;
        
        // 🔴 ELIMINAR la recarga automática
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        // 🔴 Desactivamos la carga de geocercas
        this.loadGeofences = async () => {
            console.log("Carga de geocercas desactivada en Timeline.");
        };
        this.addDeviceMarkers = async () => {
            console.log("Carga de devicemarkers desactivado en Timeline.");
        };
    }

    // ✅ Método para seleccionar un dispositivo desde el Kanban
    onCardClick(device) {
        this.state.selectedDevice = device;  // 🟢 Asigna solo al dispositivo seleccionado
        console.log("Dispositivo seleccionado en el Kanban:", device);
    
        // 🔴 Hacer zoom al dispositivo seleccionado sin afectar los checkboxes
        if (this.map && device.latitude && device.longitude) {
            this.map.getView().animate({
                center: [device.longitude, device.latitude],
                zoom: 15, 
                duration: 1000 
            });
        }
    }

    toggleDeviceVisibility(device) {
        if (!device || !device.imei) {
            console.warn("Dispositivo inválido o nulo:", device);
            return;
        }

        const deviceIndex = this.state.activeDevices.indexOf(device.imei);

        if (deviceIndex > -1) {
            // Eliminar el dispositivo de la lista activa si se desmarca
            this.state.activeDevices.splice(deviceIndex, 1);
            console.log("Checkbox desmarcado. Dispositivo ocultado:", device.imei);
        } else {
            // Añadir el dispositivo a la lista activa si se marca
            this.state.activeDevices.push(device.imei);
            console.log("Checkbox marcado. Dispositivo mostrado:", device.imei);
        }

        // Renderizar solo las rutas con checkbox activo
        this.fetchDevicePaths();
    }

    async fetchDevicePaths() {
        if (!this.state.startDate || !this.state.endDate) {
            alert("Selecciona un rango de fechas.");
            return;
        }

        // Eliminar todas las capas actuales del mapa antes de redibujar
        this.map.getLayers().getArray().forEach(layer => {
            if (layer instanceof ol.layer.Vector) {
                this.map.removeLayer(layer);
            }
        });

        // Vaciar completamente `deviceLayers` para evitar referencias residuales
        this.state.deviceLayers = {};

        // Obtener la lista de dispositivos activos (solo los con checkbox marcado)
        const activeDevices = this.state.activeDevices.slice();

        // Si no hay dispositivos activos, limpiar el mapa y salir
        if (activeDevices.length === 0) {
            console.log("No hay dispositivos activos. Mapa en blanco.");
            this.map.renderSync();
            setTimeout(() => this.map.renderSync(), 100);
            return;
        }

        const formattedStartDate = new Date(this.state.startDate).toISOString();
        const formattedEndDate = new Date(this.state.endDate).toISOString();

        try {
            for (const imei of activeDevices) {
                const device = this.state.devices.find(d => d.imei === imei);
                if (!device) continue;

                const domain = [
                    ["device_id", "=", device.id],
                    ["timestamp", ">=", formattedStartDate],
                    ["timestamp", "<=", formattedEndDate],
                ];

                const points = await this.orm.searchRead("gps.tracking.point", domain, ["latitude", "longitude"]);

                if (points.length === 0) {
                    console.log("No se encontraron puntos para el dispositivo:", device.imei);
                    continue;
                }

                const coordinates = points.map((point) => 
                    ol.proj.transform([point.longitude, point.latitude], "EPSG:4326", "EPSG:3857")
                );

                this.renderDevicePath(device, coordinates);
            }

            this.map.renderSync();
            setTimeout(() => this.map.renderSync(), 100);

        } catch (error) {
            console.error("Error al obtener recorridos:", error);
        }
    }
    
    renderDevicePath(device, coordinates) {
        if (!this.map || !device || !coordinates.length) {
            console.warn("Datos inválidos para renderizar la ruta del dispositivo:", device?.imei);
            return;
        }

        const lineFeature = new ol.Feature({
            geometry: new ol.geom.LineString(coordinates),
        });

        const lineLayer = new ol.layer.Vector({
            source: new ol.source.Vector({
                features: [lineFeature],
            }),
            style: new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: device.color || "#FF0000",
                    width: 3,
                }),
            }),
        });

        this.map.addLayer(lineLayer);

        // Guardar la capa para poder eliminarla después
        this.state.deviceLayers[device.imei] = lineLayer;

        console.log("Línea del dispositivo renderizada:", device.imei);
    }

    zoomToRoute() {
        if (!this.map || this.state.pathPoints.length === 0) {
            return;
        }

        const extent = [Infinity, Infinity, -Infinity, -Infinity];

        // 🔴 Transformar coordenadas de EPSG:4326 a EPSG:3857
        const transformedPoints = this.state.pathPoints.map((coord) =>
            ol.proj.transform(coord, "EPSG:4326", "EPSG:3857")
        );

        // 🔴 Recorrer los puntos transformados y calcular el extent
        transformedPoints.forEach(([lon, lat]) => {
            extent[0] = Math.min(extent[0], lon); // Min Longitud
            extent[1] = Math.min(extent[1], lat); // Min Latitud
            extent[2] = Math.max(extent[2], lon); // Max Longitud
            extent[3] = Math.max(extent[3], lat); // Max Latitud
        });

        // 🔴 Ajustar el mapa a la extensión calculada en EPSG:3857
        this.map.getView().fit(extent, {
            padding: [50, 50, 50, 50], // Agregar un margen alrededor
            duration: 1000,  // Animación de 1 segundo
        });

        console.log("Mapa ajustado a la ruta.");
    }
        // ✅ Método para Reiniciar Todo
    resetAll() {
        console.log("Reiniciando todo...");

        // 🧹 Eliminar todas las capas vectoriales de forma segura
        const layersToRemove = this.map.getLayers().getArray().filter(layer => layer instanceof ol.layer.Vector);

        layersToRemove.forEach(layer => {
            this.map.removeLayer(layer);
        });

        // 🧹 Vaciar el estado de las capas para evitar residuos
        this.state.deviceLayers = {};
        this.state.activeDevices = [];
        this.state.selectedDevice = null;

        // 🔲 Desmarcar todos los checkboxes en la interfaz
        document.querySelectorAll(".kanban_toggle_view input[type='checkbox']").forEach(checkbox => {
            checkbox.checked = false;
        });

        // 🔄 Llamar dos veces a renderSync para asegurar el reinicio completo
        this.map.renderSync();
        setTimeout(() => this.map.renderSync(), 100);

        console.log("Mapa y estado reiniciados completamente.");
    }
}

// Registrar el nuevo componente en Odoo
registry.category("actions").add("gps_tracking_timeline", GpsTrackingTimeline);