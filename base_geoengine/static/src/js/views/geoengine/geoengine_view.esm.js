/** @odoo-module */

import { _t } from "@web/core/l10n/translation";
import { GeoengineController } from "./geoengine_controller/geoengine_controller.esm";
import { GeoengineRenderer } from "./geoengine_renderer/geoengine_renderer.esm";
import { GeoengineArchParser } from "./geoengine_arch_parser.esm";
import { GeoengineCompiler } from "./geoengine_compiler.esm";
import { RelationalModel } from "@web/model/relational_model/relational_model";
import { registry } from "@web/core/registry";
import { View } from "@web/views/view";

export class GeoengineView extends View {
    /** Nombre de visualización de la vista */
    static display_name = _t("Geoengine");

    /** Icono de la vista */
    static icon = "fa fa-map-o";

    /** Indica si la vista maneja múltiples registros */
    static multiRecord = true;

    /** Tipo de vista */
    static type = "geoengine";

    /** Controlador de la vista */
    static Controller = GeoengineController;

    /** Renderizador de la vista */
    static Renderer = GeoengineRenderer;

    /** Modelo de la vista */
    static Model = RelationalModel;

    /** Analizador del archivo Arch de la vista */
    static ArchParser = GeoengineArchParser;

    /** Compilador de la vista */
    static Compiler = GeoengineCompiler;

    /** Método para obtener las propiedades de la vista */
    static props(genericProps) {
        const { arch, relatedModels, resModel } = genericProps;
        const archInfo = new this.ArchParser().parse(arch, relatedModels, resModel);

        return {
            ...genericProps,
            Model: this.Model,
            Renderer: this.Renderer,
            archInfo,
        };
    }
}

// Registrar la vista en el registro de vistas
registry.category("views").add("geoengine", GeoengineView);