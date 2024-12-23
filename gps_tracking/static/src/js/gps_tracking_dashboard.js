/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { SearchModel } from "@web/search/search_model";
import { GpsSearchbar } from "../components/searchbar/gps_searchbar";

class GpsTrackingDashboard extends Component {
    static props = {
        action: { type: Object, optional: true },
        actionId: { type: [String, Number], optional: true },
        updateActionState: { type: Function, optional: true },
        className: { type: String, optional: true },
        searchViewId: { type: Number, optional: true },
        context: { type: Object, optional: true },
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
        });
        this.map = null;
        this.vectorLayer = null;
        this.mapInitialized = false;

        this.mapContainerRef = useRef("mapContainer");
        this.tooltipRef = useRef("tooltip");

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
    }

    async loadDevices() {
        try {
            const devices = await this.orm.searchRead(
                "gps.tracking.device",
                [],
                ["id", "imei", "the_point", "speed", "timestamp", "altitude", "satellite", "address"]
            );
            console.log("Dispositivos cargados:", devices);
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
        await this.loadDevices(); // Recargar dispositivos
        this.state.filteredDevices = [...this.state.devices];
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
    
            // Contenido base del tooltip
            tooltipElement.innerHTML = `
                <div style="min-width: 200px;">
                    <strong>IMEI:</strong> ${imei}<br/>
                    <strong>Velocidad:</strong> ${speed} km/h<br/>
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
        const apiKey = "AIzaSyABRnjE6R9eY-5RvAoc2_jHvtcRPvnh7D4";  // <-- pon tu clave real
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
                    });
                }
            }).filter((feature) => feature);

        const vectorSource = new ol.source.Vector({ features });

        this.vectorLayer = new ol.layer.Vector({
            source: vectorSource,
            style: (feature) => {
                const isActive = this.state.activeDevice && this.state.activeDevice.imei === feature.get("imei");
                return new ol.style.Style({
                    image: new ol.style.Circle({
                        radius: isActive ? 10 : 6,
                        fill: new ol.style.Fill({ color: isActive ? "#00FF90" : "#FF0000" }),
                        stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
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
}

// Acciones y componentes
GpsTrackingDashboard.components = { ControlPanel, GpsSearchbar };
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