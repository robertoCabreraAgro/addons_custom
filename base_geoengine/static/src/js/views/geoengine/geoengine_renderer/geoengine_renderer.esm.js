/** @odoo-module */

/**
 * Copyright 2023 ACSONE SA/NV
 */

import { loadBundle, loadJS, templates } from "@web/core/assets";
// import { getTemplate } from "@web/core/templates";
import { user } from "@web/core/user";
import {GeoengineRecord} from "../geoengine_record/geoengine_record.esm";
import {LayersPanel} from "../layers_panel/layers_panel.esm";
import {RecordsPanel} from "../records_panel/records_panel.esm";
import {rasterLayersStore} from "../../../raster_layers_store.esm";
import {vectorLayersStore} from "../../../vector_layers_store.esm";
import {useService} from "@web/core/utils/hooks";
import {registry} from "@web/core/registry";
import {RelationalModel} from "@web/model/relational_model/relational_model";
import {evaluateExpr} from "@web/core/py_js/py";
import {parseXML} from "@web/core/utils/xml";
import {
    addFieldDependencies,
    extractFieldsFromArchInfo,
} from "@web/model/relational_model/utils";
import {useModel, useModelWithSampleData} from "@web/model/model";
import {
    Component,
    mount,
    onMounted,
    onPatched,
    onWillStart,
    onWillUpdateProps,
    reactive,
    useState,
} from "@odoo/owl";

/* CONSTANTS */
const DEFAULT_BEGIN_COLOR = "#FFFFFF";
const DEFAULT_END_COLOR = "#000000";
const DEFAULT_MIN_SIZE = 5;
const DEFAULT_MAX_SIZE = 15;
// For choroplets only
const DEFAULT_NUM_CLASSES = 5;
const LEGEND_MAX_ITEMS = 10;

export class GeoengineRenderer extends Component {
    setup() {
        
        this.state = useState({selectedFeatures: [], isModified: false, isFit: false});
        this.models = [];
        this.cfg_models = [];
        this.vectorModel = {};
        this.legends = [];

        // When a change is issued in the rasterLayersStore or the vectorLayersStore the LayerChanged method is called.
        this.rasterLayersStore = reactive(rasterLayersStore, () =>
            this.onRasterLayerChanged()
        );
        this.vectorLayersStore = reactive(vectorLayersStore, () =>
            this.onVectorLayerChanged()
        );

        this.orm = useService("orm");
        this.view = useService("view");
        this.fields = useService("field");

        // For related model we need to load all the service needed by RelationalModel
        this.services = {};
        for (const key of RelationalModel.services) {
            this.services[key] = useService(key);
        }

        onWillStart(async () => {
            await loadBundle("web.assets_backend");
            await loadJS('/base_geoengine/static/lib/ol-10.1.0/ol.js');
            await loadJS('/base_geoengine/static/lib/chromajs-2.4.2/chroma.js');
            await loadJS('/base_geoengine/static/lib/geostats-2.0.0/geostats.min.js');
            await this.loadVectorModel();
            this.isGeoengineAdmin = user.hasGroup("base_geoengine.group_geoengine_admin");
        });


        onMounted(() => {
            // Retrives all vector layers in the store.
            this.geometryFields = this.vectorLayersStore.vectorsLayers.map(
                (layer) => layer.geo_field_id[1]
            );
            console.log("Campos de geometría cargados:", this.geometryFields);

            this.vectorSources = [];
            this.renderMap();
            this.renderVectorLayers();
        });

        onWillUpdateProps((nextProps) => {
            document.getElementById("map-legend").textContent = "";
            if (nextProps.isSavedOrDiscarded) {
                this.state.isModified = false;
            }
        });

        onPatched(() => {
            if (this.map !== undefined && !this.state.isModified) {
                this.renderVectorLayers();
            }
        });
    }

    async loadVectorModel() {
        console.log("Cargando modelo vectorial...");
        await this.loadView("geoengine.vector.layer", "form");
        console.log("Modelo vectorial cargado.");

    }

    renderMap() {
        if (!this.map) {
            this.createOverlay();
            this.map = new ol.Map({
                target: "olmap",
                controls: [
                    new ol.control.Zoom(),
                    new ol.control.Rotate(),
                ],
                layers: [
                    new ol.layer.Group({
                        title: "Base maps",
                        layers: this.createBackgroundLayers(
                            this.rasterLayersStore.rastersLayers
                        ),
                    }),
                ],
                overlays: [this.overlay],
            });
            console.log("Mapa creado:", this.map);
            this.map.on("moveend", () => {
                const newZoom = this.map.getView().getZoom();
                if (newZoom !== localStorage.getItem("ol-zoom")) {
                    localStorage.setItem("ol-zoom", newZoom);
                }
            });
            this.addMoveEndListenerToMap();
            this.format = new ol.format.GeoJSON({
                dataProjection: this.map.getView().getProjection(),
            });
            this.setupControls();
            this.registerInteraction();
        }
    }

    addMoveEndListenerToMap() {
        this.map.on("moveend", () => {
            const newZoom = this.map.getView().getZoom();
            if (newZoom !== localStorage.getItem("ol-zoom")) {
                localStorage.setItem("ol-zoom", newZoom);
            }
        });
    }

    /**
     * Create the info-box overlay that can be displayed over the map and
     * attached to a single map location.
     */
    createOverlay() {
        this.overlay = new ol.Overlay({
            element: document.getElementById("popup"),
            autoPan: {
                animation: {
                    duration: 250,
                },
            },
        });
    }

