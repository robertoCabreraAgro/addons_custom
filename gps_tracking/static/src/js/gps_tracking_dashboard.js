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
            filteredDevices: [], // Añadido para manejar dispositivos filtrados
            activeDevices: [], // Lista de dispositivos visibles en el mapa
            activeDevice: null, // Añadido para rastrear el dispositivo activo
            expandedDevices : new Set(),
        });
        this.map = null;
        this.vectorLayer = null;
        this.mapInitialized = false;

        this.mapContainerRef = useRef('mapContainer');

        onWillStart(async () => {
            // Acceder al contexto correctamente
            const context = this.props.action.context || {};
            const searchViewId = context.search_view_id;
            console.log('searchViewId:', searchViewId);


            // Cargar los dispositivos inicialmente
            await this.loadDevices();
            this.state.filteredDevices = [...this.state.devices]; // Inicializar con todos los dispositivos
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
            const devices = await this.orm.searchRead("gps.tracking.device", [], ["id", "imei", "the_point", "speed", "timestamp", "altitude", "satellite", "address"]);
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
        this.state.expandedDevices = new Set(this.state.expandedDevices); // Forzar re-render
    }

    // Método para refrescar los datos
    async refreshData() {
        console.log("Actualizando datos...");
        await this.loadDevices(); // Recargar dispositivos
        this.state.filteredDevices = [...this.state.devices]; // Actualizar los dispositivos filtrados
        this.updateDeviceMarkers(); // Actualizar los marcadores en el mapa
        console.log("Datos actualizados.");
    }

    async loadOpenLayers() {
        try {
            await loadJS('/base_geoengine/static/lib/ol-10.1.0/ol.js');
            if (typeof ol === 'undefined') {
                throw new Error('OpenLayers no está definido después de la carga.');
            }
            console.log('OpenLayers cargado correctamente.');
        } catch (error) {
            console.error('Error al cargar OpenLayers:', error);
        }
    }

    initializeMap() {
        if (!this.mapContainerRef.el) {
            console.error("mapContainer no está disponible en las referencias.");
            return;
        }
        this.map = new ol.Map({
            target: this.mapContainerRef.el,
            layers: [
                new ol.layer.Tile({
                    source: new ol.source.XYZ({
                        url: 'https://mts1.google.com/vt/lyrs=r&x={x}&y={y}&z={z}&key=TU_CLAVE_API',
                    }),
                }),
            ],
            view: new ol.View({
                center: ol.proj.fromLonLat([0, 0]),
                zoom: 2,
            }),
        });
        console.log("Mapa inicializado:", this.map);
    }

    addDeviceMarkers() {
        if (!this.map) {
            console.error("El mapa no está inicializado.");
            return;
        }
        // Utiliza filteredDevices para mostrar solo los dispositivos filtrados
        const features = this.state.filteredDevices.map((device) => {
            if (device.the_point) {
                try {
                    const point = JSON.parse(device.the_point);
                    const coords = [point.coordinates[0], point.coordinates[1]];
                    return new ol.Feature({
                        geometry: new ol.geom.Point(coords),
                        imei: device.imei,
                    });
                } catch (error) {
                    console.error('Error al procesar device.the_point:', error);
                }
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
                    fill: new ol.style.Fill({ color: '#FF0000' }),
                    stroke: new ol.style.Stroke({ color: '#fff', width: 2 }),
                }),
            }),
        });
    
        this.map.addLayer(this.vectorLayer);
    }

    // Alternar la visibilidad del dispositivo
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
            .filter(device => this.state.activeDevices.includes(device.imei)) // Solo los seleccionados
            .map((device) => {
                if (device.the_point) {
                    const point = JSON.parse(device.the_point);
                    const coords = [point.coordinates[0], point.coordinates[1]];
                    return new ol.Feature({
                        geometry: new ol.geom.Point(coords),
                        imei: device.imei,
                    });
                }
            }).filter(feature => feature);
    
        const vectorSource = new ol.source.Vector({
            features: features,
        });
    
        this.vectorLayer = new ol.layer.Vector({
            source: vectorSource,
            style: (feature) => {
                const isActive = this.state.activeDevice && this.state.activeDevice.imei === feature.get('imei');
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
    
    // Función para animar el cambio de color y tamaño
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
                this.updateDeviceMarkers(); // Asegura que el cambio de estilo ocurra primero
    
                // Obtener las coordenadas del dispositivo seleccionado
                const point = JSON.parse(device.the_point);
                const coords = [point.coordinates[0], point.coordinates[1]];
    
                // Usar un timeout para retrasar levemente la animación del mapa
                setTimeout(() => {
                    console.log("Iniciando animación del mapa...");
                    this.map.getView().animate({
                        center: coords,
                        zoom: 15,
                        duration: 500, // Duración de la animación
                    });
                }, 200); // Retraso de 50 ms para permitir que el DOM procese los cambios de estilo
            } catch (error) {
                console.error("Error al procesar device.the_point:", error);
            }
        }
    }
}


// Importar el ControlPanel en los componentes
GpsTrackingDashboard.components = { ControlPanel, GpsSearchbar };

GpsTrackingDashboard.template = "gps_tracking.gps_tracking_dashboard_template";

GpsTrackingDashboard.prototype.onSearch = async function (query) {
    console.log("Iniciando búsqueda en el Dashboard:", query);
    const filteredDevices = this.state.devices.filter(device =>
        device.imei.toLowerCase().includes(query.toLowerCase())
    );
    console.log("Dispositivos filtrados en el Dashboard:", filteredDevices);

    this.state.filteredDevices = filteredDevices;
    this.updateDeviceMarkers(filteredDevices); // Actualizar el mapa
};

registry.category("actions").add("gps_tracking_dashboard", GpsTrackingDashboard);