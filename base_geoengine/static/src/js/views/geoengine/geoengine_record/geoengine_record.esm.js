/** @odoo-module */

import { Field } from "@web/views/fields/field";
import { GeoengineCompiler } from "../geoengine_compiler.esm";
import { INFO_BOX_ATTRIBUTE } from "../geoengine_arch_parser.esm";
import { registry } from "@web/core/registry";
import { user } from "@web/core/user";
import { useViewCompiler } from "@web/views/view_compiler";
import { Component, onWillUpdateProps, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const formatters = registry.category("formatters");

function getValue(record, fieldName) {
    const field = record.fields[fieldName];
    const value = record._values[fieldName];
    const formatter = formatters.get(field.type, String);
    console.log(`getValue: Formateando el valor del campo '${fieldName}' con el formateador '${field.type}'`);
    const formattedValue = formatter(value, { field, data: record._values });
    console.log(`getValue: Valor formateado para '${fieldName}':`, formattedValue);
    return formattedValue;
}

export class GeoengineRecord extends Component {
    /**
     * Setup the record by compiling the arch and the info-box template.
     */
    setup() {
        try {
            console.log("GeoengineRecord: setup iniciado");
            
            // Obtener el servicio 'user'
            this.user = user;
            console.log("GeoengineRecord: servicio 'user' obtenido:", this.user);
            
            const { Compiler, templates } = this.props;
            console.log("GeoengineRecord: props recibidas en setup:", this.props);
            
            // Configurar el compilador de vistas
            const ViewCompiler = Compiler || this.constructor.Compiler;
            this.templates = useViewCompiler(ViewCompiler, templates);
            console.log("GeoengineRecord: ViewCompiler y templates configurados:", this.templates);
            
            // Verificar si la plantilla principal está definida
            if (this.constructor.template) {
                console.log(`GeoengineRecord: La plantilla '${this.constructor.template}' está definida.`);
            } else {
                console.error("GeoengineRecord: La plantilla principal no está definida.");
            }
            
            // Verificar si INFO_BOX_ATTRIBUTE está definido y la plantilla existe
            if (this.constructor.INFO_BOX_ATTRIBUTE) {
                console.log(`GeoengineRecord: INFO_BOX_ATTRIBUTE está definido: '${this.constructor.INFO_BOX_ATTRIBUTE}'`);
            } else {
                console.error("GeoengineRecord: INFO_BOX_ATTRIBUTE no está definido.");
            }
            
            // Crear el registro con los datos formateados
            this.createRecord(this.props);
            onWillUpdateProps(this.createRecord);
            console.log("GeoengineRecord: método createRecord llamado y onWillUpdateProps configurado");
        } catch (error) {
            console.error("GeoengineRecord: Error en setup:", error);
        }
    }

    /**
     * Create record with formatter.
     * @param {*} props
     */
    createRecord(props) {
        try {
            console.log("GeoengineRecord: createRecord iniciado con props:", props);
            const { record } = props;
            this.record = Object.create(null);
            
            for (const fieldName in record._values) {
                this.record[fieldName] = {
                    get value() {
                        return getValue(record, fieldName);
                    },
                };
                console.log(`GeoengineRecord: Campo procesado - '${fieldName}':`, this.record[fieldName].value);
            }
            console.log("GeoengineRecord: createRecord finalizado:", this.record);
        } catch (error) {
            console.error("GeoengineRecord: Error en createRecord:", error);
        }
    }

    get renderingContext() {
        try {
            console.log("GeoengineRecord: Generando renderingContext");
            const context = {
                context: this.props.record.context,
                JSON,
                record: this.props.record,
                read_only_mode: this.props.readonly,
                selection_mode: this.props.forceGlobalClick,
                user_context: this.user.context,
                __comp__: Object.assign(Object.create(this), { this: this }),
            };
            console.log("GeoengineRecord: renderingContext generado:", context);
            
            // Verificar si la plantilla INFO_BOX_ATTRIBUTE está disponible
            const infoBoxTemplate = this.templates[this.constructor.INFO_BOX_ATTRIBUTE];
            if (infoBoxTemplate) {
                console.log(`GeoengineRecord: La plantilla '${this.constructor.INFO_BOX_ATTRIBUTE}' está disponible.`);
            } else {
                console.error(`GeoengineRecord: La plantilla '${this.constructor.INFO_BOX_ATTRIBUTE}' NO está disponible.`);
            }
            
            return context;
        } catch (error) {
            console.error("GeoengineRecord: Error en renderingContext:", error);
            return {};
        }
    }
}

GeoengineRecord.template = "base_geoengine.GeoengineRecord";
GeoengineRecord.Compiler = GeoengineCompiler;
GeoengineRecord.components = { Field };
GeoengineRecord.INFO_BOX_ATTRIBUTE = INFO_BOX_ATTRIBUTE;