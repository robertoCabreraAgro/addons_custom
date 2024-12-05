/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { SearchModel } from "@web/search/search_model";

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
            // Escuchar cambios en el searchModel
            if (this.env.searchModel) {
                this.env.searchModel.on('update', null, async () => {
                    const domain = this.env.searchModel.getDomain();
                    await this.loadDevices(domain);
                    this.updateDeviceMarkers();
                });
            } else {
                console.error("searchModel no está disponible en this.env");
            }
        });
    }

    async loadDevices() {
        try {
            const devices = await this.orm.searchRead("gps.tracking.device", [], ["id", "imei", "the_point", "speed", "timestamp", "altitude"]);
            console.log("Dispositivos cargados:", devices);
            this.state.devices = devices;
        } catch (error) {
            console.error("Error al cargar los dispositivos:", error);
            this.state.devices = [];
        }
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
        const features = this.state.devices.map(device => {
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
        }).filter(feature => feature);

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

    updateDeviceMarkers() {
        this.addDeviceMarkers();
    }

    onCardClick(device) {
        if (!this.map) {
            console.error('El mapa aún no está inicializado.');
            return;
        }
        if (device.the_point) {
            try {
                const point = JSON.parse(device.the_point);
                const coords = [point.coordinates[0], point.coordinates[1]];
                this.map.getView().animate({
                    center: coords,
                    zoom: 15,
                    duration: 2000,
                });
            } catch (error) {
                console.error('Error al procesar device.the_point:', error);
            }
        }
    }
}


// Importar el ControlPanel en los componentes
GpsTrackingDashboard.components = { ControlPanel };

GpsTrackingDashboard.template = "gps_tracking.gps_tracking_dashboard_template";

registry.category("actions").add("gps_tracking_dashboard", GpsTrackingDashboard);