    createBackgroundLayers(backgrounds) {
        const source = [];
        source.push(new ol.layer.Tile({source: new ol.source.OSM()}));
        const backgroundLayers = backgrounds.map((background) => {
            switch (background.raster_type) {
                case "osm":
                    return new ol.layer.Tile({
                        title: background.name,
                        visible: !background.overlay,
                        type: "base",
                        opacity: background.opacity,
                        source: new ol.source.OSM({
                            attributions: null  // Desactivamos las atribuciones si no son necesarias
                        }),
                    });
                case "xyz":
                return new ol.layer.Tile({
                    title: background.name,
                    visible: !background.overlay,
                    type: "base",
                    opacity: background.opacity,
                    source: new ol.source.XYZ({
                        url: background.url,
                        crossOrigin: 'anonymous',
                    }),
                });
                case "wmts":
                    const {source_opt, tilegrid_opt, layer_opt} =
                        this.createOptions(background);
                    this.getUrl(background, source_opt);
                    if (background.format_suffix) {
                        source_opt.format = background.format_suffix;
                    }
                    if (background.request_encoding) {
                        source_opt.request_encoding = background.request_encoding;
                    }
                    if (background.projection) {
                        source_opt.projection = ol.proj.get(background.projection);
                        if (source_opt.projection) {
                            const projectionExtent = source_opt.projection.getExtent();
                            tilegrid_opt.origin =
                                ol.extent.getTopLeft(projectionExtent);
                        }
                    }
                    if (background.resolutions) {
                        tilegrid_opt.resolutions = background.resolutions
                            .split(",")
                            .map(Number);
                        const nbRes = tilegrid_opt.resolutions.length;
                        const matrixIds = new Array(nbRes);
                        for (let i = 0; i < nbRes; i++) {
                            matrixIds[i] = i;
                        }
                        tilegrid_opt.matrixIds = matrixIds;
                    }
                    if (background.max_extent) {
                        const extent = background.max_extent.split(",").map(Number);
                        layer_opt.extent = extent;
                        tilegrid_opt.extent = extent;
                    }
                    if (background.params) {
                        source_opt.dimensions = JSON.parse(background.params);
                    }
                    source_opt.tileGrid = new ol.tilegrid.WMTS(tilegrid_opt);
                    layer_opt.source = new ol.source.WMTS(source_opt);
                    return new ol.layer.Tile(layer_opt);
                case "d_wms":
                    const source_opt_wms = {
                        params: JSON.parse(background.params_wms),
                        serverType: background.server_type,
                        attributions: null,
                    };
                    const urls = background.url.split(",");
                    if (urls.length > 1) {
                        source_opt_wms.urls = urls;
                    } else {
                        source_opt_wms.url = urls[0];
                    }
                    return new ol.layer.Tile({
                        title: background.name,
                        visible: !background.overlay,
                        opacity: background.opacity,
                        source: new ol.source.TileWMS(source_opt_wms),
                    });
                default:
                    return undefined;
            }
        });
        return source.concat(backgroundLayers);
    }

    getUrl(background, source_opt) {
        const urls_wmts = background.url.split(",");
        if (urls_wmts.length > 1) {
            source_opt.urls = urls_wmts;
        } else {
            source_opt.url = urls_wmts[0];
        }
    }

    createOptions(background) {
        const tilegrid_opt = {};
        const source_opt = {
            layer: background.name,
            matrixSet: background.matrix_set,
        };
        const layer_opt = {
            title: background.name,
            visible: !background.overlay,
            type: "base",
            style: "default",
        };
        return {source_opt, tilegrid_opt, layer_opt};
    }

    /**
     * Add 'ScaleLine' control.
     */
    setupControls() {
        if (this.props.editable && this.isGeoengineAdmin) {
            this.createDrawControl();
            this.createSelectControl();
            this.createEditControl();
        }
        const scaleLine = new ol.control.ScaleLine();
        this.map.addControl(scaleLine);
    }

    createEditControl() {
        const {element, button} = this.createHtmlControl(
            '<i class="fa fa-magic"></i>',
            "edit-control ol-unselectable ol-control"
        );

        button.addEventListener("click", () => {
            this.hidePopup();
            this.addSelectedClassToButton(button);
            this.removeDrawInteraction();
            this.removeSelectInteraction();

            if (
                this.modifyClick === undefined &&
                this.modifyInteraction === undefined
            ) {
                this.modifyClick = new ol.interaction.Select({
                    condition: ol.events.condition.click,
                    filter: (feature) => !feature.get("model"),
                });
                this.modifyInteraction = new ol.interaction.Modify({
                    features: this.modifyClick.getFeatures(),
                });
                this.modifyInteraction.on("modifyend", async (ev) => {
                    this.state.isModified = true;
                    const resId = ev.features.getArray()[0].getId();
                    const record = this.props.data.records.find(
                        (el) => el.resId === resId
                    );
                    await record.switchMode("edit");
                    const value = this.format.writeGeometry(
                        ev.features.getArray()[0].getGeometry()
                    );
                    this.props.updateRecord(value);
                });
                this.map.addInteraction(this.modifyClick);
                this.map.addInteraction(this.modifyInteraction);
            }
        });

        const EditControl = new ol.control.Control({
            element: element,
        });
        this.map.addControl(EditControl);
    }

    createDrawControl() {
        const {element, button} = this.createHtmlControl(
            '<i class="fa fa-pencil"></i>',
            "draw-control ol-unselectable ol-control"
        );
        button.addEventListener("click", () => {
            this.hidePopup();
            this.addSelectedClassToButton(button);
            this.removeModifyInteraction();
            this.removeSelectInteraction();
            if (this.props.data.editedRecord !== null) {
                this.props.onClickDiscard();
            }
            if (this.drawInteraction === undefined) {
                const key = Object.keys(this.props.data.fields).find(
                    (el) => this.props.data.fields[el].geo_type !== undefined
                );
                this.drawInteraction = new ol.interaction.Draw({
                    type: this.props.data.fields[key].geo_type.geo_type,
                    source: new ol.source.Vector(),
                });
                this.map.addInteraction(this.drawInteraction);
                this.drawInteraction.on("drawstart", () => {
                    this.props.onDrawStart();
                });

                this.drawInteraction.on("drawend", (ev) => {
                    this.props.createRecord(
                        this.props.data.resModel,
                        key,
                        new ol.format.GeoJSON().writeGeometry(ev.feature.getGeometry())
                    );
                });
            }
        });

        const DrawControl = new ol.control.Control({
            element: element,
        });
        this.map.addControl(DrawControl);
    }

