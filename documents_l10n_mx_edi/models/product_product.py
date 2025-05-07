from odoo import models
from odoo.osv import expression


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _retrieve_product(
        self,
        name=None,
        default_code=None,
        barcode=None,
        company=None,
        extra_domain=None,
        vendor=None,
    ):
        """Override to add more search criterias (description_purchase, supplier info).

        Search all products and find one that matches one of the parameters

        :param name:            The name of the product.
        :param default_code:    The default_code of the product.
        :param barcode:         The barcode of the product.
        :param company:         The company of the product.
        :param extra_domain:    Any extra domain to add to the search.
        :returns:               A product or an empty recordset if not found.
        """
        if name and "\n" in name:
            # cut Sales Description from the name
            name = name.split("\n")[0]
        if vendor:
            supinfo_domains = []
            if name:
                supinfo_domains.append([("product_name", "=ilike", name)])
            if default_code:
                supinfo_domains.append([("product_code", "=ilike", default_code)])
            if supinfo_domains:
                supinfo = self.env["product.supplierinfo"].search(
                    expression.AND(
                        [
                            [("partner_id", "=", vendor.id)],
                            expression.OR(supinfo_domains),
                        ]
                    ),
                    limit=1,
                )
                if supinfo:
                    product = supinfo.product_id or self.env["product.product"].search(
                        [("product_tmpl_id", "=", supinfo.product_tmpl_id.id)], limit=1
                    )
                    if product:
                        return product

        domains = []
        if default_code:
            domains.append([("default_code", "=", default_code)])
        if barcode:
            domains.append([("barcode", "=", barcode)])
        # Search for the product with the exact name, then ilike the name
        name_domains = (
            [("name", "=", name)],
            [("name", "ilike", name)],
            [("description_purchase", "=ilike", name)] if name else [],
        )
        company = company or self.env.company
        for name_domain in name_domains:
            for extra_domain in (
                [
                    *self.env["res.partner"]._check_company_domain(company),
                    ("company_id", "!=", False),
                ],
                [("company_id", "=", False)],
            ):
                product = self.env["product.product"].search(
                    expression.AND(
                        [
                            expression.OR(domains + [name_domain]),
                            extra_domain,
                        ]
                    ),
                    limit=1,
                )
                if product:
                    return product
        return self.env["product.product"]
