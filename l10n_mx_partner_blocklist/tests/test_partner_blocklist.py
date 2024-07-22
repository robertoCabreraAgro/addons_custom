from odoo.exceptions import ValidationError
from odoo.tests import tagged

from odoo.addons.l10n_mx_edi.tests.common import TestMxEdiCommon


@tagged("post_install", "-at_install")
class TestL10nMxPartnerBlocklist(TestMxEdiCommon):
    def setUp(self):
        super().setUp()
        self.certificate._check_credentials()
        self.partner_camptocamp = self.env.ref("base.res_partner_12")
        self.partner_camptocamp.write(
            {
                "vat": "XAXX010101000",
            }
        )
        self.server_action = self.env.ref("l10n_mx_partner_blocklist.partner_blocklist_status_server_action")

    def test_partner_blocklist(self):
        # Checking partner status messages
        self.assertEqual(self.partner_camptocamp.l10n_mx_in_blocklist, "normal", "The action was already executed")
        self.server_action.with_context(
            **{"active_ids": self.partner_camptocamp.id, "active_model": "res.partner"}
        ).run()
        self.assertEqual(self.partner_camptocamp.l10n_mx_in_blocklist, "done", "The partner is not OK")
        self.env["res.partner.blacklist"].sudo().create(
            {
                "vat": "XAXX010101000",
                "taxpayer_name": self.partner_camptocamp.name,
            }
        )
        self.server_action.with_context(
            **{"active_ids": self.partner_camptocamp.id, "active_model": "res.partner"}
        ).run()
        self.assertEqual(self.partner_camptocamp.l10n_mx_in_blocklist, "blocked", "The partner is not blocked")

        # Checking the user is not able to sale, purchase or invoicing with
        # a blocked partner.
        raise_msg = "The SAT provides a block list"

        try:
            self._create_invoice()
            self.assertEqual(self.partner_camptocamp.l10n_mx_in_blocklist, "blocked", "The Invoice has been validated")
        except ValidationError as e:
            self.assertEqual(raise_msg, e.name[:29])