    createSelectControl() {
        const {element, button} = this.createHtmlControl(
            '<i class="fa fa-mouse-pointer"></i>',
            "select-control ol-unselectable ol-control"
        );
        this.addSelectedClassToButton(button);

        button.addEventListener("click", () => {
            this.addSelectedClassToButton(button);
            this.removeDrawInteraction();
            this.removeModifyInteraction();
            if (this.props.data.editedRecord !== null) {
                this.props.onClickDiscard();
            }
            if (
                this.selectPointerMove === undefined &&
                this.selectClick === undefined
            ) {
                this.registerInteraction();
            }
        });

        const SelectControl = new ol.control.Control({
            element: element,
        });
        this.map.addControl(SelectControl);
    }

    addSelectedClassToButton(button) {
        document
            .querySelectorAll(".selected-control")
            .forEach((el) => el.classList.remove("selected-control"));
        button.classList.add("selected-control");
    }

    removeDrawInteraction() {
        if (this.drawInteraction !== undefined) {
            this.map.removeInteraction(this.drawInteraction);
            this.drawInteraction = undefined;
        }
    }

    removeModifyInteraction() {
        if (this.modifyClick !== undefined && this.modifyInteraction !== undefined) {
            this.map.removeInteraction(this.modifyClick);
            this.map.removeInteraction(this.modifyInteraction);
            this.modifyClick = undefined;
            this.modifyInteraction = undefined;
        }
    }

    removeSelectInteraction() {
        if (this.selectClick !== undefined && this.selectPointerMove !== undefined) {
            this.map.removeInteraction(this.selectClick);
            this.map.removeInteraction(this.selectPointerMove);
            this.selectClick = undefined;
            this.selectPointerMove = undefined;
        }
    }

    createHtmlControl(innerHTML, className) {
        const button = document.createElement("button");
        button.innerHTML = innerHTML;
        const element = document.createElement("div");
        element.className = className;
        element.appendChild(button);
        return {element, button};
    }

    /**
     * Add 2 interactions. The first is for the hovering elements.
     * The second is for the click on the feature.
     */
    registerInteraction() {
        this.selectPointerMove = new ol.interaction.Select({
            condition: ol.events.condition.pointerMove,
            style: this.selectStyle,
        });
        this.selectClick = new ol.interaction.Select({
            condition: ol.events.condition.click,
            style: this.selectStyle,
        });

        this.selectClick.on("select", (e) => {
            const features = e.target.getFeatures();
            this.updateInfoBox(features);
        });
        this.map.addInteraction(this.selectClick);
        this.map.addInteraction(this.selectPointerMove);
    }

    /**
     * This is the style that is set when selecting or clicking on a feature.
     * @param {*} feature
     * @returns style
     */
    selectStyle(feature) {
        var geometryType = feature.getGeometry().getType();
        switch (geometryType) {
            case "Point":
                return new ol.style.Style({
                    image: new ol.style.Circle({
                        radius: 3 * 2,
                        fill: new ol.style.Fill({
                            color: [0, 153, 255, 1],
                        }),
                        stroke: new ol.style.Stroke({
                            color: [255, 255, 255, 1],
                            width: 3 / 2,
                        }),
                    }),
                    zIndex: Infinity,
                });
            case "MultiPolygon":
                return new ol.style.Style({
                    fill: new ol.style.Fill({
                        color: chroma(feature.values_.attributes.color)
                            .alpha(0.4)
                            .css(),
                    }),
                });
        }
    }
    /**
     * Allow you to display the info box on the map.
     * @param {*} features
     */
    updateInfoBox(features) {
        const feature = features.item(0);
        if (feature !== undefined) {
            const popup = this.getPopup();
            if (feature !== undefined) {
                var attributes = feature.get("attributes");

                if (this.cfg_models.includes(feature.get("model"))) {
                    const model = this.models.find(
                        (el) => el.model.resModel === feature.get("model")
                    );
                    this.mountGeoengineRecord({
                        popup,
                        archInfo: model.archInfo,
                        templateDocs: model.archInfo.templateDocs,
                        model: model.model,
                        attributes,
                    });
                } else {
                    this.mountGeoengineRecord({
                        popup,
                        archInfo: this.props.archInfo,
                        templateDocs: this.props.archInfo.templateDocs,
                        model: this.props.data,
                        attributes,
                    });
                }

                var coord = ol.extent.getCenter(feature.getGeometry().getExtent());
                this.overlay.setPosition(coord);
            }
        } else {
            this.hidePopup();
        }
    }

    getPopup() {
        const popup = document.getElementById("popup-content");
        if (popup.firstChild !== null) {
            popup.removeChild(popup.firstChild);
        }
        return popup;
    }

    /**
     * Allow you to mount geoengine record. This displays the record in the info box template.
     * @param {*} popup
     * @param {*} archInfo
     * @param {*} templateDocs
     * @param {*} model
     * @param {*} attributes
     * @param {*} record
     */
    mountGeoengineRecord({popup, archInfo, templateDocs, model, attributes, record}) {
        this.record =
            record === undefined
                ? model.records.find((element) => element._values.id === attributes.id)
                : record;
        mount(GeoengineRecord, popup, {
            env: this.env,
            props: {
                archInfo,
                record: this.record,
                templates: templateDocs,
            },
            templates,
        });
    }
    
