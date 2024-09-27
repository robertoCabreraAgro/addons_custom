/** @odoo-module **/

/**
 * Copyright 2023 ACSONE SA/NV
 */

import {loadBundle, loadJS, loadCSS} from "@web/core/assets";
import {registry} from "@web/core/registry";
import {useService} from "@web/core/utils/hooks";
import {standardFieldProps} from "@web/views/fields/standard_field_props";

import {Component, onMounted, onRendered, onWillStart, useEffect} from "@odoo/owl";

export class FieldGeoEngineEditMap extends Component {
    static template = "base_geoengine.FieldGeoEngineEditMap";
    setup() {

        console.log('Props recibidos:', this.props);


        // Allows you to have a unique id if you put the same field in the view several times
        this.id = `map_${Date.now()}`;
        this.orm = useService("orm");

        onWillStart(async () => {
            await loadBundle("web.assets_backend");
            await loadJS('/base_geoengine/static/lib/ol-10.1.0/ol.js');
            await loadJS('/base_geoengine/static/lib/chromajs-2.4.2/chroma.js');
            await loadJS('/base_geoengine/static/lib/geostats-2.0.0/geostats.js');
        });

        onMounted(async () => {
            console.log("FieldGeoEngineEditMap: onMounted iniciado");
            console.log("Props recibidas en onMounted:", this.props);
        
            try {
                const result = await this.orm.call(
                    this.props.record.resModel,
                    "get_edit_info_for_geo_column",
                    [this.props.name]
                );
                console.log("FieldGeoEngineEditMap: Resultado de get_edit_info_for_geo_column:", result);
        
                this.projection = result.projection;
                console.log("FieldGeoEngineEditMap: Proyección establecida:", this.projection);
        
                this.defaultExtent = result.default_extent;
                console.log("FieldGeoEngineEditMap: Extensión por defecto establecida:", this.defaultExtent);
        
                this.defaultZoom = result.default_zoom;
                console.log("FieldGeoEngineEditMap: Zoom por defecto establecido:", this.defaultZoom);
        
                this.restrictedExtent = result.restricted_extent;
                console.log("FieldGeoEngineEditMap: Extensión restringida establecida:", this.restrictedExtent);
        
                this.srid = result.srid;
                console.log("FieldGeoEngineEditMap: SRID establecido:", this.srid);
        
                this.createLayers();
                console.log("FieldGeoEngineEditMap: Capas creadas");
        
                this.renderMap();
                console.log("FieldGeoEngineEditMap: Mapa renderizado");
        
                this.setValue(this.props.record.data[this.props.name]);
                console.log("FieldGeoEngineEditMap: Valor establecido en el mapa:", this.props.record.data[this.props.name]);
            } catch (error) {
                console.error("FieldGeoEngineEditMap: Error en onMounted:", error);
            }
        });

        useEffect(
            () => {
                if (!this.props.readonly && this.map !== undefined) {
                    this.setupControls();
                }
            },
            () => [this.props.record.data[this.props.name]]
        );

        // Is executed after component is rendered. When we use pagination.
        onRendered(() => {
            this.setValue(this.props.record.data[this.props.name]);
        });
    }

    /**
     * Displays geo data on the map using the collection of features.
     */
    createVectorLayer() {
        this.features = new ol.Collection();
        this.source = new ol.source.Vector({features: this.features});
        const colorHex = this.props.color !== undefined ? this.props.color : "#ee9900";
        const opacity = this.props.opacity !== undefined ? this.props.opacity : 1;
        const color = chroma(colorHex).alpha(opacity).css();
        const fill = new ol.style.Fill({
            color: color,
        });
        const stroke = new ol.style.Stroke({
            color,
            width: 2,
        });
        return new ol.layer.Vector({
            source: this.source,
            style: new ol.style.Style({
                fill,
                stroke,
                image: new ol.style.Circle({
                    radius: 5,
                    fill,
                    stroke,
                }),
            }),
        });
    }

    /**
     * Call the method that creates the layer to display the geo data on the map.
     */
    createLayers() {
        this.vectorLayer = this.createVectorLayer();
        console.log("capa creada")
    }

    /**
     * Allows you to centre the area defined for the user.
     * If there is an item to display.
     */
    updateMapZoom() {
        if (this.source) {
            var extent = this.source.getExtent();
            if (!ol.extent.isEmpty(extent)) {
                var map_view = this.map.getView();
                if (map_view) {
                    var maxZoom = this.defaultZoom ?? 5;
                    map_view.fit(extent, {maxZoom: maxZoom});
                }
            }
        }
    }
    
    updateMapEmpty() {
        var map_view = this.map.getView();
        if (map_view) {
            var extent = this.defaultExtent.replace(/\s/g, "").split(",").map(Number);
            var maxZoom = this.defaultZoom ?? 5;
            map_view.fit(extent, {maxZoom: maxZoom});
        }
    }

    /**
     * Based on the value passed in props, adds a new feature to the collection.
     * @param {*} value
     */
    setValue(value) {
        if (this.map) {
            /**
             * If the value to be displayed is equal to the one passed in props, do nothing
             * otherwise clear the map and display the new value.
             */
            if (this.displayValue == value) return;
            this.displayValue = value;
            var ft = new ol.Feature({
                geometry: new ol.format.GeoJSON().readGeometry(value),
                labelPoint: new ol.format.GeoJSON().readGeometry(value),
            });
            this.source.clear();
            this.source.addFeature(ft);

            if (value) {
                this.updateMapZoom();
            } else {
                this.updateMapEmpty();
            }
        }
    }

