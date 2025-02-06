/** @odoo-module **/

import { SearchModel } from "@web/search/search_model";
import { Domain } from "@web/core/domain";

export class GpsSearchModel extends SearchModel {
    _getFieldDomain(field, autocompleteValues) {
        if (field.fieldName === "imei") {
            const domains = autocompleteValues.map(({ value, operator }) => {
                let domain = [["imei", operator, value]];
                return new Domain(domain);
            });
            return Domain.or(domains);
        }
        return super._getFieldDomain(...arguments);
    }
}