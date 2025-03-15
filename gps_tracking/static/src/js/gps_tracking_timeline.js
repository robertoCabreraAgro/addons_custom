/** @odoo-module **/

import { GpsTrackingDashboard } from "./gps_tracking_dashboard";
import { registry } from "@web/core/registry";

export class GpsTrackingTimeline extends GpsTrackingDashboard {
    static template = "gps_tracking.gps_tracking_timeline_template";
    static props = {
        ...GpsTrackingDashboard.props,
    };

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
        if (device.the_point) {
            try {
                this.state.selectedDevice = device;  // 🟢 Asigna solo al dispositivo seleccionado
                console.log("Dispositivo seleccionado en el Kanban:", device);
                
                this.state.activeDevice = device;
                this.updateDeviceRoutes();

                const point = JSON.parse(device.the_point);
                const coords = [point.coordinates[0], point.coordinates[1]];

                // 🔴 Hacer zoom al dispositivo seleccionado sin afectar los checkboxes
                setTimeout(() => {
                    console.log("Iniciando animación del mapa...");
                    this.map.getView().animate({
                        center: coords,
                        zoom: 10,
                        duration: 500,
                    });
                }, 200);
            } catch (error) {
                console.error("Error al procesar device.the_point:", error);
            }
        }
    }
    updateDeviceRoutes() {
        if (!this.map) {
            console.error("El mapa no está inicializado.");
            return;
        }
    
        // 🔥 Eliminar SOLO capas de rutas sin afectar marcadores de íconos
        Object.values(this.state.routeLayers || {}).forEach(layer => {
            this.map.removeLayer(layer);
        });
    
        this.state.routeLayers = {}; // Limpiar almacenamiento de rutas
    
        // Filtrar dispositivos activos con checkbox marcado
        const activeDevices = this.state.devices.filter(device => 
            this.state.activeDevices.includes(device.imei)
        );
    
        if (activeDevices.length === 0) {
            console.log("No hay dispositivos activos para mostrar rutas.");
            return;
        }
    
        activeDevices.forEach(async (device) => {
            // 🔥 Verificar que `the_point` no sea null/undefined antes de intentar parsear
            if (!device.the_point) {
                console.warn(`El dispositivo ${device.imei} no tiene coordenadas.`);
                return;
            }
    
            try {
                const domain = [
                    ["device_id", "=", device.id],
                    ["timestamp", ">=", new Date(this.state.startDate).toISOString()],
                    ["timestamp", "<=", new Date(this.state.endDate).toISOString()]
                ];
    
                const points = await this.orm.searchRead("gps.tracking.point", domain, ["latitude", "longitude"]);
    
                if (!points || points.length === 0) {
                    console.log(`No se encontraron puntos para el dispositivo ${device.imei}`);
                    return;
                }
    
                // Convertir puntos GPS a coordenadas de OpenLayers
                const coordinates = points
                    .filter(point => point.latitude !== null && point.longitude !== null) // 🔥 Evitar errores con datos inválidos
                    .map(point => ol.proj.transform([point.longitude, point.latitude], "EPSG:4326", "EPSG:3857"));
    
                if (coordinates.length === 0) {
                    console.warn(`No hay coordenadas válidas para ${device.imei}`);
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
                this.state.routeLayers[device.imei] = lineLayer; // Guardar referencia
    
                console.log(`Ruta agregada para ${device.imei}`);
            } catch (error) {
                console.error(`Error al obtener recorrido del dispositivo ${device.imei}:`, error);
            }
        });
    }
    
    
    toggleDeviceRouteVisibility(device) {
        if (!device || !device.imei) {
            console.warn("Dispositivo inválido o nulo:", device);
            return;
        }
        const updatedActiveDevices = [...this.state.activeDevices];
        const deviceIndex = updatedActiveDevices.indexOf(device.imei);
    
        if (deviceIndex > -1) {
            updatedActiveDevices.splice(deviceIndex, 1);
            console.log("Checkbox desmarcado. Dispositivo ocultado:", device.imei);
        } else {
            updatedActiveDevices.push(device.imei);
            console.log("Checkbox marcado. Dispositivo mostrado:", device.imei);
        }
        this.state.activeDevices = updatedActiveDevices;
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
    
                // Obtener todos los puntos para la ruta
                const points = await this.orm.searchRead("gps.tracking.point", domain, ["latitude", "longitude"]);
                
                // Obtener el primer punto (el más antiguo)
                const firstPointResult = await this.orm.searchRead(
                    "gps.tracking.point", 
                    domain, 
                    ["latitude", "longitude", "timestamp"],
                    {
                        order: "timestamp ASC",
                        limit: 1
                    }
                );
                const firstPoint = firstPointResult[0];
                
                // Obtener el último punto (el más reciente)
                const lastPointResult = await this.orm.searchRead(
                    "gps.tracking.point", 
                    domain, 
                    ["latitude", "longitude", "timestamp"],
                    {
                        order: "timestamp DESC",
                        limit: 1
                    }
                );
                const lastPoint = lastPointResult[0];
                
                if (points.length === 0) {
                    console.log("No se encontraron puntos para el dispositivo:", device.imei);
                    continue;
                }
    
                const coordinates = points.map((point) => 
                    ol.proj.transform([point.longitude, point.latitude], "EPSG:4326", "EPSG:3857")
                );
    
                // Pasar también el primer y último punto al método de renderizado
                this.renderDevicePath(device, coordinates, firstPoint, lastPoint);
            }
    
            this.map.renderSync();
            setTimeout(() => this.map.renderSync(), 100);
    
        } catch (error) {
            console.error("Error al obtener recorridos:", error);
        }
    }
    
    renderDevicePath(device, coordinates, firstPoint, lastPoint) {
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
        this.state.deviceLayers[device.imei] = lineLayer;
    
        // Crear marcador para el primer punto (inicio de ruta)
        if (firstPoint) {
            const startCoord = ol.proj.transform([firstPoint.longitude, firstPoint.latitude], "EPSG:4326", "EPSG:3857");
            const startFeature = new ol.Feature({
                geometry: new ol.geom.Point(startCoord),
                name: `Inicio - ${device.imei}`,
                device: device.imei,
                timestamp: firstPoint.timestamp,
            });
    
            const startStyle = new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 7,
                    fill: new ol.style.Fill({ color: '#00FF00' }),
                    stroke: new ol.style.Stroke({ color: '#FFFFFF', width: 2 })
                }),
                text: new ol.style.Text({
                    text: 'Inicio',
                    offsetY: -20,
                    fill: new ol.style.Fill({ color: '#000000' }),
                    stroke: new ol.style.Stroke({ color: '#FFFFFF', width: 2 })
                })
            });
    
            startFeature.setStyle(startStyle);
            
            const startLayer = new ol.layer.Vector({
                source: new ol.source.Vector({
                    features: [startFeature]
                })
            });
            
            this.map.addLayer(startLayer);
            this.state.deviceLayers[`${device.imei}_start`] = startLayer;
        }
    
        // Crear marcador para el último punto (fin de ruta)
        if (lastPoint) {
            const endCoord = ol.proj.transform([lastPoint.longitude, lastPoint.latitude], "EPSG:4326", "EPSG:3857");
            const endFeature = new ol.Feature({
                geometry: new ol.geom.Point(endCoord),
                name: `Fin - ${device.imei}`,
                device: device.imei,
                timestamp: lastPoint.timestamp,
            });
    
            const endStyle = new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 7,
                    fill: new ol.style.Fill({ color: '#FF0000' }),
                    stroke: new ol.style.Stroke({ color: '#FFFFFF', width: 2 })
                }),
                text: new ol.style.Text({
                    text: 'Fin',
                    offsetY: -20,
                    fill: new ol.style.Fill({ color: '#000000' }),
                    stroke: new ol.style.Stroke({ color: '#FFFFFF', width: 2 })
                })
            });
    
            endFeature.setStyle(endStyle);
            
            const endLayer = new ol.layer.Vector({
                source: new ol.source.Vector({
                    features: [endFeature]
                })
            });
            
            this.map.addLayer(endLayer);
            this.state.deviceLayers[`${device.imei}_end`] = endLayer;
        }
    
        console.log("Línea y marcadores del dispositivo renderizados:", device.imei);
    }
    

    zoomToRoute() {
        if (!this.map || this.state.pathPoints.length === 0) {
            return;
        }

        const extent = [Infinity, Infinity, -Infinity, -Infinity];

        const transformedPoints = this.state.pathPoints.map((coord) =>
            ol.proj.transform(coord, "EPSG:4326", "EPSG:3857")
        );

        transformedPoints.forEach(([lon, lat]) => {
            extent[0] = Math.min(extent[0], lon); // Min Longitud
            extent[1] = Math.min(extent[1], lat); // Min Latitud
            extent[2] = Math.max(extent[2], lon); // Max Longitud
            extent[3] = Math.max(extent[3], lat); // Max Latitud
        });

        this.map.getView().fit(extent, {
            padding: [50, 50, 50, 50], // Agregar un margen alrededor
            duration: 1000,  // Animación de 1 segundo
        });

        console.log("Mapa ajustado a la ruta.");
    }
        // ✅ Método para Reiniciar Todo
    resetAll() {
        console.log("Reiniciando todo...");
        const layersToRemove = this.map.getLayers().getArray().filter(layer => layer instanceof ol.layer.Vector);
        layersToRemove.forEach(layer => this.map.removeLayer(layer));
        this.state.deviceLayers = {};
        this.state.routeLayers = {}; // 🔥 Ahora también eliminamos rutas
        this.state.activeDevices = [];
        this.state.selectedDevice = null;
        const today = new Date();
        today.setHours(0, 0, 0, 0); // Establece la hora en 00:00:00
        const formattedDate = today.toISOString().slice(0, 16); // Formato YYYY-MM-DDTHH:mm
        this.state.startDate = formattedDate;
        this.state.endDate = formattedDate;
        console.log(`Fechas reiniciadas: ${this.state.startDate} - ${this.state.endDate}`);
        document.querySelectorAll(".kanban_toggle_view input[type='checkbox']").forEach(checkbox => {
            checkbox.checked = false;
        });
        this.map.renderSync();
        setTimeout(() => this.map.renderSync(), 100);
        console.log("Mapa y estado reiniciados completamente.");
    }
}

// Registrar el nuevo componente en Odoo
registry.category("actions").add("gps_tracking_timeline", GpsTrackingTimeline);