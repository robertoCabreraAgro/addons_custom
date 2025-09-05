from odoo import fields, models, api


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    default_planning_manufacturing_project_id = fields.Many2one(
        comodel_name="project.project",
        string="Default Manufacturing Planning Project",
        default_model="planning.slot"
    )

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        IrConfigParam = self.env["ir.config_parameter"].sudo()
        IrConfigParam.set_param(
            "planning_mrp.default_planning_manufacturing_project_id",
            self.default_planning_manufacturing_project_id.id
        )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        IrConfigParam = self.env["ir.config_parameter"].sudo()
        project_id = IrConfigParam.get_param(
            "planning_mrp.default_planning_manufacturing_project_id"
        )
        res.update(
            default_planning_manufacturing_project_id=int(project_id) if project_id else False,
        )
        return res
