/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { SearchModel } from "@web/search/search_model";
import { GpsSearchbar } from "../components/searchbar/gps_searchbar";

export class GpsTrackingDashboard extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: [String, Number], optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
        searchViewId: { type: Number, optional: true },
        context: { type: Object, optional: true },
        searchDomain: { type: Array, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            devices: [],
            filteredDevices: [],
            activeDevices: [],
            activeDevice: null,
            expandedDevices: new Set(),
            tooltipLocked: false, // <-- Indica si el tooltip está "bloqueado"
            startDate: null,
            endDate: null,
            pathPoints: [],
        });
        this.map = null;
        this.vectorLayer = null;
        this.mapInitialized = false;

        this.mapContainerRef = useRef("mapContainer");
        this.tooltipRef = useRef("tooltip");

        // Cada vez que cambie searchDomain, recarga o filtra
        onWillUpdateProps((nextProps) => {
            if (nextProps.searchDomain !== this.props.searchDomain) {
                // Se ha actualizado el dominio => recargamos
                this._reloadDevicesWithDomain(nextProps.searchDomain);
            }
        });

        // Llamar a la función de actualización periódicamente (cada 10 segundos)
        this.refreshInterval = setInterval(() => {
            this.refreshData();
        }, 1000); // 10 segundos

        onWillStart(async () => {
            // Acceder al contexto correctamente
            const context = this.props.action.context || {};
            const searchViewId = context.search_view_id;
            console.log("searchViewId:", searchViewId);

            // Cargar los dispositivos inicialmente
            await this.loadDevices();
            this.state.filteredDevices = [...this.state.devices];
            await this.loadOpenLayers();
        });

        onMounted(() => {
            if (this.mapContainerRef.el) {
                console.log("mapContainer está disponible.");
                this.initializeMap();
                this.addDeviceMarkers();
                this.loadGeofences(); // Cargar geocercas al iniciar el mapa
                this.mapInitialized = true;
            } else {
                console.error("mapContainer no está disponible en onMounted.");
                setTimeout(() => {
                    if (this.mapContainerRef.el) {
                        this.initializeMap();
                        this.addDeviceMarkers();
                        this.mapInitialized = true;
                    } else {
                        console.error("mapContainer sigue sin estar disponible.");
                    }
                }, 0);
            }
        });

        onWillUnmount(() => {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
                console.log("Intervalo de actualización limpiado.");
            }
        });
    }

    async _reloadDevicesWithDomain(domain) {
        console.log("Recargando con domain:", domain);
        // Llama a searchRead en gps.tracking.device con ese domain
        try {
            const devices = await this.orm.searchRead(
                "gps.tracking.device",
                domain || [],
                ["id", "imei", "the_point", "speed", "timestamp", "altitude", "satellite", "address", "gsm_signal", "ignition", "movement", "color", "vehicle_id", "license_plate", "driver_name", "total_odometer"]
            );
            this.state.devices = devices;
            this.state.filteredDevices = devices;
            // Actualizar marcadores si lo deseas, etc.
        } catch (error) {
            console.error("Error al recargar dispositivos:", error);
        }
    }

    async loadDevices() {
        try {
            const devices = await this.orm.searchRead(
                "gps.tracking.device",
                [],
                ["id", "imei", "the_point", "speed", "timestamp", "altitude", "satellite", "address", "gsm_signal", "ignition", "movement", "color", "vehicle_id", "license_plate", "driver_name", "total_odometer"]
            );
            this.state.devices = devices;
        } catch (error) {
            console.error("Error al cargar los dispositivos:", error);
            this.state.devices = [];
        }
    }

    toggleExpand(device) {
        if (this.state.expandedDevices.has(device.imei)) {
            this.state.expandedDevices.delete(device.imei); // Contraer
        } else {
            this.state.expandedDevices.add(device.imei); // Expandir
        }
        // Forzar re-render
        this.state.expandedDevices = new Set(this.state.expandedDevices);
    }

    // Método para refrescar los datos
    async refreshData() {
        console.log("Actualizando datos...");
        // llamamos a _reloadDevicesWithDomain() usando el dominio actual de las props.
        await this._reloadDevicesWithDomain(this.props.searchDomain || []);
        // Ajustamos los marcadores
        this.updateDeviceMarkers();
        console.log("Datos actualizados.");
    }

    // Cargar OpenLayers de forma global
    async loadOpenLayers() {
        try {
            await loadJS("/base_geoengine/static/lib/ol-10.1.0/ol.js");
            if (typeof ol === "undefined") {
                throw new Error("OpenLayers no está definido después de la carga.");
            }
            console.log("OpenLayers cargado correctamente.");
        } catch (error) {
            console.error("Error al cargar OpenLayers:", error);
        }
    }

    // Ocultar tooltip
    _hideTooltip() {
        const tooltipElement = this.tooltipRef.el;
        if (tooltipElement) {
            tooltipElement.style.visibility = "hidden";
        }
    }

    // Mostrar la info del Feature, si existe
    _displayFeatureInfo(pixel, target, click = false) {

        if (this.state.drawingToolActive) {
            // No mostrar el tooltip si la herramienta de dibujo está activa
            return;
        }

        const tooltipElement = this.tooltipRef.el;
        if (!tooltipElement) return;

        // Verificar si el cursor está sobre un control OL
        const feature = target.closest(".ol-control")
            ? undefined
            : this.map.forEachFeatureAtPixel(pixel, (f) => f);

        if (feature) {
            tooltipElement.style.visibility = "visible";
            tooltipElement.style.left = pixel[0] + "px";
            tooltipElement.style.top = pixel[1] + "px";

            // Recopilar datos del feature
            const imei = feature.get("imei") || "Desconocido";
            const speed = feature.get("speed") || 0;
            const ignition = feature.get("ignition") || 0;
            const movement = feature.get("movement") || 0;

            // Contenido base del tooltip
            tooltipElement.innerHTML = `
            <div style="min-width: 200px;">
                <strong>IMEI:</strong> ${imei}<br/>
                <strong>Velocidad:</strong> ${speed} km/h<br/>
                <strong>Encendido:</strong>
                <span style="color: ${ignition == 1 ? 'green' : 'red'};">
                    <i class="fa fa-power-off" style="margin-right: 5px;"></i>
                    ${ignition == 1 ? 'Encendido' : 'Apagado'}
                </span><br/>
                <strong>Movimiento:</strong>
                <span style="color: ${movement == 1 ? 'green' : 'red'};">
                    <i class="fa fa-car" style="margin-right: 5px;"></i>
                    ${movement == 1 ? 'En movimiento' : 'Estacionado'}
                </span><br/>
                <button id="btn-street" class="btn btn-sm btn-info" style="margin-top:5px;">
                    Ver Street View
                </button>
            </div>
            `;

            // Asignar listeners tras crear el contenido
            setTimeout(() => {
                // Botón StreetView
                const btnStreet = document.getElementById("btn-street");
                if (btnStreet) {
                    btnStreet.addEventListener("click", (evt) => {
                        evt.stopPropagation();  // Evitar que el mapa lo oculte
                        this._showStreetViewInsideTooltip(tooltipElement, feature);
                    });
                }
            }, 0);

        } else {
            this._hideTooltip();
        }
    }

    _generateStreetViewEmbedUrl(lat, lng, apiKey) {
        const baseUrl = "https://www.google.com/maps/embed/v1/streetview";
        return `${baseUrl}?key=${apiKey}&location=${lat},${lng}`;
    }

    _showStreetViewInsideTooltip(tooltipElement, feature) {
        // 1. Obtener coords EPSG:3857 => EPSG:4326
        const coords3857 = feature.getGeometry().getCoordinates();
        const coords4326 = ol.proj.transform(coords3857, 'EPSG:3857', 'EPSG:4326');
        const lat = coords4326[1];
        const lng = coords4326[0];

        // 2. Generar la URL embed con tu API Key
        const apiKey = "";  // <-- pon tu clave real
        const embedUrl = this._generateStreetViewEmbedUrl(lat, lng, apiKey);

        // 3. Guardar contenido anterior del tooltip
        const oldContent = tooltipElement.innerHTML;

        console.log(embedUrl)

        // 4. Renderizar el iFrame con la URL embed
        tooltipElement.innerHTML = `
            <div style="position: relative; width: 400px; height: 300px;">
                <button id="close-streetview"
                        style="position: absolute; top: 3px; right: 3px; z-index: 10;"
                        class="btn btn-sm btn-danger">
                    Cerrar
                </button>
                <iframe
                    src="${embedUrl}"
                    style="width: 100%; height: 100%; border: none;"
                    allow="geolocation; accelerometer; gyroscope; autoplay"
                    allowfullscreen>
                </iframe>
            </div>
        `;

        // 5. Manejar el botón “Cerrar”
        setTimeout(() => {
            const btnClose = document.getElementById("close-streetview");
            if (btnClose) {
                btnClose.addEventListener("click", () => {
                    tooltipElement.innerHTML = oldContent;
                    // Re-asignar el evento al botón “Ver Street View” que tenías en el contenido anterior
                    const btnStreet = document.getElementById("btn-street");
                    if (btnStreet) {
                        btnStreet.addEventListener("click", () => {
                            this._showStreetViewInsideTooltip(tooltipElement, feature);
                        });
                    }
                });
            }
        }, 0);
    }


    initializeMap() {
        if (!this.mapContainerRef.el) {
            console.error("mapContainer no está disponible.");
            return;
        }

        // Crear el mapa con su capa base
        this.map = new ol.Map({
            target: this.mapContainerRef.el,
            layers: [
                new ol.layer.Tile({
                    source: new ol.source.XYZ({
                        url: "https://mts1.google.com/vt/lyrs=r&x={x}&y={y}&z={z}&key=TU_CLAVE_API",
                    }),
                }),
            ],
            view: new ol.View({
                center: ol.proj.fromLonLat([0, 0]),
                zoom: 2,
            }),
        });

        console.log("Mapa inicializado:", this.map);

        // Manejar pointermove para tooltip
        this.map.on("pointermove", (evt) => {
            // Evitar tooltip si se está arrastrando el mapa
            if (evt.dragging) {
                this._hideTooltip();
                this.state.tooltipLocked = false;
                return;
            }

            // Si el tooltip está bloqueado, no queremos ocultarlo ni moverlo.
            if (this.state.tooltipLocked) {
                return;
            }
            // Si NO está bloqueado, ejecutamos la lógica de mostrar/ocultar:
            this._displayFeatureInfo(evt.pixel, evt.originalEvent.target);
        });

        // Ocultar tooltip al salir del contenedor
        this.map.getTargetElement().addEventListener("pointerleave", () => {
            this._hideTooltip();
        });
    }

    addDeviceMarkers() {
        if (!this.map) {
            console.error("El mapa no está inicializado.");
            return;
        }

        // Elimina los marcadores existentes
        if (this.vectorLayer) {
            this.map.removeLayer(this.vectorLayer);
        }

        // Crea nuevos marcadores como Features
        const features = this.state.filteredDevices.map((device) => {
            if (device.the_point) {
                const point = JSON.parse(device.the_point);
                // Nota: coords en EPSG:3857 => posible proyección de tus datos
                const coords = [point.coordinates[0], point.coordinates[1]];
                return new ol.Feature({
                    geometry: new ol.geom.Point(coords),
                    imei: device.imei,
                    speed: device.speed,
                    ignition: device.ignition,
                    movement: device.movement,
                });
            }
        }).filter((feature) => feature);

        const vectorSource = new ol.source.Vector({
            features: features,
        });

        this.vectorLayer = new ol.layer.Vector({
            source: vectorSource,
            style: new ol.style.Style({
                image: new ol.style.Circle({
                    radius: 6,
                    fill: new ol.style.Fill({ color: "#FF0000" }),
                    stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
                }),
            }),
        });

        this.map.addLayer(this.vectorLayer);
    }

    toggleDeviceVisibility(device) {
        const index = this.state.activeDevices.indexOf(device.imei);
        if (index === -1) {
            // Agregar a la lista de dispositivos activos
            this.state.activeDevices.push(device.imei);
        } else {
            // Eliminar de la lista de dispositivos activos
            this.state.activeDevices.splice(index, 1);
        }
        this.updateDeviceMarkers();
    }

    updateDeviceMarkers() {
        if (!this.map) {
            console.error("El mapa no está inicializado.");
            return;
        }

        // Eliminar marcadores existentes
        if (this.vectorLayer) {
            this.map.removeLayer(this.vectorLayer);
        }

        // Crear marcadores para dispositivos activos
        const features = this.state.devices
            .filter((device) => this.state.activeDevices.includes(device.imei))
            .map((device) => {
                if (device.the_point) {
                    const point = JSON.parse(device.the_point);
                    const coords = [point.coordinates[0], point.coordinates[1]];
                    return new ol.Feature({
                        geometry: new ol.geom.Point(coords),
                        imei: device.imei,
                        speed: device.speed,
                        ignition: device.ignition,
                        movement: device.movement,
                    });
                }
            }).filter((feature) => feature);

        const vectorSource = new ol.source.Vector({ features });

        // Cambiar el estilo para usar íconos personalizados
        this.vectorLayer = new ol.layer.Vector({
            source: vectorSource,
            style: (feature) => {
                const isActive = this.state.activeDevice && this.state.activeDevice.imei === feature.get("imei");
                return new ol.style.Style({
                    image: new ol.style.Icon({
                        anchor: [0.5, 1],
                        src: isActive ? '/gps_tracking/static/src/img/active-icon.png' : '/gps_tracking/static/src/img/default-icon.png', // Rutas de íconos
                        scale: 0.3,
                    }),
                });
            },
        });

        this.map.addLayer(this.vectorLayer);
    }

    // Animación ejemplo (si lo necesitas)
    animateFeature(feature) {
        const startRadius = 6;
        const endRadius = 10;
        const startColor = [255, 0, 0, 1]; // Rojo
        const endColor = [0, 255, 144, 1]; // Verde
        const duration = 500; // Duración de la animación en ms

        const startTime = Date.now();

        const step = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);

            const interpolatedRadius = startRadius + progress * (endRadius - startRadius);
            const interpolatedColor = startColor.map((start, index) =>
                start + progress * (endColor[index] - start)
            );

            feature.setStyle(
                new ol.style.Style({
                    image: new ol.style.Circle({
                        radius: interpolatedRadius,
                        fill: new ol.style.Fill({ color: `rgba(${interpolatedColor.join(",")})` }),
                        stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
                    }),
                })
            );

            if (progress < 1) {
                requestAnimationFrame(step);
            }
        };

        step();
    }

    onCardClick(device) {
        if (!this.map) {
            console.error("El mapa aún no está inicializado.");
            return;
        }

        if (device.the_point) {
            try {
                console.log("Dispositivo seleccionado:", device);

                // Actualizar el dispositivo activo y el estilo de los marcadores
                this.state.activeDevice = device;
                this.updateDeviceMarkers();

                // Obtener las coordenadas
                const point = JSON.parse(device.the_point);
                const coords = [point.coordinates[0], point.coordinates[1]];

                // Animar el mapa
                setTimeout(() => {
                    console.log("Iniciando animación del mapa...");
                    this.map.getView().animate({
                        center: coords,
                        zoom: 15,
                        duration: 500,
                    });
                }, 200);
            } catch (error) {
                console.error("Error al procesar device.the_point:", error);
            }
        }
    }

    async loadGeofences() {
        try {
            const geofences = await this.orm.searchRead(
                "gps.geofence",
                [["active", "=", true]],
                ["id", "name", "geometry", "color"]
            );
            console.log("Geocercas cargadas:", geofences);

            const features = geofences.map((geofence) => {
                const geom = JSON.parse(geofence.geometry); // Validar que el JSON sea válido
                const color = geofence.color || "#FF0000";

                // Convertir coordenadas de EPSG:4326 a EPSG:3857
                const transformedCoords = geom.coordinates.map((ring) =>
                    ring.map((coord) => ol.proj.transform(coord, "EPSG:4326", "EPSG:3857"))
                );

                // Crear la feature usando las coordenadas transformadas
                return new ol.Feature({
                    geometry: new ol.geom.Polygon(transformedCoords),
                    name: geofence.name,
                    color: color,
                });
            });

            const vectorSource = new ol.source.Vector({
                features: features,
            });

            this.geofenceLayer = new ol.layer.Vector({
                source: vectorSource,
                style: (feature) => {
                    return new ol.style.Style({
                        stroke: new ol.style.Stroke({
                            color: feature.get("color"),
                            width: 2,
                        }),
                        fill: new ol.style.Fill({
                            color: feature.get("color") + "44", // Transparente
                        }),
                    });
                },
            });

            this.map.addLayer(this.geofenceLayer);
            console.log("Geocercas añadidas al mapa.");
        } catch (error) {
            console.error("Error al cargar las geocercas:", error);
        }
    }

    checkDeviceInGeofence(device) {
        const point = new ol.geom.Point([device.longitude, device.latitude]);
        let inside = false;

        this.geofenceLayer.getSource().getFeatures().forEach((feature) => {
            if (feature.getGeometry().intersectsCoordinate(point.getCoordinates())) {
                inside = true;
                console.log(`${device.imei} está dentro de la geocerca: ${feature.get("name")}`);
            }
        });

        if (!inside) {
            console.log(`${device.imei} está fuera de todas las geocercas.`);
        }
    }

    addGeofenceDrawingTool() {
        // Verificar si la capa de geocercas está inicializada
        if (!this.geofenceLayer) {
            console.error("La capa de geocercas no está inicializada.");
            return;
        }

        // Alternar la herramienta de dibujo
        if (this.state.drawingToolActive) {
            this.map.removeInteraction(this.state.drawingInteraction);
            this.state.drawingToolActive = false;
            this.state.drawingInteraction = null;
            console.log("Herramienta de dibujo desactivada desde el botón.");
            alert("La herramienta de dibujo se ha desactivado.");
            return;
        }

        // Crear una nueva interacción de dibujo
        const draw = new ol.interaction.Draw({
            source: this.geofenceLayer.getSource(),
            type: "Polygon", // Cambia a 'Circle' si deseas geocercas circulares
        });

        draw.on("drawend", async (event) => {
            const geometry = event.feature.getGeometry().clone().transform('EPSG:3857', 'EPSG:4326'); // Convertir a EPSG:4326
            const geoJson = new ol.format.GeoJSON().writeGeometry(geometry);

            console.log("Nueva Geocerca creada (GeoJSON):", geoJson);

            const name = prompt("Ingrese un nombre para la geocerca:");
            const color = prompt("Ingrese un color para la geocerca (ej. #FF0000):", "#FF0000");

            try {
                const newGeofence = {
                    name: name || "Geocerca sin nombre",
                    geometry: geoJson,
                    color: color || "#FF0000",
                    active: true,
                };

                // Guardar la geocerca en Odoo
                const result = await this.orm.create("gps.geofence", [newGeofence]);
                console.log("Geocerca guardada en Odoo:", result);
                alert(`Geocerca "${name}" guardada correctamente.`);
            } catch (error) {
                console.error("Error al guardar la geocerca en Odoo:", error);
                alert("Hubo un error al guardar la geocerca.");
            }

            // Desactivar la herramienta de dibujo después de guardar
            this.map.removeInteraction(draw);
            this.state.drawingToolActive = false;
            console.log("Herramienta de dibujo desactivada automáticamente.");
        });

        // Agregar interacción al mapa
        this.map.addInteraction(draw);
        this.state.drawingInteraction = draw;
        this.state.drawingToolActive = true;
        console.log("Herramienta de dibujo activada.");
        alert("La herramienta de dibujo se ha activado.");
    }

    // Recorrido por fechas
    // Recorrido por fechas
    async fetchDevicePath() {
        if (!this.state.startDate || !this.state.endDate) {
            alert("Selecciona un rango de fechas.");
            return;
        }

        // Convertir fechas locales a UTC dentro del contexto de la clase
        const formattedStartDate = this.localToUTC(this.state.startDate);
        const formattedEndDate = this.localToUTC(this.state.endDate);

        // Imprimir fechas formateadas
        console.log("Fecha de inicio (UTC):", formattedStartDate);
        console.log("Fecha de fin (UTC):", formattedEndDate);
        console.log("Device ID del dispositivo activo:", this.state.activeDevice.id);

        try {
            // Crear el dominio con las fechas en UTC
            const domain = [
                ["device_id", "=", this.state.activeDevice.id], // Usamos el ID del dispositivo
                ["timestamp", ">=", formattedStartDate],
                ["timestamp", "<=", formattedEndDate],
            ];
            console.log("Dominio enviado al backend:", domain);

            const points = await this.orm.searchRead(
                "gps.tracking.point",
                domain,
                ["latitude", "longitude", "timestamp"]
            );

            // Imprimir resultado de la consulta
            console.log("Puntos obtenidos del backend:", points);

            if (points.length === 0) {
                alert("No se encontraron puntos en el rango de fechas seleccionado.");
                return;
            }

            this.state.pathPoints = points.map((point) => [
                point.longitude,
                point.latitude,
            ]);

            console.log("Puntos formateados para OpenLayers:", this.state.pathPoints);
            this.renderDevicePath();
        } catch (error) {
            console.error("Error al obtener el recorrido:", error);
        }
    }

    // Método para ajustar la fecha local 
    localToUTC(dateString) {
        const date = new Date(dateString);
        return new Date(
            date.getTime() // Añadir 6 horas en milisegundos
        ).toISOString().slice(0, 19).replace("T", " ");
    }

    renderDevicePath() {
        if (!this.map || this.state.pathPoints.length === 0) return;

        // Transformar las coordenadas a EPSG:3857 para OpenLayers
        const coordinates = this.state.pathPoints.map((coord) =>
            ol.proj.transform(coord, "EPSG:4326", "EPSG:3857")
        );

        // Crear la geometría de línea con los puntos
        const lineFeature = new ol.Feature({
            geometry: new ol.geom.LineString(coordinates),
        });

        // Crear la capa de línea y agregarla al mapa
        const lineLayer = new ol.layer.Vector({
            source: new ol.source.Vector({
                features: [lineFeature],
            }),
            style: new ol.style.Style({
                stroke: new ol.style.Stroke({
                    color: "#FF0000", // Color de la línea
                    width: 3,        // Ancho de la línea
                }),
            }),
        });

        // Eliminar cualquier capa anterior de recorrido
        if (this.state.pathLayer) {
            this.map.removeLayer(this.state.pathLayer);
        }

        this.state.pathLayer = lineLayer; // Guardar referencia a la capa de recorrido
        this.map.addLayer(lineLayer);

        console.log("Recorrido renderizado en el mapa.");
    }

}

// Acciones y componentes
GpsTrackingDashboard.components = { ControlPanel, GpsSearchbar, SearchBar };
GpsTrackingDashboard.template = "gps_tracking.gps_tracking_dashboard_template";

GpsTrackingDashboard.prototype.onSearch = async function (query) {
    console.log("Iniciando búsqueda en el Dashboard:", query);
    const filteredDevices = this.state.devices.filter((device) =>
        device.imei.toLowerCase().includes(query.toLowerCase())
    );
    console.log("Dispositivos filtrados en el Dashboard:", filteredDevices);

    this.state.filteredDevices = filteredDevices;
    this.updateDeviceMarkers(filteredDevices); // Actualizar el mapa
};

registry.category("actions").add("gps_tracking_dashboard", GpsTrackingDashboard);