    /**
     * When you click on a record in the RecordsPanel, this method is called to display the popup.
     * @param {*} record
     */
    onDisplayPopupRecord(record) {
        try {
            console.log("GeoengineRenderer: onDisplayPopupRecord llamado con registro:", record);
        
            const popup = this.getPopup();
            console.log("GeoengineRenderer: Popup obtenido:", popup);
        
            const feature = this.vectorSource.getFeatureById(record.id);
            console.log("GeoengineRenderer: Feature obtenido por ID:", feature);
        
            if (feature) {
                this.mountGeoengineRecord({
                    popup,
                    archInfo: this.props.archInfo,
                    templateDocs: this.props.archInfo.templateDocs,
                    record,
                });
                console.log("GeoengineRenderer: mountGeoengineRecord llamado correctamente.");
            
                var coord = ol.extent.getCenter(feature.getGeometry().getExtent());
                console.log("GeoengineRenderer: Coordenadas calculadas para el centro:", coord);
                this.overlay.setPosition(coord);
                console.log("GeoengineRenderer: Posición del overlay establecida.");
            
                var map_view = this.map.getView();
                if (map_view) {
                    map_view.animate({
                        center: feature.getGeometry().getFirstCoordinate(),
                        duration: 500,
                    });
                    console.log("GeoengineRenderer: Animación del mapa iniciada.");
                } else {
                    console.error("GeoengineRenderer: 'map_view' no está definido.");
                }
            } else {
                console.warn("GeoengineRenderer: No se encontró una feature para el registro con ID:", record.id);
            }
        } catch (error) {
            console.error("GeoengineRenderer: Error en onDisplayPopupRecord:", error);
        }
    }

    zoomOnFeature(record) {
        const feature = this.vectorSource.getFeatureById(record.resId);
        var map_view = this.map.getView();
        if (map_view) {
            map_view.fit(feature.getGeometry(), {maxZoom: 14});
        }
    }

    getOriginalZoom() {
        var extent = this.vectorLayersResult
            .find((res) => res.values_.visible === true)
            .getSource()
            .getExtent();
        var infinite_extent = [Infinity, Infinity, -Infinity, -Infinity];
        if (JSON.stringify(extent) === JSON.stringify(infinite_extent)) {
            extent = [-13360714.671289, 5314503.622, 8284735.328607, 7099727.320865]
        }

        if (JSON.stringify(extent) !== JSON.stringify(infinite_extent)) {
            var map_view = this.map.getView();
            if (map_view) {
                map_view.fit(extent, {maxZoom: 15});
            }
        }
    }

    /**
     * Allow you to hide the popup by clicking on the cross.
     */
    clickToHidePopup() {
        this.hidePopup();
    }

    hidePopup() {
        this.overlay.setPosition(undefined);
    }

    /**
     * When you click on the open button, it calls the controller's
     * openRecord method.
     */
    onInfoBoxClicked() {
        var viewIds = this.env?.config?.views
        var formViewId = null

        if (viewIds){
            formViewId = viewIds.filter(subList => subList.includes("form"));
        }
        this.props.openRecord(this.record.resModel, this.record.resId, formViewId);
    }

    /**
     * Allows you to change the visibility of layers. This method is called
     * when the user changes raster layers.
     */
    onRasterLayerChanged() {
        this.map
            .getLayers()
            .getArray()
            .find((layer) => layer.get("title") === "Base maps")
            .getLayers()
            .getArray()
            .forEach((layer) => {
                this.rasterLayersStore.rastersLayers.forEach((raster) => {
                    if (raster.name === layer.get("title")) {
                        layer.setVisible(raster.isVisible);
                        layer.setOpacity(raster.opacity);
                    }
                });
            });
    }

    /**
     * Allows you to change the visibility of layers. This method is called
     * when the user changes vector layers.
     */
    async onVectorLayerChanged() {
        if (!this.map) {
            console.warn("onVectorLayerChanged: el mapa aún no está inicializado");
            return;
        }
    
        const overlaysLayerGroup = this.map
            .getLayers()
            .getArray()
            .find((layer) => layer.get("title") === "Overlays");
    
        if (!overlaysLayerGroup) {
            console.warn("onVectorLayerChanged: No se encontró el grupo de capas 'Overlays'");
            return;
        }
    
        // Crear un mapa para acceder rápidamente a las capas por título
        const mapLayersByTitle = new Map();
        overlaysLayerGroup.getLayers().forEach((layer) => {
            mapLayersByTitle.set(layer.get("title"), layer);
        });
    
        // Recorrer los vectores y aplicar cambios si existen en el mapa
        for (const vector of this.vectorLayersStore.vectorsLayers) {
            const layer = mapLayersByTitle.get(vector.name);
            if (layer) {
                // onVisibleChanged
                if (vector.onVisibleChanged) {
                    this.onVisibleChanged(vector, layer);
                    const legend = document.getElementById(`legend-${vector.resId}`);
                    if (legend) {
                        legend.style.display = vector.isVisible ? "block" : "none";
                    }
                }
    
                // onDomainChanged
                if (vector.onDomainChanged) {
                    this.onVectorLayerModelDomainChanged(vector, layer);
                }
    
                // onLayerChanged
                if (vector.onLayerChanged) {
                    await this.onLayerChanged(vector, layer);
                }
    
                // onSequenceChanged
                if (vector.onSequenceChanged) {
                    this.onSequenceChanged(vector, layer);
                }
            } else {
                console.warn(`onVectorLayerChanged: No se encontró la capa en el mapa para el vector '${vector.name}'`);
            }
        }
    }

    /**
     * This method assigns a new priority to the layer according to the new sequence.
     * @param {*} vector
     * @param {*} layer
     */
    onSequenceChanged(vector, layer) {
        layer.setZIndex(vector.sequence);
    }

