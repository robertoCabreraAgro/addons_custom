# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    "name": "Purchases Teams",
    "version": "1.1",
    "category": "Inventory/Purchase",
    "summary": "Purchases Teams",
    "description": """
Using this application you can manage Purchase Teams with SRM and/or Purchase
=======================================================================
 """,
    "website": "https://www.odoo.com/app/crm",
    "depends": ["purchase"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/srm_team_data.xml",
        "views/srm_tag_views.xml",
        "views/srm_team_views.xml",
        "views/srm_team_member_views.xml",
        "views/res_partner_views.xml",
        "views/purchase_order_views.xml",
    ],
    "demo": [
        "demo/srm_team_demo.xml",
        "demo/srm_tag_demo.xml",
    ],
    "installable": True,
    "license": "LGPL-3",
}