    /**
     * This is triggered when the view changed. When we have finished drawing our geo data, or
     * when we clear the map.
     * @param {*} geometry
     */
    onUIChange(geometry) {
        var value = null;
        if (geometry) {
            value = this.format.writeGeometry(geometry);
        }
        this.props.record.update({[this.props.name]: value});
    }

    /**
     * Allow you to setup the trash button and the draw interaction.
     */
    setupControls() {
        if (!this.props.record.data[this.props.name]) {
            void (
                this.selectInteraction !== undefined &&
                this.map.removeInteraction(this.selectInteraction)
            );
            void (
                this.modifyInteraction !== undefined &&
                this.map.removeInteraction(this.modifyInteraction)
            );
            this.drawInteraction = new ol.interaction.Draw({
                type: this.geoType,
                source: this.source,
            });
            this.map.addInteraction(this.drawInteraction);

            this.drawInteraction.on("drawend", (e) => {
                this.onUIChange(e.feature.getGeometry());
            });
        } else {
            void (
                this.drawInteraction !== undefined &&
                this.map.removeInteraction(this.drawInteraction)
            );
            this.selectInteraction = new ol.interaction.Select();
            this.modifyInteraction = new ol.interaction.Modify({
                features: this.selectInteraction.getFeatures(),
            });
            this.map.addInteraction(this.selectInteraction);
            this.map.addInteraction(this.modifyInteraction);

            this.modifyInteraction.on("modifyend", (e) => {
                e.features.getArray().forEach((item) => {
                    this.onUIChange(item.getGeometry());
                });
            });
        }

        const element = this.createTrashControl();

        this.clearmapControl = new ol.control.Control({element: element});

        this.map.addControl(this.clearmapControl);
    }

    /**
     * Create the trash button that clears the map.
     * @returns the div in which the button is located.
     */
    createTrashControl() {
        const button = document.createElement("button");
        button.innerHTML = '<i class="fa fa-trash"/>';
        button.addEventListener("click", () => {
            this.source.clear();
            this.onUIChange(null);
        });
        const element = document.createElement("div");
        element.className = "ol-clear ol-unselectable ol-control";
        element.appendChild(button);
        return element;
    }

    /**
     * Displays the map in the div provided.
     */
    renderMap() {
        this.map = new ol.Map({
            target: this.id,
            layers: [
                new ol.layer.Tile({
                    source: new ol.source.OSM(),
                }),
            ],
            view: new ol.View({
                center: [0, 0],
                zoom: 10,
            }),
        });
        this.map.addLayer(this.vectorLayer);
        this.format = new ol.format.GeoJSON({
            internalProjection: this.map.getView().getProjection(),
            externalProjection: "EPSG:" + this.srid,
        });

        if (!this.props.readonly) {
            this.setupControls();
        }
    }
}

FieldGeoEngineEditMap.template = "base_geoengine.FieldGeoEngineEditMap";
FieldGeoEngineEditMap.props = {
    ...standardFieldProps,
    opacity: {type: Number, optional: true},
    color: {type: String, optional: true},
};

FieldGeoEngineEditMap.extractProps = (attrs) => {
    let options = {};
    if (attrs.options) {
        try {
            options = JSON.parse(attrs.options);
        } catch (e) {
            console.error("Error al parsear las opciones del campo:", e);
        }
    }
    return {
        opacity: options.opacity,
        color: options.color,
    };
};

export class FieldGeoEngineEditMapMultiPolygon extends FieldGeoEngineEditMap {
    setup() {
        this.geoType = "MultiPolygon";
        super.setup();
    }
}

export class FieldGeoEngineEditMapPolygon extends FieldGeoEngineEditMap {
    setup() {
        this.geoType = "Polygon";
        super.setup();
    }
}

export class FieldGeoEngineEditMapPoint extends FieldGeoEngineEditMap {
    setup() {
        this.geoType = "Point";
        super.setup();
    }
}

export class FieldGeoEngineEditMapMultiPoint extends FieldGeoEngineEditMap {
    setup() {
        this.geoType = "MultiPoint";
        super.setup();
    }
}

export class FieldGeoEngineEditMapLine extends FieldGeoEngineEditMap {
    setup() {
        this.geoType = "LineString";
        super.setup();
    }
}

export class FieldGeoEngineEditMapMultiLine extends FieldGeoEngineEditMap {
    setup() {
        this.geoType = "MultiLineString";
        super.setup();
    }
}

export const fieldGeoEngineEditMapMultiPolygon = {
    component: FieldGeoEngineEditMapMultiPolygon,
};

export const fieldGeoEngineEditMapPolygon = {
    component: FieldGeoEngineEditMapPolygon,
};

export const fieldGeoEngineEditMapPoint = {
    component: FieldGeoEngineEditMapPoint,
};

export const fieldGeoEngineEditMapMultiPoint = {
    component: FieldGeoEngineEditMapMultiPoint,
};

export const fieldGeoEngineEditMapLine = {
    component: FieldGeoEngineEditMapLine,
};

export const fieldGeoEngineEditMapMultiLine = {
    component: FieldGeoEngineEditMapMultiLine,
};

registry.category("fields").add("geo_multi_polygon", fieldGeoEngineEditMapMultiPolygon);
registry.category("fields").add("geo_polygon", fieldGeoEngineEditMapPolygon);
registry.category("fields").add("geo_point", fieldGeoEngineEditMapPoint);
registry.category("fields").add("geo_multi_point", fieldGeoEngineEditMapMultiPoint);
registry.category("fields").add("geo_line", fieldGeoEngineEditMapLine);
registry.category("fields").add("geo_multi_line", fieldGeoEngineEditMapMultiLine);