    /**
     * This method assing a new source to the layer according on the layer edited.
     * @param {*} vector
     * @param {*} layer
     */
    async onLayerChanged(vector, layer) {
        layer.setSource(null);
        const element = document.getElementById(`legend-${vector.resId}`);
        if (element !== null) {
            element.remove();
        }
        if (vector.model) {
            this.cfg_models.push(vector.model);
            const fields_to_read = [vector.geo_field_id[1]];
            if (vector.attribute_field_id) {
                fields_to_read.push(vector.attribute_field_id[1]);
            }
            const data = await this.getModelData(vector, fields_to_read);
            this.styleVectorLayerAndLegend(vector, data, layer);
            this.useRelatedModel(vector, layer, data);
        } else {
            const data = this.props.data.records;
            this.styleVectorLayerAndLegend(vector, data, layer);
            this.addSourceToLayer(data, vector, layer);
        }
    }

    /**
     * This method assigns the visibility received by the layer.
     * @param {*} vector
     * @param {*} layer
     */
    onVisibleChanged(vector, layer) {
        layer.setVisible(vector.isVisible);
    }

    /**
     * This method assigns a new source with the revalued domain.
     * @param {*} cfg
     * @param {*} layer
     */
    async onVectorLayerModelDomainChanged(vector, layer) {
        layer.setSource(null);
        const element = document.getElementById(`legend-${vector.resId}`);
        if (element !== null) {
            element.remove();
        }
        const fields_to_read = this.getFieldsToRead(vector);
        const data = await this.getModelData(vector, fields_to_read);
        this.useRelatedModel(vector, layer, data);
        const styleInfo = this.styleVectorLayer(vector, data);
        this.initLegend(styleInfo, vector);
    }

    async renderVectorLayers() {
        try {
            console.log("GeoengineRenderer: renderVectorLayers iniciado");
            const vectorLayers = await this.createVectorLayers();
            console.log("GeoengineRenderer: Vector layers creados:", vectorLayers);
    
            this.vectorLayersResult = await Promise.all(vectorLayers);
            console.log("GeoengineRenderer: vectorLayersResult actualizado:", this.vectorLayersResult);
    
            // Remover capas existentes de "Overlays"
            this.map.getLayers().forEach((layer) => {
                if (layer.get("title") === "Overlays") {
                    console.log("GeoengineRenderer: Removiendo capa 'Overlays'");
                    this.map.removeLayer(layer);
                }
            });
    
            // Crear grupo de overlays y añadir capas
            this.overlaysGroup = new ol.layer.Group({
                title: "Overlays",
                layers: this.vectorLayersResult,
            });
            console.log("GeoengineRenderer: Grupo de Overlays creado:", this.overlaysGroup);
    
            // Configurar visibilidad según vectorLayersStore
            this.vectorLayersResult.forEach((vlayer) => {
                this.vectorLayersStore.vectorsLayers.forEach((vector) => {
                    if (vlayer.values_.title === vector.name) {
                        vlayer.setVisible(vector.isVisible);
                        console.log(`GeoengineRenderer: Capa '${vector.name}' visibilidad establecida a ${vector.isVisible}`);
                    }
                });
            });
    
            // Añadir grupo de overlays al mapa
            this.map.addLayer(this.overlaysGroup);
            console.log("GeoengineRenderer: Grupo de Overlays añadido al mapa");
    
            // Actualizar zoom
            this.updateZoom();
            console.log("GeoengineRenderer: Zoom actualizado");
        } catch (error) {
            console.error("GeoengineRenderer: Error en renderVectorLayers:", error);
        }
    }

    /**
     * Adapts the zoom according to the result obtained.
     */
    updateZoom() {
        if (this.state.isFit) {
            this.map.getView().setZoom(localStorage.getItem("ol-zoom"));
        } else if (this.props.data.records.length) {
            this.getOriginalZoom();
            this.state.isFit = true;
        }
    }

    createVectorLayers() {
        return this.vectorLayersStore.vectorsLayers.map((layer) =>
            this.createVectorLayer(layer)
        );
    }

    async createVectorLayer(cfg) {
        var lv = new ol.layer.Vector({
            title: cfg.name,
            active_on_startup: cfg.active_on_startup,
        });
        // If we want to use an other model in the layer
        if (cfg.model) {
            this.cfg_models.push(cfg.model);
            const fields_to_read = this.getFieldsToRead(cfg);
            await this.loadView(cfg.model, "geoengine");
            const data = await this.getModelData(cfg, fields_to_read);
            this.styleVectorLayerAndLegend(cfg, data, lv);
            this.useRelatedModel(cfg, lv, data);
        } else {
            const data = this.props.data.records;
            if (!data.length) {
                return new ol.layer.Vector({
                    source: new ol.source.Vector(),
                    title: cfg.name,
                });
            }
            this.styleVectorLayerAndLegend(cfg, data, lv);
            this.addSourceToLayer(data, cfg, lv);
        }
        if (cfg.layer_opacity) {
            lv.setOpacity(cfg.layer_opacity);
        }
        lv.setZIndex(cfg.sequence);
        return lv;
    }

    getFieldsToRead(cfg) {
        const fields_to_read = [cfg.geo_field_id[1]];
        if (cfg.attribute_field_id) {
            fields_to_read.push(cfg.attribute_field_id[1]);
        }
        return fields_to_read;
    }

    async getModelData(cfg, fields_to_read) {
        const domain = this.evalModelDomain(cfg);
        let data = await this.orm.searchRead(cfg.model, [domain][0], fields_to_read);
        const modelsRecords = this.models.find((e) => e.model.resModel === cfg.model)
            .model.records;
        data = data.map((data) => modelsRecords.find((rec) => rec.resId === data.id));
        return data;
    }

    styleVectorLayerAndLegend(cfg, data, lv) {
        const styleInfo = this.styleVectorLayer(cfg, data);
        this.initLegend(styleInfo, cfg);
        lv.setStyle(styleInfo.style);
    }

