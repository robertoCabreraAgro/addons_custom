/** @odoo-module **/

import { GpsTrackingDashboard } from "./gps_tracking_dashboard";
import { registry } from "@web/core/registry";

export class GpsTrackingTimeline extends GpsTrackingDashboard {
    static template = "gps_tracking.gps_tracking_timeline_template";

    setup() {
        super.setup();
        this.state.liveMode = false;
        this.state.pathPoints = [];

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
        this.state.activeDevice = device;  // 🔴 Asignamos el dispositivo activo
        console.log("Dispositivo seleccionado:", device);
    
        // 🔴 Verificamos que el mapa y el dispositivo tengan coordenadas válidas
        if (this.map && device.latitude && device.longitude) {
            this.map.getView().animate({
                center: [device.longitude, device.latitude],
                zoom: 15,  // Ajusta el zoom según prefieras
                duration: 1000  // Suaviza la animación en 1 segundo
            });
        }
    }

    async fetchDevicePath() {
        if (!this.state.activeDevice) {
            alert("Selecciona un dispositivo antes de buscar.");
            return;
        }
        if (!this.state.startDate || !this.state.endDate) {
            alert("Selecciona un rango de fechas.");
            return;
        }

        const formattedStartDate = new Date(this.state.startDate).toISOString();
        const formattedEndDate = new Date(this.state.endDate).toISOString();

        try {
            const domain = [
                ["device_id", "=", this.state.activeDevice.id],
                ["timestamp", ">=", formattedStartDate],
                ["timestamp", "<=", formattedEndDate],
            ];

            const points = await this.orm.searchRead("gps.tracking.point", domain, ["latitude", "longitude"]);

            if (points.length === 0) {
                alert("No se encontraron puntos en el rango seleccionado.");
                return;
            }

            this.state.pathPoints = points.map((point) => [point.longitude, point.latitude]);

            // 🔴 Obtener el color del dispositivo
            this.state.routeColor = this.state.activeDevice.color || "#FF0000";  // Rojo si no tiene color asignado

            this.zoomToRoute();
            this.renderDevicePath();
        } catch (error) {
            console.error("Error al obtener recorrido:", error);
        }
    }

    renderDevicePath() {
        if (!this.map || this.state.pathPoints.length === 0) return;
    
        // 🔴 Transformar coordenadas de EPSG:4326 a EPSG:3857
        const coordinates = this.state.pathPoints.map((coord) =>
            ol.proj.transform(coord, "EPSG:4326", "EPSG:3857")
        );
    
        // 🔴 Crear la línea con el color seleccionado
        const lineFeature = new ol.Feature({
            geometry: new ol.geom.LineString(coordinates),
        });
    
        const lineLayer = new ol.layer.Vector({
            source: new ol.source.Vector({
                features: [lineFeature],
            }),
            style: new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: this.state.routeColor,  // 🔴 Usamos el color del dispositivo
                    width: 3,
                }),
            }),
        });
    
        // 🔴 Remover la capa anterior si ya existía
        if (this.state.pathLayer) {
            this.map.removeLayer(this.state.pathLayer);
        }
    
        this.state.pathLayer = lineLayer;
        this.map.addLayer(lineLayer);
    
        console.log("Recorrido renderizado con color:", this.state.routeColor);
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
}

// Registrar el nuevo componente en Odoo
registry.category("actions").add("gps_tracking_timeline", GpsTrackingTimeline);