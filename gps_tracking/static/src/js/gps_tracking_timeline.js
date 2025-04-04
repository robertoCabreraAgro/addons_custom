/** @odoo-module **/

import { GpsTrackingDashboard } from "./gps_tracking_dashboard";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
export class GpsTrackingTimeline extends GpsTrackingDashboard {
    static template = "gps_tracking.gps_tracking_timeline_template";
    static props = {
        ...GpsTrackingDashboard.props,
    };

    // Initializes the component state and configuration
    setup() {
        super.setup();
        this.state.liveMode = false;
        this.state.pathPoints = [];
        this.state.deviceLayers = {};
        this.state.selectedDevice = null;
        this.state.firstOdometers = 0; 
        this.state.initialFuel = 0;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const formattedDate = today.toISOString().slice(0, 16);
        this.state.startDate = formattedDate;
        this.state.endDate = formattedDate;

        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        this.loadGeofences = async () => {
            console.log("Carga de geocercas desactivada en Timeline.");
        };
        this.addDeviceMarkers = async () => {
            console.log("Carga de devicemarkers desactivado en Timeline.");
        };
    }

    // Handles device selection from the Kanban view and centers the map on its location
    onCardClick(device) {
        if (device.the_point) {
            try {
                this.state.selectedDevice = device;

                this.state.activeDevice = device;
                this.updateDeviceRoutes();

                const point = JSON.parse(device.the_point);
                const coords = [point.coordinates[0], point.coordinates[1]];

                setTimeout(() => {
                    console.log("Iniciando animación del mapa...");
                    this.map.getView().animate({
                        center: coords,
                        zoom: 13,
                        duration: 500,
                    });
                }, 200);
            } catch (error) {
                console.error("Error al procesar device.the_point:", error);
            }
        }
    }

