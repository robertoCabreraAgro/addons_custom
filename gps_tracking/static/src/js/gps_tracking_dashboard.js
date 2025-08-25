
import { Component, useState, onWillStart, onMounted, useRef, onWillUnmount, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { loadJS } from "@web/core/assets";
import { ControlPanel } from "@web/search/control_panel/control_panel";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { SearchModel } from "@web/search/search_model";
import { GpsSearchbar } from "../components/searchbar/gps_searchbar";
import { GeofenceDialog } from "../components/geofence_dialog";

// Constants
const REFRESH_INTERVAL_MS = 1000; // 1 second for real-time tracking updates
const DEFAULT_ZOOM_LEVEL = 15;
const ANIMATION_DURATION_MS = 500;
const DEFAULT_STROKE_COLOR = "#3399CC";
const TRANSPARENT_FILL = "rgba(0, 0, 0, 0)";

// GPS Tracking user group types
const GPS_USER_GROUPS = {
    MANAGER: 'manager',
    PRIVATE: 'private', 
    VEHICLE_LOAN: 'vehicle_loan',
    REPORTING: 'reporting',
    USER: 'user',
    NONE: 'none'
};

// Department ID for reporting group
const REPORTING_DEPARTMENT_ID = 4;

// Base device fields for queries
const BASE_DEVICE_FIELDS = [
    "id", "imei", "the_point", "speed", "timestamp", "altitude", 
    "satellite", "address", "gsm_signal", "ignition", "movement", 
    "color", "vehicle_id", "license_plate",
    "odometer", "real_odometer", "location", "department_id", "driver_name"
];

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
        this.dialog = useService("dialog");
        this.notification = useService("notification");
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
            leftPanelVisible: true, // Control de visibilidad del panel izquierdo
            canCreateGeofence: false, // Permission to create geofences
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

        // Real-time tracking refresh every 1 second
        this.startAutoRefresh();

        // Pause/resume refresh based on page visibility for performance
        this.handleVisibilityChange = () => {
            if (document.hidden) {
                this.pauseAutoRefresh();
            } else {
                this.resumeAutoRefresh();
            }
        };
        document.addEventListener('visibilitychange', this.handleVisibilityChange);

        onWillStart(async () => {
            // Cargar los dispositivos inicialmente
            await this.loadDevices();
            
            // Configurar permisos para crear geofences
            await this.setupGeofencePermissions();
            
            // Configurar visibilidad del panel izquierdo basado en permisos
            await this.setupLeftPanelVisibility();
            
            // Esperar un momento para que se calculen los campos computados y luego refiltrar
            setTimeout(() => {
                this.applyDepartmentFilter();
            }, 2000); // Esperar 2 segundos
            
            await this.loadOpenLayers();
        });

        onMounted(() => {
            if (this.mapContainerRef.el) {
                this.initializeMap();
                this.updateDeviceMarkers();
                this.loadGeofences();
                // Ejecutar checkGeofenceContext después de que todo esté cargado
                setTimeout(() => {
                    this.checkGeofenceContext();
                }, 800);
                this.mapInitialized = true;
            } else {
                setTimeout(() => {
                    if (this.mapContainerRef.el) {
                        this.initializeMap();
                        this.updateDeviceMarkers();
                        setTimeout(() => {
                            this.checkGeofenceContext();
                        }, 800);
                        this.mapInitialized = true;
                    }
                }, 0);
            }
        });

        onWillUnmount(() => {
            this.stopAutoRefresh();
            document.removeEventListener('visibilitychange', this.handleVisibilityChange);
        });
    }

    /**
     * Auto-refresh management functions
     */
    startAutoRefresh() {
        if (!this.refreshInterval) {
            this.refreshInterval = setInterval(() => {
                this.refreshTrackingData();
            }, REFRESH_INTERVAL_MS);
        }
    }

    pauseAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    resumeAutoRefresh() {
        if (!this.refreshInterval) {
            this.startAutoRefresh();
        }
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Setup geofence creation permissions based on user groups
     */
    async setupGeofencePermissions() {
        try {
            const userInfo = await this.getUserPermissions();
            
            // Only reporting and manager groups can create geofences
            this.state.canCreateGeofence = (
                userInfo.group === GPS_USER_GROUPS.REPORTING ||
                userInfo.group === GPS_USER_GROUPS.MANAGER
            );
        } catch (error) {
            console.error('Error setting up geofence permissions:', error);
            this.state.canCreateGeofence = false;
        }
    }

    /**
     * Setup left panel visibility based on user permissions and available devices
     */
    async setupLeftPanelVisibility() {
        try {
            const userInfo = await this.getUserPermissions();
            
            // If user is group_gps_tracking_user (no access to any vehicles), hide the left panel
            if (userInfo.group === GPS_USER_GROUPS.USER) {
                this.state.leftPanelVisible = false;
            }
        } catch (error) {
            console.error('Error setting up left panel visibility:', error);
        }
    }

    /**
     * Cache for user permissions to avoid repeated server calls
     */
    _userPermissionsCache = null;

    /**
     * Get user permissions with caching
     */
    async getUserPermissions() {
        if (!this._userPermissionsCache) {
            try {
                this._userPermissionsCache = await this.orm.call(
                    'res.users',
                    'get_gps_tracking_permissions',
                    []
                );
            } catch (error) {
                console.error('Error getting user permissions:', error);
                // Fallback permissions for error cases
                this._userPermissionsCache = { 
                    group: GPS_USER_GROUPS.REPORTING, 
                    can_read_private: false 
                };
            }
        }
        return this._userPermissionsCache;
    }

    /**
     * Prepare fields array for device queries based on user permissions
     */
    async prepareDeviceFields() {
        const userInfo = await this.getUserPermissions();
        const fields = [...BASE_DEVICE_FIELDS];
        
        // Add private field only if user has permission
        if (userInfo.can_read_private) {
            fields.push("private");
        }
        
        return fields;
    }

    /**
     * Generic device loading function with filtering
     */
    async loadDevicesWithFiltering(domain = []) {
        try {
            const fields = await this.prepareDeviceFields();
            const devices = await this.orm.searchRead(
                "gps.tracking.device",
                domain,
                fields
            );
            
            return await this.filterDevicesByUserPermissions(devices);
        } catch (error) {
            console.error("Error loading devices:", error);
            return [];
        }
    }

    /**
     * Filter devices based on user permissions and groups
     */
    async filterDevicesByUserPermissions(devices) {
        const userInfo = await this.getUserPermissions();
        return devices.filter(device => this._isDeviceAllowedForUser(device, userInfo));
    }

    /**
     * Check if a specific device is allowed for the current user
     */
    _isDeviceAllowedForUser(device, userInfo) {
        const hasDept = device.department_id && Array.isArray(device.department_id) && device.department_id.length > 0;
        const deptId = hasDept ? device.department_id[0] : null;
        const isPrivate = device.hasOwnProperty('private') ? device.private : false;

        // Apply filtering based on user group
        switch(userInfo.group) {
            case GPS_USER_GROUPS.MANAGER:
                return true;
                
            case GPS_USER_GROUPS.PRIVATE:
                return true;
                
            case GPS_USER_GROUPS.VEHICLE_LOAN:
                return !isPrivate;
                
            case GPS_USER_GROUPS.REPORTING:
                return deptId === REPORTING_DEPARTMENT_ID;
                
            case GPS_USER_GROUPS.USER:
                return false;
                
            default:
                return false;
        }
    }

    async _reloadDevicesWithDomain(domain) {
        try {
            const filteredDevices = await this.loadDevicesWithFiltering(domain || []);
            
            this.state.devices = filteredDevices;
            this.state.filteredDevices = filteredDevices;
        } catch (error) {
            console.error("Error al recargar dispositivos:", error);
            this.state.devices = [];
            this.state.filteredDevices = [];
        }
    }

    async loadDevices() {
        try {
            const filteredDevices = await this.loadDevicesWithFiltering();
            
            this.state.devices = filteredDevices;
            this.state.filteredDevices = filteredDevices;
        } catch (error) {
            console.error("Error al cargar los dispositivos:", error);
            this.state.devices = [];
            this.state.filteredDevices = [];
        }
    }

    async applyDepartmentFilter() {
        /**
         * Apply department filtering after computed fields are available.
         * This method re-reads the devices with department_id and applies filtering.
         */
        try {
            const filteredDevices = await this.loadDevicesWithFiltering();
            
            // Update state with filtered devices
            this.state.devices = filteredDevices;
            this.state.filteredDevices = filteredDevices;
            
            // Update map markers if map is initialized
            if (this.mapInitialized) {
                this.updateDeviceMarkers();
            }
            
        } catch (error) {
            console.error("Error in applyDepartmentFilter:", error);
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

    /**
     * Refresh only tracking data for real-time updates (optimized)
     */
    async refreshTrackingData() {
        if (!this.state.devices || this.state.devices.length === 0) {
            return;
        }

        try {
            const deviceIds = this.state.devices.map(d => d.id);
            const trackingFields = ["id", "the_point", "speed", "timestamp", "altitude", "address", "gsm_signal", "ignition", "movement"];
            
            const updatedDevices = await this.orm.searchRead(
                "gps.tracking.device",
                [['id', 'in', deviceIds]],
                trackingFields
            );

            // Update existing devices with new tracking data
            this.state.devices.forEach(device => {
                const updated = updatedDevices.find(u => u.id === device.id);
                if (updated) {
                    Object.assign(device, updated);
                }
            });

            // Update map markers with new positions (optimized for real-time)
            this.updateDevicePositions();
            
        } catch (error) {
            console.error("Error refreshing tracking data:", error);
        }
    }

    // Full data refresh (for manual refresh or search changes)
    async refreshData() {
        await this._reloadDevicesWithDomain(this.props.searchDomain || []);
        this.updateDeviceMarkers();
    }

    // Verificar si hay contexto de geofence para hacer zoom automático
    checkGeofenceContext() {
        if (!this.map) {
            return;
        }

        // Buscar coordenadas en el contexto
        const context = this.props.context || {};
        const actionContext = (this.props.action && this.props.action.context) || {};
        
        let targetContext = null;
        if (context.default_center_lat && context.default_center_lng) {
            targetContext = context;
        } else if (actionContext.default_center_lat && actionContext.default_center_lng) {
            targetContext = actionContext;
        }
        
        if (targetContext) {
            const lat = parseFloat(targetContext.default_center_lat);
            const lng = parseFloat(targetContext.default_center_lng);
            const zoom = targetContext.default_zoom || 16;
            
            // Convertir coordenadas y hacer zoom
            const coords = ol.proj.fromLonLat([lng, lat]);
            
            setTimeout(() => {
                this.map.getView().animate({
                    center: coords,
                    zoom: zoom,
                    duration: 500,
                });
            }, 500);
        }
    }

    // Cargar OpenLayers de forma global
    async loadOpenLayers() {
        try {
            await loadJS("/base_geoengine/static/lib/ol-10.5.0/ol.js");
            if (typeof ol === "undefined") {
                throw new Error("OpenLayers no está definido después de la carga.");
            }
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

            const featureType = feature.get("feature_type");
            let tooltipContent = "";

            if (featureType === 'device') {
                // Device tooltip content
                const imei = feature.get("imei") || "Unknown";
                const speed = feature.get("speed") || 0;
                const ignition = feature.get("ignition") || 0;
                const movement = feature.get("movement") || 0;

                tooltipContent = `
                <div style="min-width: 200px;">
                    <strong>IMEI:</strong> ${imei}<br/>
                    <strong>Speed:</strong> ${speed} km/h<br/>
                    <strong>Engine:</strong>
                    <span style="color: ${ignition == 1 ? 'green' : 'red'};">
                        <i class="fa fa-power-off" style="margin-right: 5px;"></i>
                        ${ignition == 1 ? 'On' : 'Off'}
                    </span><br/>
                    <strong>Movement:</strong>
                    <span style="color: ${movement == 1 ? 'green' : 'red'};">
                        <i class="fa fa-car" style="margin-right: 5px;"></i>
                        ${movement == 1 ? 'Moving' : 'Parked'}
                    </span><br/>
                    <button id="btn-street" class="btn btn-sm btn-info" style="margin-top:5px;">
                        View Street View
                    </button>
                </div>
                `;
            } else if (featureType === 'geofence') {
                // Geofence tooltip content
                const name = feature.get("name") || "Unnamed Area";
                const areaType = feature.get("area_type") || "Unknown";
                const partnerId = feature.get("partner_id");
                const parentId = feature.get("parent_id");

                tooltipContent = `
                <div style="min-width: 200px;">
                    <strong><i class="fa fa-map-marker"></i> ${name}</strong><br/>
                    <strong>Type:</strong> ${areaType.charAt(0).toUpperCase() + areaType.slice(1).replace('_', ' ')}<br/>
                    ${partnerId ? `<strong>Client:</strong> ${partnerId[1]}<br/>` : ''}
                    ${parentId ? `<strong>Parent Area:</strong> ${parentId[1]}<br/>` : ''}
                    <div style="margin-top: 8px;">
                        <span style="display: inline-block; width: 15px; height: 15px; background-color: ${feature.get("color")}; border: 1px solid #000; margin-right: 5px;"></span>
                        <small>Geographic Area</small>
                    </div>
                </div>
                `;
            }

            // Set tooltip content
            tooltipElement.innerHTML = tooltipContent;

            // Assign listeners after creating content
            setTimeout(() => {
                // StreetView button (only for devices)
                if (featureType === 'device') {
                    const btnStreet = document.getElementById("btn-street");
                    if (btnStreet) {
                        btnStreet.addEventListener("click", (evt) => {
                            evt.stopPropagation();  // Prevent map from hiding it
                            this._showStreetViewInsideTooltip(tooltipElement, feature);
                        });
                    }
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
            return;
        }

        if (typeof ol === 'undefined') {
            setTimeout(() => this.initializeMap(), 100);
            return;
        }

        // Crear capas base para diferentes tipos de vista
        this.baseLayers = {
            satellite: new ol.layer.Tile({
                title: 'Satellite',
                type: 'base',
                visible: true,
                source: new ol.source.XYZ({
                    url: "https://mts1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}&key=TU_CLAVE_API",
                })
            }),
            roads: new ol.layer.Tile({
                title: 'Roads Only',
                type: 'base',
                visible: false,
                source: new ol.source.XYZ({
                    url: "https://mts1.google.com/vt/lyrs=r&x={x}&y={y}&z={z}&key=TU_CLAVE_API",
                })
            })
        };

        // Crear el mapa con todas las capas base
        this.map = new ol.Map({
            target: this.mapContainerRef.el,
            layers: Object.values(this.baseLayers),
            view: new ol.View({
                center: ol.proj.fromLonLat([0, 0]),
                zoom: 2,
            }),
        });

        // Agregar control de cambio de capas
        this.addLayerSwitcher();


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
                    feature_type: 'device',
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

    /**
     * Optimized position update for real-time tracking (doesn't recreate layer)
     */
    updateDevicePositions() {
        if (!this.map || !this.vectorLayer) {
            // Fallback to full update if layer doesn't exist
            this.updateDeviceMarkers();
            return;
        }

        const vectorSource = this.vectorLayer.getSource();
        const features = vectorSource.getFeatures();

        // Update existing features with new positions
        features.forEach(feature => {
            if (feature.get('feature_type') === 'device') {
                const imei = feature.get('imei');
                const device = this.state.devices.find(d => d.imei === imei);
                
                if (device && device.the_point) {
                    try {
                        const point = JSON.parse(device.the_point);
                        const newCoords = [point.coordinates[0], point.coordinates[1]];
                        feature.getGeometry().setCoordinates(newCoords);
                        
                        // Update feature properties
                        feature.set('speed', device.speed);
                        feature.set('ignition', device.ignition);
                        feature.set('movement', device.movement);
                    } catch (error) {
                        console.error(`Error updating position for device ${imei}:`, error);
                    }
                }
            }
        });
    }

    updateDeviceMarkers() {
        if (!this.map) {
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
                        feature_type: 'device',
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

    toggleLeftPanel() {
        this.state.leftPanelVisible = !this.state.leftPanelVisible;
        
        // Notificar al mapa que se redimensione
        setTimeout(() => {
            if (this.map) {
                this.map.updateSize();
            }
        }, 300); // Esperar a que termine la transición CSS
    }

    onCardClick(device) {
        if (!this.map) {
            return;
        }

        if (device.the_point) {
            try {
                this.state.activeDevice = device;
                this.updateDeviceMarkers();

                const point = JSON.parse(device.the_point);
                const coords = [point.coordinates[0], point.coordinates[1]];
                
                setTimeout(() => {
                    this.map.getView().animate({
                        center: coords,
                        zoom: DEFAULT_ZOOM_LEVEL,
                        duration: ANIMATION_DURATION_MS,
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
                ["id", "name", "geometry", "color", "area_type", "partner_id", "parent_id"]
            );

            const features = geofences.map((geofence) => {
                const geom = JSON.parse(geofence.geometry); // Validar que el JSON sea válido
                const color = geofence.color || "#FF0000";

                // Convertir coordenadas de EPSG:4326 a EPSG:3857
                const transformedCoords = geom.coordinates.map((ring) =>
                    ring.map((coord) => ol.proj.transform(coord, "EPSG:4326", "EPSG:3857"))
                );

                // Create the feature using transformed coordinates
                return new ol.Feature({
                    geometry: new ol.geom.Polygon(transformedCoords),
                    name: geofence.name,
                    color: color,
                    area_type: geofence.area_type,
                    partner_id: geofence.partner_id,
                    parent_id: geofence.parent_id,
                    feature_type: 'geofence',
                });
            });

            const vectorSource = new ol.source.Vector({
                features: features,
            });

            this.geofenceLayer = new ol.layer.Vector({
                source: vectorSource,
                style: (feature) => {
                    // Si la feature no tiene color asignado (temporal), hacer relleno transparente
                    const color = feature.get("color");
                    const fillColor = color ? color + "44" : TRANSPARENT_FILL; // Transparente para temporales
                    const strokeColor = color || DEFAULT_STROKE_COLOR; // Azul por defecto para temporales
                    
                    return new ol.style.Style({
                        stroke: new ol.style.Stroke({
                            color: strokeColor,
                            width: 2,
                        }),
                        fill: new ol.style.Fill({
                            color: fillColor,
                        }),
                    });
                },
            });

            this.map.addLayer(this.geofenceLayer);
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
            }
        });
    }

    async addGeofenceDrawingTool() {
        /**
         * Activate the geofence drawing tool and show creation dialog
         */
        if (!this.geofenceLayer) {
            return;
        }

        if (this.state.drawingToolActive) {
            this.map.removeInteraction(this.state.drawingInteraction);
            this.state.drawingToolActive = false;
            this.state.drawingInteraction = null;
            return;
        }

        // Create new drawing interaction
        const draw = new ol.interaction.Draw({
            source: this.geofenceLayer.getSource(),
            type: "Polygon",
        });

        draw.on("drawend", async (event) => {
            const geometry = event.feature.getGeometry().clone().transform('EPSG:3857', 'EPSG:4326');
            const geoJson = new ol.format.GeoJSON().writeGeometry(geometry);
            
            // Store reference to the temporary feature for potential removal
            const tempFeature = event.feature;
            
            // Create cleanup function to avoid code duplication
            const cleanupTempFeature = (reason = "cancelled") => {
                
                if (tempFeature && this.geofenceLayer) {
                    this.geofenceLayer.getSource().removeFeature(tempFeature);
                }
                
                this.removeTemporaryFeatures();
            };

            // Show dialog with geometry
            this.dialog.add(GeofenceDialog, {
                geometry: geoJson,
                onSave: (result) => {
                    this.loadGeofences();
                    this.notification.add("Geographic area saved successfully.", { type: "success" });
                },
                onCancel: () => cleanupTempFeature("cancelled")
            }, {
                onClose: () => cleanupTempFeature("closed")
            });

            // Deactivate drawing tool after drawing
            this.map.removeInteraction(draw);
            this.state.drawingToolActive = false;
        });

        this.map.addInteraction(draw);
        this.state.drawingInteraction = draw;
        this.state.drawingToolActive = true;
    }

    removeTemporaryFeatures() {
        /**
         * Remove all temporary features (features without color property) from the geofence layer
         */
        if (!this.geofenceLayer) {
            return;
        }

        const source = this.geofenceLayer.getSource();
        const featuresToRemove = [];

        // Find all features that are temporary (no color or not saved geofences)
        source.forEachFeature((feature) => {
            const color = feature.get("color");
            const featureType = feature.get("feature_type");
            
            // Remove features that don't have color AND don't have feature_type="geofence"
            if (!color || featureType !== "geofence") {
                featuresToRemove.push(feature);
            }
        });

        // Remove all temporary features
        featuresToRemove.forEach((feature) => {
            source.removeFeature(feature);
        });
        
        if (featuresToRemove.length > 0) {
        }
    }

    // Recorrido por fechas
    async fetchDevicePath() {
        if (!this.state.startDate || !this.state.endDate) {
            this.notification.add("Please select a date range.", { type: "warning" });
            return;
        }

        // Convertir fechas locales a UTC dentro del contexto de la clase
        const formattedStartDate = this.localToUTC(this.state.startDate);
        const formattedEndDate = this.localToUTC(this.state.endDate);


        try {
            // Crear el dominio con las fechas en UTC
            const domain = [
                ["device_id", "=", this.state.activeDevice.id], // Usamos el ID del dispositivo
                ["timestamp", ">=", formattedStartDate],
                ["timestamp", "<=", formattedEndDate],
            ];

            const points = await this.orm.searchRead(
                "gps.tracking.point",
                domain,
                ["latitude", "longitude", "timestamp"]
            );


            if (points.length === 0) {
                this.notification.add("No points found for the selected date range.", { type: "info" });
                return;
            }

            this.state.pathPoints = points.map((point) => [
                point.longitude,
                point.latitude,
            ]);

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

    }

    addLayerSwitcher() {
        // Crear botones para cambiar tipo de mapa
        const layerSwitcherDiv = document.createElement('div');
        layerSwitcherDiv.className = 'layer-switcher ol-unselectable ol-control';
        layerSwitcherDiv.style.cssText = 'top: 10px; right: 10px; background: rgba(255,255,255,0.9); border-radius: 6px; padding: 8px; display: flex; gap: 5px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);';
        
        const layers = [
            { key: 'satellite', label: '🛰️', title: 'Vista Satelital' },
            { key: 'roads', label: '🚗', title: 'Solo Carreteras' }
        ];

        layers.forEach(layer => {
            const button = document.createElement('button');
            button.innerHTML = layer.label;
            button.title = layer.title;
            button.className = layer.key === 'satellite' ? 'active' : '';
            button.style.cssText = 'padding: 6px 8px; border: 1px solid #ddd; background: white; cursor: pointer; border-radius: 4px; font-size: 16px; min-width: 35px; transition: all 0.2s;';
            
            button.onclick = () => {
                // Ocultar todas las capas
                Object.values(this.baseLayers).forEach(l => l.setVisible(false));
                // Mostrar la capa seleccionada
                this.baseLayers[layer.key].setVisible(true);
                
                // Actualizar botones activos
                layerSwitcherDiv.querySelectorAll('button').forEach(b => {
                    b.className = '';
                    b.style.background = 'white';
                });
                button.className = 'active';
                button.style.background = '#007bff';
                button.style.color = 'white';
            };
            
            layerSwitcherDiv.appendChild(button);
        });

        // Crear control personalizado
        const layerSwitcherControl = new ol.control.Control({
            element: layerSwitcherDiv
        });

        this.map.addControl(layerSwitcherControl);

        // Estilo inicial para botón activo
        const activeButton = layerSwitcherDiv.querySelector('.active');
        if (activeButton) {
            activeButton.style.background = '#007bff';
            activeButton.style.color = 'white';
        }
    }

}

// Acciones y componentes
GpsTrackingDashboard.components = { ControlPanel, GpsSearchbar, SearchBar };
GpsTrackingDashboard.template = "gps_tracking.gps_tracking_dashboard_template";

GpsTrackingDashboard.prototype.onSearch = async function (query) {
    const filteredDevices = this.state.devices.filter((device) =>
        device.imei.toLowerCase().includes(query.toLowerCase())
    );

    this.state.filteredDevices = filteredDevices;
    this.updateDeviceMarkers(filteredDevices);
};

registry.category("actions").add("gps_tracking_dashboard", GpsTrackingDashboard);
