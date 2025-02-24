/** @odoo-module **/

import { session } from '@web/session';

// Registrar 'geoengine' en session.view_info
session.view_info['geoengine'] = {
    label: 'GeoEngine',
    multi_record: true,
    icon: 'fa fa-map',
    searchable: true,
};