    // Updates the route layers for active devices on the map
    updateDeviceRoutes() {
        if (!this.map) {
            console.error("El mapa no está inicializado.");
            return;
        }
        this.cleanupAllLayers();
        const activeDevices = this.state.devices.filter(device =>
            this.state.activeDevices.includes(device.imei)
        );
        if (activeDevices.length === 0) {
            console.log("No hay dispositivos activos para mostrar rutas.");
            return;
        }
        activeDevices.forEach(async (device) => {
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
                const points = await this.orm.searchRead(
                    "gps.tracking.point", domain, 
                    [
                        "latitude", 
                        "longitude", 
                        "ignition", 
                        "speed", 
                        "odometer", 
                        "timestamp",
                        "movement",  
                        "fuel_consumed_counted"
                    ]
                );
                if (!points || points.length === 0) {
                    console.log(`No se encontraron puntos para el dispositivo ${device.imei}`);
                    return;
                }
                const coordinates = points
                    .filter(point => point.latitude !== null && point.longitude !== null)
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
                this.state.routeLayers[device.imei] = lineLayer;
                console.log(`Ruta agregada para ${device.imei}`);
            } catch (error) {
                console.error(`Error al obtener recorrido del dispositivo ${device.imei}:`, error);
            }
        });
    }

    cleanupAllLayers() {
        const layers = this.map.getLayers().getArray().slice();
        layers.forEach(layer => {
            if (layer instanceof ol.layer.Vector) {
                this.map.removeLayer(layer);
            }
        });
        this.state.routeLayers = {};
        this.state.deviceLayers = {};
        console.log("Todas las capas vectoriales eliminadas completamente");
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
        this.refreshMapWithActiveDevices();
    }

    refreshMapWithActiveDevices() {
        this.cleanupAllLayers();
        if (this.state.activeDevices.length === 0) {
            console.log("No hay dispositivos activos para mostrar");
            this.map.renderSync();
            return;
        }
        this.fetchDevicePaths();
    }

    async fetchDevicePaths() {
        if (!this.state.startDate || !this.state.endDate) {
            alert("Selecciona un rango de fechas.");
            return;
        }
        this.cleanupAllLayers();
        const activeDevices = this.state.activeDevices.slice();
        if (activeDevices.length === 0) {
            console.log("No hay dispositivos activos. Mapa en blanco.");
            this.map.renderSync();
            return;
        }
        const formattedStartDate = new Date(this.state.startDate).toISOString();
        const formattedEndDate = new Date(this.state.endDate).toISOString();
        try {
            for (const imei of activeDevices) {
                const device = this.state.devices.find(d => d.imei === imei);
                if (!device) {
                    console.warn(`Dispositivo ${imei} no encontrado en la lista de dispositivos`);
                    continue;
                }
                const domain = [
                    ["device_id", "=", device.id],
                    ["timestamp", ">=", formattedStartDate],
                    ["timestamp", "<=", formattedEndDate],
                ];
                const points = await this.orm.searchRead(
                    "gps.tracking.point",
                    domain,
                    [
                        "latitude", 
                        "longitude", 
                        "ignition", 
                        "speed", 
                        "odometer", 
                        "timestamp", 
                        "movement", 
                        "fuel_consumed_counted"
                    ]
                );
                console.log("Puntos obtenidos para", device.imei, points);
                if (points.length === 0) {
                    console.log("No se encontraron puntos para el dispositivo:", device.imei);
                    continue;
                }
                points.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

                device.points = points;
                const coordinates = points.map((point) =>
                    ol.proj.transform([point.longitude, point.latitude], "EPSG:4326", "EPSG:3857")
                );
                const firstPoint = points[0];
                
                this.state.firstOdometers = firstPoint?.odometer || 0;
                this.state.firstFuel = firstPoint?.fuel_consumed_counted || 0;
                const lastPoint = points[points.length - 1]
                this.renderDevicePath(device, coordinates, firstPoint, lastPoint);
            }
            this.map.renderSync();
        } catch (error) {
            console.error("Error al obtener recorridos:", error);
        }
    }

    // Removes all vector layers from the map
    clearAllVectorLayers() {
        const layersToRemove = this.map.getLayers().getArray().filter(layer =>
            layer instanceof ol.layer.Vector
        );
        layersToRemove.forEach(layer => {
            this.map.removeLayer(layer);
        });
        this.state.deviceLayers = {};
        this.state.routeLayers = {};
        console.log("Todas las capas vectoriales han sido eliminadas del mapa");
    }

    // Renders a device's path on the map with start and end markers
    renderDevicePath(device, coordinates, firstPoint, lastPoint) {
        if (!this.map || !device || !coordinates || coordinates.length === 0) {
            console.warn("Datos inválidos para renderizar la ruta del dispositivo:", device?.imei);
            return;
        }
    
        // Crear capa para la línea de la ruta
        const lineFeature = new ol.Feature({
            geometry: new ol.geom.LineString(coordinates),
            name: `Ruta - ${device.imei}`,
            device: device.imei
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
            zIndex: 5,
            id: `route_${device.imei}`
        });
    
        this.map.addLayer(lineLayer);
        this.state.deviceLayers[device.imei] = lineLayer;

        const getColorBySpeed = (speed, ignition) => {
            const ign = Number(ignition);
            const spd = Number(speed);
        
            if (spd === 0 && ign === 0) {
                return {
                    fill: new ol.style.Fill({ color: "#0033A0" }), // 🔵
                    radius: 5,
                    z: 20
                };
            }
            if (spd === 0 && ign === 1) {
                return {
                    fill: new ol.style.Fill({ color: "#FBC02D" }), // 🟡
                    radius: 3,
                    z: 10
                };
            }
            if (spd > 110) {
                return {
                    fill: new ol.style.Fill({ color: "#FB8C00" }), // 🟠
                    radius: 3,
                    z: 5
                };
            }
            if (spd > 125) {
                return {
                    fill: new ol.style.Fill({ color: "#D32F2F" }), // 🔴
                    radius: 3,
                    z: 5
                };
            }
            return {
                fill: new ol.style.Fill({ color: "#388E3C" }), // 🟢
                radius: 3,
                z: 0
            };
        };
    
        const pointFeatures = device.points.map((point, index) => {
            const coord = ol.proj.transform([point.longitude, point.latitude], "EPSG:4326", "EPSG:3857");
            const { fill, radius, z } = getColorBySpeed(
                Number(point.speed) || 0,
                Number(point.ignition)
            );
            

            const pointFeature = new ol.Feature({
                geometry: new ol.geom.Point(coord),
                name: `Punto ${index + 1} - ${device.imei}`,
                device: device.imei,
                timestamp: point.timestamp || "Desconocido",
                speed: point.speed || 0,
                odometer: point.odometer || 0,
                ignition: point.ignition,
                movement: point.movement,
                fuel_consumed_counted: point.fuel_consumed_counted || 0, 
            });
    
            pointFeature.setStyle(new ol.style.Style({
                image: new ol.style.Circle({
                    radius,
                    fill
                }),
                zIndex: z,
            }));
    
            return pointFeature;
        });
    
        // Agregar marcador para el primer punto
        if (firstPoint && firstPoint.latitude && firstPoint.longitude) {
            const firstCoord = ol.proj.transform([firstPoint.longitude, firstPoint.latitude], "EPSG:4326", "EPSG:3857");
            const firstFeature = new ol.Feature({
                geometry: new ol.geom.Point(firstCoord),
                name: `Inicio - ${device.imei}`,
                device: device.imei,
                timestamp: firstPoint.timestamp,
                speed: firstPoint.speed || 0,
                odometer: firstPoint.odometer || 0
            });
    
            firstFeature.setStyle(new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 6,
                    zIndex:50,
                    fill: new ol.style.Fill({ color: '#00FF00' }), // Verde para el inicio
                }),
            }));
    
            pointFeatures.push(firstFeature);
        }
    
        // Agregar marcador para el último punto
        if (lastPoint && lastPoint.latitude && lastPoint.longitude) {
            const lastCoord = ol.proj.transform([lastPoint.longitude, lastPoint.latitude], "EPSG:4326", "EPSG:3857");
            const lastFeature = new ol.Feature({
                geometry: new ol.geom.Point(lastCoord),
                name: `Fin - ${device.imei}`,
                device: device.imei,
                timestamp: lastPoint.timestamp,
                speed: lastPoint.speed || 0,
                odometer: lastPoint.odometer || 0
            });
    
            lastFeature.setStyle(new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 6,
                    zIndex:50,
                    fill: new ol.style.Fill({ color: '#FF0000' }), // Rojo para el final
                }),
            }));
    
            pointFeatures.push(lastFeature);
        }
    
        // Agregar los puntos al mapa
        const pointLayer = new ol.layer.Vector({
            source: new ol.source.Vector({
                features: pointFeatures,
            }),
            zIndex: 10,
            id: `points_${device.imei}`
        });
    
        this.map.addLayer(pointLayer);
        this.state.deviceLayers[`${device.imei}_points`] = pointLayer;
    
        console.log(`Ruta, puntos y marcadores de inicio/fin del dispositivo ${device.imei} renderizados correctamente.`);
    }
    

    // Adjusts the map view to fit the entire route
    zoomToRoute() {
        if (!this.map || this.state.pathPoints.length === 0) {
            return;
        }
        const extent = [Infinity, Infinity, -Infinity, -Infinity]
        const transformedPoints = this.state.pathPoints.map((coord) =>
            ol.proj.transform(coord, "EPSG:4326", "EPSG:3857")
        );
        transformedPoints.forEach(([lon, lat]) => {
            extent[0] = Math.min(extent[0], lon);
            extent[1] = Math.min(extent[1], lat);
            extent[2] = Math.max(extent[2], lon);
            extent[3] = Math.max(extent[3], lat);
        });
        this.map.getView().fit(extent, {
            padding: [50, 50, 50, 50],
            duration: 1000,
        });
        console.log("Mapa ajustado a la ruta.");
    }

    _displayFeatureInfo(pixel, target, click = false) {
        if (!this.map || this.state.drawingToolActive) {
            return;
        }
        const tooltipElement = this.tooltipRef?.el;
        if (!tooltipElement) {
            console.error("Tooltip no encontrado en el DOM.");
            return;
        }
        let closestFeature = null;
        this.map.forEachFeatureAtPixel(pixel, (feature) => {
            if (feature.getGeometry().getType() === "Point") {
                closestFeature = feature;
            }
        });
        if (!closestFeature) {
            this._hideTooltip();
            return;
        }
        
        const timestamp = closestFeature.get("timestamp") || "Desconocido";
        const movement = closestFeature.get("movement") || "Desconocido";
        const ignition = closestFeature.get("ignition") || "Desconocido";
        const plate = closestFeature.get("device_id") || closestFeature.get("imei") || "Desconocido";
        const speed = closestFeature.get("speed") || 0;
        const currentOdometer = closestFeature.get("odometer") || 0;
        const currentFuel = closestFeature.get("fuel_consumed_counted") || 0;
        console.log("currentOdometer",currentOdometer)
        console.log("currentFuel",currentFuel)
        const imei = closestFeature.get("device");

        const initialOdometer = this.state.firstOdometers;
        const initialFuel = this.state.firstFuel;
        console.log("initialOdometer",initialOdometer)
        console.log("initialFuel",initialFuel)
        const consumedFuel = currentFuel - initialFuel;
        const distanceTraveled = currentOdometer - initialOdometer;
        tooltipElement.style.visibility = "visible";
        tooltipElement.style.left = pixel[0] + "px";
        tooltipElement.style.top = pixel[1] + "px";
        let formattedTime = timestamp
        ? new Date(timestamp + "Z").toLocaleString("es-MX", { timeZone: "America/Mexico_City" })
        : "";
        tooltipElement.innerHTML = `
            <div style="min-width: 200px;">
                <strong>Plate:</strong> ${plate}<br/>
                <strong>Velocidad:</strong> ${speed} km/h<br/>
                <strong>Encendido:</strong>
                <span style="color: ${ignition == 1 ? 'green' : 'red'};">
                    <i class="fa fa-power-off" style="margin-right: 5px;"></i>
                    ${ignition == 1 ? 'Encendido' : 'Apagado'}
                </span><br/>
                <strong>Odómetro:</strong> ${distanceTraveled.toFixed(2)} km<br/>
                <strong>Fuel:</strong> ${consumedFuel.toFixed(2)} km<br/>
                <strong>Hora:</strong> ${formattedTime}<br/>
                <button id="btn-street" class="btn btn-sm btn-info" style="margin-top:5px;">
                    Ver Street View
                </button>
            </div>
        `;
    }

    // Resets the component state and clears the map
    resetAll() {
        console.log("Reiniciando todo...");
        const layersToRemove = this.map.getLayers().getArray().filter(layer => layer instanceof ol.layer.Vector);
        layersToRemove.forEach(layer => this.map.removeLayer(layer));
        this.state.deviceLayers = {};
        this.state.routeLayers = {};
        this.state.activeDevices = [];
        this.state.selectedDevice = null;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const formattedDate = today.toISOString().slice(0, 16);
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

registry.category("actions").add("gps_tracking_timeline", GpsTrackingTimeline);