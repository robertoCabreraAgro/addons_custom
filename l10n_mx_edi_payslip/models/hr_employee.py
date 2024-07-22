from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_mx_edi_syndicated = fields.Boolean(
        "Syndicated",
        groups="hr.group_hr_user",
        help="Used in the XML to indicate if the worker is "
        "associated with a union. If it is omitted, it is assumed that it is "
        "not associated with any union.",
    )
    l10n_mx_edi_risk_rank_id = fields.Many2one(
        "l10n_mx_edi.job.risk",
        "Job Risk",
        groups="hr.group_hr_user",
        help="Used in the XML to express the key according to the Class in "
        "which the employers must register, according to the activities "
        "carried out by their workers, as provided in article 196 of the "
        "Regulation on Affiliation Classification of Companies, Collection "
        "and Inspection, or in accordance with the regulations Of the Social "
        "Security Institute of the worker.",
    )
    l10n_mx_edi_contract_regime_type = fields.Selection(
        selection=[
            ("02", "Sueldos"),
            ("03", "Jubilados"),
            ("04", "Pensionados"),
            ("05", "Asimilados Miembros Sociedades Cooperativas Produccion"),
            ("06", "Asimilados Integrantes Sociedades Asociaciones Civiles"),
            ("07", "Asimilados Miembros consejos"),
            ("08", "Asimilados comisionistas"),
            ("09", "Asimilados Honorarios"),
            ("10", "Asimilados acciones"),
            ("11", "Asimilados otros"),
            ("99", "Otro Regimen"),
        ],
        string="Regimen Type",
        groups="hr.group_hr_user",
        help="Indicates the regimen type for the employee.",
    )
    l10n_mx_edi_is_assimilated = fields.Boolean(
        "Is assimilated?",
        groups="hr.group_hr_user",
        help="If this employee is assimilated, must be "
        "used this option, to get the correct rules on their payslips",
    )
    l10n_mx_edi_employer_registration_id = fields.Many2one(
        "l10n_mx_edi.employer.registration",
        "Employer Registration",
        groups="hr.group_hr_user",
        store=True,
        readonly=False,
        compute="_compute_l10n_mx_edi_employer_registration_id",
        help="If the company has multiple employer registration, define the correct for this employee.",
    )
    l10n_mx_edi_alimony_ids = fields.One2many(
        "hr.employee.alimony",
        "employee_id",
        "Alimony",
        help="Indicate the alimony for the employee. Will be considered on the payslip.",
    )
    l10n_mx_edi_alimony_count = fields.Integer(
        compute="_compute_l10n_mx_edi_alimony_count",
        string="Alimony Count",
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_mx_edi_disciplinary_warning_ids = fields.One2many(
        "hr.employee.disciplinary.warning",
        "employee_id",
        "Disciplinary Warnings",
        help="Indicates the disciplinary warnings the employee has.",
    )
    l10n_mx_edi_disciplinary_warning_count = fields.Integer(
        compute="_compute_l10n_mx_edi_disciplinary_warning_count",
        string="Disciplinary Warning Count",
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_mx_edi_payment_method_id = fields.Many2one(
        "l10n_mx_edi.payment.method",
        "Payment Way",
        groups="hr.group_hr_user",
    )
    l10n_mx_edi_medical_unit = fields.Char(
        "Medical Unit",
        groups="hr.group_hr_user",
        help="Indicate the medical unit for the employee, will be used in the IDSE report.",
    )
    # TODO: Review, native odoo now have employee_type, check if it is possible to use that field instead this one
    l10n_mx_edi_type = fields.Selection(
        selection=[
            ("1", "Permanent worker"),
            ("2", "Casual City Worker"),
            ("3", "Casual Construction Worker"),
        ],
        string="MX Employee Type",
        groups="hr.group_hr_user",
        help="Indicate the employee type, based on the IDSE options.",
    )
    l10n_mx_birth_state_id = fields.Many2one(
        "res.country.state",
        "State of birth",
        groups="hr.group_hr_user",
        help="Value to set in the SUA report",
    )
    l10n_mx_beneficiary_id = fields.Many2one(
        "res.partner",
        "Beneficiary",
        groups="hr.group_hr_user",
        tracking=True,
        domain="[('type', '=', 'contact')]",
        help="Employee's laboral or legal beneficiary. Indicate the contact information of the person who will get "
        "the laboral or legal benefits in the event of the employee's death.",
    )
    l10n_mx_beneficiary_type = fields.Selection(
        selection=[
            ("spouse", "Spouse"),
            ("child", "Child"),
            ("parent", "Parent"),
            ("concubine", "Concubine"),
            ("other", "Other"),
        ],
        string="Beneficiary Relationship",
        groups="hr.group_hr_user",
        help="Indicates the relation between the employee and the beneficiary.",
    )
    l10n_mx_edi_force_attendances = fields.Boolean(
        "Force Attendances?",
        groups="hr.group_hr_user",
        help="If enable this option, the employee must to register all the attendances, "
        "if an attendance is not registered and the employee must work that day, must be reduce that day from the "
        "salary.",
    )

    @api.depends("l10n_mx_edi_alimony_ids")
    def _compute_l10n_mx_edi_alimony_count(self):
        for employee in self:
            employee.l10n_mx_edi_alimony_count = len(employee.l10n_mx_edi_alimony_ids)

    @api.depends("l10n_mx_edi_disciplinary_warning_ids")
    def _compute_l10n_mx_edi_disciplinary_warning_count(self):
        for employee in self:
            employee.l10n_mx_edi_disciplinary_warning_count = len(employee.l10n_mx_edi_disciplinary_warning_ids)

    @api.depends("address_id")
    def _compute_l10n_mx_edi_employer_registration_id(self):
        emp_reg = self.env["l10n_mx_edi.employer.registration"]
        for record in self.filtered("address_id"):
            record.l10n_mx_edi_employer_registration_id = (
                emp_reg.search([("branch_id", "=", record.address_id.id)], limit=1)
                or record.l10n_mx_edi_employer_registration_id
            )

    @api.onchange("l10n_mx_birth_state_id")
    def onchange_birth_state(self):
        for record in self:
            record.country_of_birth = record.l10n_mx_birth_state_id.country_id

    def get_cfdi_employee_data(self, contract):
        self.ensure_one()
        return {
            "contract_type": contract.contract_type_id.l10n_mx_edi_code,
            "emp_syndicated": "Sí" if self.l10n_mx_edi_syndicated else "No",
            "working_day": self.sudo().get_working_date(),
            "emp_diary_salary": "%.2f" % contract.l10n_mx_edi_integrated_salary,
        }

    def get_working_date(self, whole_text=False):
        """Based on employee category, verify if a category set in this
        employee come from this module and get code."""
        category = self.category_ids.filtered(lambda r: r.color == 3)
        if not category or not category[0].get_external_id()[category[0].id].startswith("l10n_mx_edi_payslip"):
            return ""
        return category[0].name[:2] if not whole_text else category[0].name

    def get_isn_percentage(self):
        self.ensure_one()
        return (self.l10n_mx_edi_employer_registration_id.branch_id or self.address_id).state_id.l10n_mx_payslip_isn