    initLegend(styleInfo, cfg) {
        if (document.getElementById(`legend-${cfg.resId}`) === null) {
            const parentContainer = document.getElementById("map-legend");
            const containerLegend = document.createElement("div");
            if (styleInfo.legend !== "") {
                containerLegend.innerHTML = styleInfo.legend;
                containerLegend.setAttribute("id", `legend-${cfg.resId}`);
                containerLegend.className = "legend";
                if (cfg.isVisible) {
                    containerLegend.style.display = "block";
                }
                parentContainer.appendChild(containerLegend);
            }
        }
    }

    /**
     * This method is called when a layer uses another model.
     * @param {*} cfg
     * @param {*} lv
     */
    useRelatedModel(cfg, lv, res) {
        const vectorSource = new ol.source.Vector();
        this.addFeatureToSource(res, cfg, vectorSource);
        lv.setSource(vectorSource);
    }

    /**
     * Set source to the given layer.
     * @param {*} res
     * @param {*} cfg
     * @param {*} lv
     */
    addSourceToLayer(res, cfg, lv) {
        this.vectorSource = new ol.source.Vector();
        this.addFeatureToSource(res, cfg, this.vectorSource);
        lv.setSource(this.vectorSource);
    }

    /**
     * Evaluates the domain passed to the layer model.
     * @param {*} cfg
     * @returns {Array}
     */
    evalModelDomain(cfg) {
        let domain = [];
        // We can put active_ids in our domain to get all ids of all the
        // element displayed.
        if (cfg.model_domain.includes("{ACTIVE_IDS}")) {
            const start = cfg.model_domain.search("ACTIVE_IDS") - 2;
            let newDomain =
                cfg.model_domain.slice(0, start) + cfg.model_domain.slice(start + 2);
            const end = newDomain.search("ACTIVE_IDS") + 10;
            newDomain = newDomain.slice(0, end) + newDomain.slice(end + 2);
            newDomain = newDomain.replace("not in active_ids", "not in");
            newDomain = newDomain.replace("in active_ids", "in");
            domain = evaluateExpr(newDomain, {
                ACTIVE_IDS: this.props.data.records.map(
                    (datapoint) => `${datapoint.resId}`
                ),
            });
        } else {
            domain = evaluateExpr(cfg.model_domain);
        }
        return domain;
    }
    /**
     * Loads the model's view that is passed to the layer.
     * @param {*} model
     * @param {*} domain
     */
    async loadView(model, view) {
        const viewRegistry = registry.category("views");
        const fields = await this.fields.loadFields(model, {
            attributes: [
                "store",
                "searchable",
                "type",
                "string",
                "relation",
                "selection",
                "related",
            ],
        });
        const {relatedModels, views} = await this.view.loadViews({
            resModel: model,
            views: [[false, view]],
        });
        const {ArchParser, Model} = viewRegistry.get(view);

        const xmlDoc = parseXML(views[view].arch);
        const archInfo = new ArchParser().parse(xmlDoc, relatedModels, model);

        if (model === "geoengine.vector.layer") {
            const notAllowedField = Object.keys(fields).filter(
                (field) =>
                    fields[field] !== undefined &&
                    fields[field].relation !== undefined &&
                    fields[field].relation === "ir.ui.view"
            );
            notAllowedField.forEach((field) => {
                delete field[field];
            });
        }

        const {activeFields, arch_fields} = extractFieldsFromArchInfo(archInfo, fields);
        addFieldDependencies(
            activeFields,
            arch_fields,
            this.progressBarAggregateFields(archInfo)
        );

        const modelConfig = {
            model,
            activeFields,
            openGroupsByDefault: true,
            domain: [],
            orderBy: [],
            groupBy: {},
            resModel: model,
            fields: fields,
        };

        const searchParams = {
            config: modelConfig,
            limit: 10000,
            groupsLimit: Number.MAX_SAFE_INTEGER,
            countLimit: archInfo.countLimit,
            orderBy: [],
            resModel: model,
        };

        if (model === "geoengine.vector.layer") {
            this.vectorModel = new Model(this.env, searchParams, this.services);
            await this.vectorModel.load(searchParams);
        } else if (this.models.find((e) => e.model.resModel === model) === undefined) {
            const toLoadModel = new Model(this.env, searchParams, this.services);
            await toLoadModel.load().then(() => {
                this.models.push({model: toLoadModel.root, archInfo});
            });
        }
    }

    progressBarAggregateFields(archInfo) {
        const res = [];
        const {progressAttributes} = archInfo;
        if (progressAttributes && progressAttributes.sumField) {
            res.push(progressAttributes.sumField);
        }
        return res;
    }

    addFeatureToSource(data, cfg, vectorSource) {
        data.forEach((item) => {
            var attributes =
                item._values === undefined
                    ? Object.assign({}, item || {})
                    : Object.assign({}, item._values || {});
            this.geometryFields.forEach((geo_field) => delete attributes[geo_field]);

            if (cfg.display_polygon_labels === true) {
                attributes.label =
                    item._values === undefined
                        ? item[cfg.attribute_field_id[1]]
                        : item._values[cfg.attribute_field_id[1]];
            } else {
                attributes.label = "";
            }
            attributes.color = cfg.begin_color;

            const json_geometry =
                item._values === undefined
                    ? item[cfg.geo_field_id[1]]
                    : item._values[cfg.geo_field_id[1]];
            if (json_geometry) {
                const feature = new ol.Feature({
                    geometry: new ol.format.GeoJSON().readGeometry(json_geometry),
                    attributes: attributes,
                    model: cfg.model,
                });
                feature.setId(item.resId);

                vectorSource.addFeature(feature);
            }
        });
    }

    styleVectorLayer(cfg, data) {
        switch (cfg.geo_repr) {
            case "colored":
                return this.styleVectorLayerColored(cfg, data);
            case "proportion":
                return this.styleVectorLayerProportion(cfg, data);
            default:
                return this.styleVectorLayerDefault(cfg);
        }
    }

