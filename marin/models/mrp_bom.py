from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.osv.expression import AND, OR

from collections import defaultdict


class MrpBom(models.Model):
    _inherit = "mrp.bom"

    x_type = fields.Selection(
        [
            ("refill", "Refill"),
            ("formulate", "Formulate"),
            ("reformulate", "Reformulate")
        ],
        "Marin Type",
    )

    @api.constrains("active", "product_id", "product_tmpl_id", "bom_line_ids")
    def _check_bom_cycle(self):
        
        if boms_to_validate := self.filtered(lambda bom: bom.x_type != "reformulate"):
            super()._check_bom_cycle()
        else:
            subcomponents_dict = dict()

            def _check_cycle(components, finished_products):
                products_to_find = self.env["product.product"]

                for component in components:
                    if component not in subcomponents_dict:
                        products_to_find |= component

                bom_find_result = self._bom_find(products_to_find)
                for component in components:
                    if component not in subcomponents_dict:
                        bom = bom_find_result.get(component, False)
                        if bom:
                            subcomponents = bom.bom_line_ids.filtered(lambda l: not l._skip_bom_line(component)).product_id
                            subcomponents_dict[component] = subcomponents
                        else:
                            subcomponents_dict[component] = self.env["product.product"] 

                    subcomponents = subcomponents_dict[component]
                    if subcomponents:
                        _check_cycle(subcomponents, finished_products | component)

            boms_to_check = self
            if self.bom_line_ids.product_id:
                boms_to_check |= self.search(OR([
                    self._bom_find_domain(product)
                    for product in self.bom_line_ids.product_id
                ]))

            for bom in boms_to_check:
                if not bom.active:
                    continue

                finished_products = bom.product_id or bom.product_tmpl_id.product_variant_ids

                if bom.bom_line_ids.bom_product_template_attribute_value_ids:
                    grouped_by_components = defaultdict(lambda: self.env["product.product"])
                    for finished in finished_products:
                        components = bom.bom_line_ids.filtered(lambda l: not l._skip_bom_line(finished)).product_id
                        grouped_by_components[components] |= finished
                    for components, finished in grouped_by_components.items():
                        _check_cycle(components, finished)
                else:
                    _check_cycle(bom.bom_line_ids.product_id, finished_products)
