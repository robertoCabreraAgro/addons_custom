from odoo import models


class HrVersion(models.Model):
    _inherit = "hr.version"

    def compute_sheet(self):
        """Inherit method to assign secondary dates payslip created"""
        res = super().compute_sheet()
        payslip_obj = self.env["hr.payslip"]
        active_id = self.env.context.get("active_id")
        payslips = payslip_obj.search([("payslip_run_id", "=", active_id)])
        [run_data] = (
            self.env["hr.payslip.run"]
            .browse(active_id)
            .read(["secondary_date_from", "secondary_date_to"])
            if active_id
            else []
        )
        payslips.write(
            {
                "secondary_date_from": run_data.get("secondary_date_from", False),
                "secondary_date_to": run_data.get("secondary_date_to", False),
            }
        )
        return res