    styleVectorLayerColored(cfg, data) {
        try {
            console.log("=== Iniciando styleVectorLayerColored ===");
            console.log("Configuración (cfg):", cfg);
            console.log("Datos (data):", data);
    
            var indicator = cfg.attribute_field_id[1];
            console.log("Indicador (indicator):", indicator);
    
            // Verificar si 'indicator' está definido
            if (!indicator) {
                console.error("Error: 'indicator' está undefined.");
                return {
                    style: () => defaultStyle, // Define un estilo por defecto
                    legend: null,
                };
            }
    
            var values = this.extractLayerValues(cfg, data);
            console.log("Valores extraídos (values):", values);
    
            var nb_class = cfg.nb_class || DEFAULT_NUM_CLASSES;
            console.log("Número de clases (nb_class):", nb_class);
    
            var opacity = cfg.layer_opacity;
            console.log("Opacidad (opacity):", opacity);
    
            var begin_color_hex = cfg.begin_color || DEFAULT_BEGIN_COLOR;
            var end_color_hex = cfg.end_color || DEFAULT_END_COLOR;
            console.log("Color de inicio (begin_color_hex):", begin_color_hex);
            console.log("Color de fin (end_color_hex):", end_color_hex);
    
            var begin_color = chroma(begin_color_hex).alpha(opacity).css();
            var end_color = chroma(end_color_hex).alpha(opacity).css();
            console.log("Color de inicio con opacidad (begin_color):", begin_color);
            console.log("Color de fin con opacidad (end_color):", end_color);
    
            var scale = chroma.scale([begin_color, end_color]);
            console.log("Escala de colores (scale):", scale);
    
            var serie = new geostats(values);
            console.log("Serie de geostats (serie):", serie);
    
            var vals = null;
            switch (cfg.classification) {
                case "unique":
                case "custom":
                    vals = serie.getClassUniqueValues();
                    console.log("Valores únicos (vals):", vals);
                    scale = chroma.scale("RdYlBu").domain([0, vals.length], vals.length);
                    console.log("Nueva escala para 'unique'/'custom' (scale):", scale);
                    break;
                case "quantile":
                    serie.getClassQuantile(nb_class);
                    vals = serie.getRanges();
                    console.log("Rangos de cuantiles (vals):", vals);
                    scale = scale.domain([0, vals.length], vals.length);
                    console.log("Nueva escala para 'quantile' (scale):", scale);
                    break;
                case "interval":
                    serie.getClassEqInterval(nb_class);
                    vals = serie.getRanges();
                    console.log("Rangos de intervalos (vals):", vals);
                    scale = scale.domain([0, vals.length], vals.length);
                    console.log("Nueva escala para 'interval' (scale):", scale);
                    break;
                default:
                    console.warn("Advertencia: Clasificación desconocida. Se usará la escala por defecto.");
                    break;
            }
    
            let colors = [];
            if (cfg.classification === "custom") {
                colors = vals.map((val, index) => {
                    if (val) {
                        const color = chroma(val).alpha(opacity).css();
                        console.log(`Color personalizado para valor '${val}':`, color);
                        return color;
                    } else {
                        console.warn(`Valor en 'vals' en posición ${index} es falsy:`, val);
                        return DEFAULT_BEGIN_COLOR; // O un color por defecto
                    }
                });
            } else {
                colors = scale.colors(vals.length).map((color, index) => {
                    const colored = chroma(color).alpha(opacity).css();
                    console.log(`Color de escala para índice ${index}:`, colored);
                    return colored;
                });
            }
            console.log("Colores generados (colors):", colors);
    
            const styles_map = this.createStylesWithColors(colors);
            console.log("Mapa de estilos (styles_map):", styles_map);
    
            let legend = null;
            if (vals.length <= LEGEND_MAX_ITEMS) {
                legend = serie.getHtmlLegend(colors, cfg.name, 1);
                console.log("Leyenda generada (legend):", legend);
            }
    
            // Verificar si 'styles_map' y 'colors' están correctamente definidos
            if (!styles_map || typeof styles_map !== 'object') {
                console.error("'styles_map' está undefined o no es un objeto.");
                return {
                    style: () => defaultStyle,
                    legend: null,
                };
            }
    
            if (!colors || !Array.isArray(colors) || colors.length === 0) {
                console.error("'colors' está undefined, no es un array o está vacío.");
                return {
                    style: () => defaultStyle,
                    legend: null,
                };
            }
    
            return {
                style: (feature) => {
                    try {
                        console.log("=== Aplicando estilo al feature ===");
                        console.log("Feature completo:", feature);
    
                        const attributes = feature.get("attributes");
                        console.log("Attributes del feature:", attributes);
    
                        if (!attributes) {
                            console.error("Error: 'attributes' del feature están undefined.");
                            return defaultStyle;
                        }
    
                        const value = attributes[indicator];
                        console.log(`Valor para el indicador '${indicator}':`, value);
    
                        if (value === undefined) {
                            console.error(`Error: El indicador '${indicator}' no está definido en 'attributes'.`);
                            return defaultStyle;
                        }
    
                        const color_idx = this.getClass(value, vals);
                        console.log(`Índice de color obtenido (color_idx):`, color_idx);
    
                        if (color_idx < 0 || color_idx >= colors.length) {
                            console.error(`Error: color_idx (${color_idx}) está fuera del rango de 'colors'.`);
                            return defaultStyle;
                        }
    
                        var label_text = attributes.label;
                        console.log(`Texto de etiqueta original (label_text):`, label_text);
    
                        if (label_text === false || label_text === undefined || label_text === null) {
                            console.log("label_text es falsy. Asignando cadena vacía.");
                            label_text = "";
                        }
    
                        // Verificar si 'styles_map[colors[color_idx]]' está definido
                        if (!styles_map[colors[color_idx]]) {
                            console.error(`Error: 'styles_map' no contiene el color '${colors[color_idx]}'.`);
                            return defaultStyle;
                        }
    
                        // Verificar si el estilo específico está definido
                        if (!styles_map[colors[color_idx]][0] || !styles_map[colors[color_idx]][0].text_) {
                            console.error(`Error: El estilo para el color '${colors[color_idx]}' no está completamente definido.`);
                            return defaultStyle;
                        }
    
                        // Asignar el texto a la etiqueta del estilo
                        styles_map[colors[color_idx]][0].text_.text_ = label_text.toString();
                        console.log(`Texto de etiqueta asignado: '${label_text}' para color '${colors[color_idx]}'`);
    
                        // Retornar el estilo correspondiente
                        return styles_map[colors[color_idx]];
                    } catch (error) {
                        console.error("Error en la función de estilo del feature:", error);
                        return defaultStyle;
                    }
                },
                legend,
            };
        } catch (error) {
            console.error("Error en styleVectorLayerColored:", error);
            return {
                style: () => defaultStyle,
                legend: null,
            };
        }
    }

    styleVectorLayerProportion(cfg, data) {
        var indicator = cfg.attribute_field_id[1];
        var values = this.extractLayerValues(cfg, data);
        var serie = new geostats(values);
        var styles_map = {};
        var minSize = cfg.min_size || DEFAULT_MIN_SIZE;
        var maxSize = cfg.max_size || DEFAULT_MAX_SIZE;
        var minVal = serie.min();
        var maxVal = serie.max();
        var color_hex = cfg.begin_color || DEFAULT_BEGIN_COLOR;
        var color = chroma(color_hex).alpha(cfg.layer_opacity).css();

        const {fill, stroke} = this.createFillAndStroke(color);

        values.forEach((value) => {
            if (value in styles_map) {
                return;
            }
            var proportion = (value - minVal) / (maxVal - minVal);
            var proportion_sized = proportion * (maxSize - minSize);
            var radius = proportion_sized + minSize;
            var styles = [
                new ol.style.Style({
                    image: new ol.style.Circle({
                        fill: fill,
                        stroke: stroke,
                        radius: radius,
                    }),
                    fill: fill,
                    stroke: stroke,
                }),
            ];
            styles_map[value] = styles;
        });
        return {
            style: (feature) => {
                var value = feature.get("attributes")[indicator];
                return styles_map[value];
            },
            legend: "",
        };
    }

    styleVectorLayerDefault(cfg) {
        const color_hex = cfg.begin_color || DEFAULT_BEGIN_COLOR;
        var opacity = cfg.layer_opacity
        if (cfg.layer_transparent) {
            opacity = 0.0
        }
        var color = chroma(color_hex).alpha(opacity).css();
        // Basic

        const {fill, stroke} = this.createFillAndStroke(color);

        var olStyleText = this.createStyleText();
        var styles = [
            new ol.style.Style({
                image: new ol.style.Circle({
                    fill: fill,
                    stroke: stroke,
                    radius: 5,
                }),
                fill: fill,
                stroke: stroke,
                text: olStyleText,
            }),
        ];
        return {
            style: (feature) => {
                var label_text = feature.values_.attributes.label;
                if (label_text === false) {
                    label_text = "";
                }
                styles[0].text_.text_ = label_text;
                return styles;
            },
            legend: "",
        };
    }
    createStyleText() {
        return new ol.style.Text({
            text: "",
            fill: new ol.style.Fill({
                color: "#000000",
            }),
            stroke: new ol.style.Stroke({
                color: "#FFFFFF",
                width: 5,
            }),
        });
    }

    /**
     * Create a feature style based on the color table.
     * @param {*} colors
     * @returns
     */
    createStylesWithColors(colors) {
        const styles_map = {};
        colors.forEach((color) => {
            if (color in styles_map) {
                return;
            }
            const {fill, stroke} = this.createFillAndStroke(color);
            var olStyleText = this.createStyleText();
            const styles = [
                new ol.style.Style({
                    image: new ol.style.Circle({
                        fill: fill,
                        stroke: stroke,
                        radius: 7,
                    }),
                    fill: fill,
                    stroke: stroke,
                    text: olStyleText,
                }),
            ];
            styles_map[color] = styles;
        });
        return styles_map;
    }

    createFillAndStroke(color) {
        const fill = new ol.style.Fill({
            color: color,
        });
        const stroke = new ol.style.Stroke({
            color: "#333333",
            width: 2,
        });
        return {fill, stroke};
    }
    /**
     * Allows you to find the index of the color to be used according to its value.
     * @param {*} val
     * @param {*} a
     * @returns {Number}
     */
    getClass(val, a) {
        // Classification uniqueValues
        var idx = a.indexOf(val);
        if (idx > -1) {
            return idx;
        }
        // Range classification
        var separator = " - ";
        for (var i = 0; i < a.length; i++) {
            // All classification except uniqueValues
            if (a[i].indexOf(separator) !== -1) {
                var item = a[i].split(separator);
                if (val <= parseFloat(item[1])) {
                    return i;
                }
            } else if (val === a[i]) {
                // Classification uniqueValues
                return i;
            }
        }
    }

    /**
     * Extracts the values of the field corresponding to the attribute field.
     * @param {*} cfg, the layer.
     * @param {*} data, all of the records
     * @returns {Array}
     */
    extractLayerValues(cfg, data) {
        var indicator = cfg.attribute_field_id[1];
        return data.map((item) => item._values[indicator]);
    }
}

GeoengineRenderer.template = "base_geoengine.GeoengineRenderer";
GeoengineRenderer.props = {
    isSavedOrDiscarded: {type: Boolean},
    archInfo: {type: Object},
    data: {type: Object},
    openRecord: {type: Function},
    editable: {type: Boolean, optional: true},
    updateRecord: {type: Function},
    onClickDiscard: {type: Function},
    createRecord: {type: Function},
    onDrawStart: {type: Function},
};
GeoengineRenderer.components = {LayersPanel, GeoengineRecord, RecordsPanel};
