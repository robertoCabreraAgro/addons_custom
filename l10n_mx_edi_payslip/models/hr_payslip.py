import base64
import logging
import re
import time
from calendar import monthrange
from datetime import time as dt_time, timedelta, datetime
from io import BytesIO

from lxml import etree, objectify
from pytz import timezone as pytz_timezone
from zeep import Client
from zeep.transports import Transport

from odoo import Command, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tools import (
    DEFAULT_SERVER_DATETIME_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT,
    groupby,
)
from odoo.tools.xml_utils import _check_with_xsd

_logger = logging.getLogger(__name__)


PAYSLIP_TEMPLATE = "l10n_mx_edi_payslip.payroll12"
PAYSLIP_TEMPLATE_40 = "l10n_mx_edi_payslip.payroll12_40"
# TODO: Update reference to new Odoo module
CFDI_XSLT_CADENA_40 = "l10n_mx_edi_payslip/data/4.0/cadenaoriginal.xslt"


def create_list_html(array):
    """Convert an array of string to a html list.
    :param list array: A list of strings
    :return: empty string if not array, an html list otherwise.
    :rtype: str"""
    if not array:  # pragma: no cover
        return ""  # pragma: no cover
    msg = ""
    for item in array:
        msg += "<li>" + item + "</li>"
    return "<ul>" + msg + "</ul>"


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    l10n_mx_edi_payment_date = fields.Date(
        "Payment Date",
        required=True,
        default=time.strftime("%Y-%m-01"),
        help="Save the payment date that will be added on CFDI.",
    )
    l10n_mx_edi_cfdi_name = fields.Char(
        string="CFDI name",
        copy=False,
        readonly=True,
        help="The attachment name of the CFDI.",
    )
    l10n_mx_edi_cfdi = fields.Binary(
        "CFDI content",
        compute="_compute_cfdi_values",
        help="The cfdi xml content encoded in base64.",
    )
    l10n_mx_edi_overtime_line_ids = fields.One2many(
        "hr.payslip.overtime",
        "payslip_id",
        "Extra hours",
        readonly=True,
        copy=True,
        help="Used in XML like optional node to express the extra hours applicable by employee.",
    )
    l10n_mx_edi_pac_status = fields.Selection(
        selection=[
            ("retry", "Retry"),
            ("to_sign", "To sign"),
            ("signed", "Signed"),
            ("to_cancel", "To cancel"),
            ("cancelled", "Cancelled"),
        ],
        string="PAC status",
        readonly=True,
        copy=False,
        help="Refers to the status of the payslip inside the PAC.",
    )
    l10n_mx_edi_sat_status = fields.Selection(
        selection=[
            ("none", "State not defined"),
            ("undefined", "Not Synced Yet"),
            ("not_found", "Not Found"),
            ("cancelled", "Cancelled"),
            ("valid", "Valid"),
        ],
        string="SAT status",
        readonly=True,
        copy=False,
        required=True,
        tracking=True,
        default="undefined",
        help="Refers to the status of the payslip inside the SAT system.",
    )
    l10n_mx_edi_cfdi_uuid = fields.Char(
        "Fiscal Folio",
        compute="_compute_cfdi_values",
        help="Folio in electronic payroll, is returned by SAT when send to stamp.",
    )
    l10n_mx_edi_cfdi_supplier_rfc = fields.Char(
        "Supplier RFC",
        compute="_compute_cfdi_values",
        help="The supplier tax identification number.",
    )
    l10n_mx_edi_cfdi_customer_rfc = fields.Char(
        "Customer RFC",
        compute="_compute_cfdi_values",
        help="The customer tax identification number.",
    )
    l10n_mx_edi_cfdi_amount = fields.Float(
        "Total Amount",
        compute="_compute_cfdi_values",
        help="The total amount reported on the cfdi.",
    )
    l10n_mx_edi_action_title_ids = fields.One2many(
        "hr.payslip.action.titles",
        "payslip_id",
        string="Action or Titles",
        help="If the payslip have perceptions with code 045, assign here the "
        "values to the attribute in XML, use the perception type to indicate "
        "if apply to exempt or taxed.",
    )
    l10n_mx_edi_extra_node_ids = fields.One2many(
        "hr.payslip.extra.perception",
        "payslip_id",
        string="Extra data to perceptions",
        help="If the payslip have perceptions with code in 022, 023 or 025,"
        "must be created a record with data that will be assigned in the "
        'node "SeparacionIndemnizacion", or if the payslip have perceptions '
        "with code in 039 or 044 must be created a record with data that will "
        'be assigned in the node "JubilacionPensionRetiro". Only must be '
        "created a record by node.",
    )
    l10n_mx_edi_balance_favor = fields.Float(
        "Balance in Favor",
        help="If the payslip include other payments, and "
        "one of this records have the code 004 is need add the balance in "
        'favor to assign in node "CompensacionSaldosAFavor".',
    )
    l10n_mx_edi_comp_year = fields.Integer(
        "Year",
        help="If the payslip include other payments, and "
        "one of this records have the code 004 is need add the year to assign "
        'in node "CompensacionSaldosAFavor".',
    )
    l10n_mx_edi_remaining = fields.Float(
        "Remaining",
        help="If the payslip include other payments, and "
        "one of this records have the code 004 is need add the remaining to "
        'assign in node "CompensacionSaldosAFavor".',
    )
    l10n_mx_edi_source_resource = fields.Selection(
        selection=[
            ("IP", "Own income"),
            ("IF", "Federal income"),
            ("IM", "Mixed income"),
        ],
        string="Source Resource",
        help="Used in XML to identify the source of the resource used "
        "for the payment of payroll of the personnel that provides or "
        "performs a subordinate or assimilated personal service to salaries "
        "in the dependencies. This value will be set in the XML attribute "
        '"OrigenRecurso" to node "EntidadSNCF".',
    )
    l10n_mx_edi_amount_sncf = fields.Float(
        "Own resource",
        help='When the attribute in "Source Resource" is "IM" '
        "this attribute must be added to set in the XML attribute "
        '"MontoRecursoPropio" in node "EntidadSNCF", and must be less that '
        '"TotalPercepciones" + "TotalOtrosPagos"',
    )
    l10n_mx_edi_cfdi_string = fields.Char(
        "CFDI Original String",
        help='Attribute "cfdi_cadena_original" '
        "returned by PAC request when is stamped the CFDI, this attribute is "
        "used on report.",
    )
    l10n_mx_edi_origin = fields.Char(
        string="CFDI Origin",
        copy=False,
        help="In some cases the payroll must be regenerated to fix data in it."
        " In that cases is necessary this field filled, the format is: "
        "\n04|UUID1, UUID2, ...., UUIDn.\n"
        'Example:\n"04|89966ACC-0F5C-447D-AEF3-3EED22E711EE,'
        '89966ACC-0F5C-447D-AEF3-3EED22E711EE"',
    )
    l10n_mx_edi_expedition_date = fields.Date(
        string="Payslip date",
        readonly=True,
        copy=False,
        index=True,
        help="Keep empty to use the current date",
    )
    l10n_mx_edi_time_payslip = fields.Char(
        string="Time payslip",
        readonly=True,
        copy=False,
        help="Keep empty to use the current México central time",
    )
    l10n_mx_edi_error = fields.Html(
        "MX Edi Error",
        copy=False,
        readonly=True,
        help="The text of the last error that happened during Electronic Payroll operation.",
    )
    l10n_mx_edi_error_count = fields.Integer(
        copy=False,
        default=0,
        help="Technical field to count the errors in the signing, it is used to show the error message in the view.",
    )
    l10n_mx_edi_cancellation = fields.Char(
        string="Cancellation Case",
        copy=False,
        tracking=True,
        help="The SAT has 3 cases in which an payslip could be cancelled, please fill this field based on your case:\n"
        "Case 1: The invoice was generated with errors and must be re-invoiced, the format must be:\n"
        '"01" The UUID will be taken from the new invoice related to the record.\n'
        "Case 2: The invoice has an error on the customer, this will be cancelled and replaced by a new with the "
        'customer fixed. The format must be:\n "02", only is required the case number.\n'
        "Case 3: The invoice was generated but the operation was cancelled, this will be cancelled and not must be "
        'generated a new invoice. The format must be:\n "03", only is required the case number.\n',
    )
    l10n_mx_edi_cancel_payslip_id = fields.Many2one(
        comodel_name="hr.payslip",
        string="Substituted By",
        compute="_compute_l10n_mx_edi_cancel",
    )
    sent = fields.Boolean(
        readonly=True,
        copy=False,
        help="It indicates that the payslip has been sent.",
    )
    input_line_ids = fields.One2many(copy=True)
    l10n_mx_edi_employer_registration_id = fields.Many2one(
        related="employee_id.l10n_mx_edi_employer_registration_id",
        store=True,
    )

    def _compute_l10n_mx_edi_cancel(self):
        for payslip in self:
            if payslip.l10n_mx_edi_cfdi_uuid:
                replaced_payslip = payslip.search(
                    [
                        ("l10n_mx_edi_origin", "like", "04|%"),
                        (
                            "l10n_mx_edi_origin",
                            "like",
                            "%" + payslip.l10n_mx_edi_cfdi_uuid + "%",
                        ),
                        ("company_id", "=", payslip.company_id.id),
                    ],
                    limit=1,
                )
                payslip.l10n_mx_edi_cancel_payslip_id = replaced_payslip
            else:
                payslip.l10n_mx_edi_cancel_payslip_id = None

    @api.depends("l10n_mx_edi_payment_date")
    def _compute_warning_message(self):
        super()._compute_warning_message()
        for slip in self.filtered(
            lambda p: p.l10n_mx_edi_payment_date
            and not p.date_from <= p.l10n_mx_edi_payment_date <= p.date_to
        ):
            date_warning = self.env._(
                "Please note that the payment date falls outside the payslip period. Proceed only if "
                "this is expected."
            )
            if slip.warning_message:
                date_warning = "%s\n  ・ %s" % (slip.warning_message, date_warning)
            else:
                date_warning = "%s\n  ・ %s" % (
                    self.env._("This payslip can be erroneous :"),
                    date_warning,
                )
            slip.warning_message = date_warning
        return True

    @api.depends("l10n_mx_edi_cfdi_name")
    def _compute_cfdi_values(self):
        """Fill the payroll fields from the CFDI values."""
        for record in self:
            attachment_id = record.l10n_mx_edi_retrieve_last_attachment()
            record.l10n_mx_edi_cfdi_uuid = None
            if not attachment_id:
                record.l10n_mx_edi_cfdi = None
                record.l10n_mx_edi_cfdi_supplier_rfc = ""
                record.l10n_mx_edi_cfdi_customer_rfc = ""
                record.l10n_mx_edi_cfdi_amount = 0
                continue
            # At this moment, the attachment contains the file size in its
            # 'datas' field because to save some memory, the attachment will
            # store its data on the physical disk.
            # To avoid this problem, we read the 'datas' directly on the disk.
            datas = attachment_id._file_read(attachment_id.store_fname)
            record.l10n_mx_edi_cfdi = datas
            tree = record.l10n_mx_edi_get_xml_etree(datas)
            # if already signed, extract uuid
            tfd_node = record.l10n_mx_edi_get_tfd_etree(tree)
            if tfd_node is not None:
                record.l10n_mx_edi_cfdi_uuid = tfd_node.get("UUID")
            record.l10n_mx_edi_cfdi_amount = tree.get("Total", tree.get("total"))
            record.l10n_mx_edi_cfdi_supplier_rfc = tree.Emisor.get(
                "Rfc", tree.Emisor.get("rfc")
            )
            record.l10n_mx_edi_cfdi_customer_rfc = tree.Receptor.get(
                "Rfc", tree.Receptor.get("rfc")
            )

    def compute_sheet(self):
        if (
            self.filtered(lambda r: r.l10n_mx_edi_is_required())
            and not self.env.company.l10n_mx_edi_minimum_wage
        ):
            raise ValidationError(
                self.env._(
                    "Please, you set the minimum wage in Mexico to that you can calculate the payroll."
                )
            )
        res = super().compute_sheet()
        for payslip in self.filtered(lambda slip: slip.state in ["draft", "verify"]):
            payslip.write(
                {
                    "l10n_mx_edi_extra_node_ids": [
                        Command.create(node) for node in payslip._get_extra_nodes()
                    ]
                }
            )
            payslip.line_ids.filtered(
                lambda line: line.category_id.code != "NETSA" and (not line.amount)
            ).unlink()
        return res

    def _l10n_mx_edi_finkok_verify_is_stamped(self, cfdi_values):
        """Returns the signed CFDI if it exists in FINKOK.

        This method uses the FINKOK service to verify if the CFDI has been
        previously signed.
        """
        finkok_info = self._l10n_mx_edi_finkok_info(self.company_id, "sign")
        try:
            transport = Transport(timeout=20)
            client = Client(finkok_info["url"], transport=transport)
            response = client.service.stamped(
                cfdi_values["cfdi"], finkok_info["username"], finkok_info["password"]
            )
        except BaseException as e:
            self.l10n_mx_edi_log_error(str(e))
            return False
        if not response.UUID:
            return False
        xml_signed_bytes = response.xml.encode("utf-8")
        xml_signed = base64.b64encode(xml_signed_bytes)
        self._l10n_mx_edi_post_sign_process(xml_signed, 0, None)
        cfdi_values["cfdi"] = xml_signed_bytes
        return True

    def action_open_overtimes(self):
        self.ensure_one()
        self.auto_generate_overtimes()
        weeks = []
        for day in range((self.date_to - self.date_from).days + 1):
            weeks.append((self.date_from + timedelta(days=day)).isocalendar()[1])
        return {
            "name": self.env._("Overtimes"),
            "view_mode": "list,form",
            "res_model": "hr.payslip.overtime",
            "view_id": False,
            "type": "ir.actions.act_window",
            "domain": [
                ("employee_id", "=", self.employee_id.id),
                ("week", "in", weeks),
                ("name", ">=", self.date_from - timedelta(days=7)),
                ("name", "<=", self.date_to + timedelta(days=7)),
            ],
        }

    def action_payslip_cancel(self):
        """Overwrite method when state is done, to allow cancel payslip in done"""
        to_cancel = self.filtered(lambda r: r.state == "done")
        # First cancell payslips whose cancelation case is 01
        case_01 = to_cancel.filtered(
            lambda p: p.l10n_mx_edi_cancellation
            and p.l10n_mx_edi_cancellation.split("|")[0] == "01"
            and p.l10n_mx_edi_pac_status == "to_cancel"
        )
        case_01.write({"state": "cancel"})
        super(HrPayslip, case_01).action_payslip_cancel()
        to_cancel = to_cancel - case_01

        if "signed" in to_cancel.mapped("l10n_mx_edi_pac_status"):
            raise UserError(
                self.env._(
                    "You have selected signed payslips. Please, use the option Request Edi Cancellation "
                    "instead directly cancelling the payslip"
                )
            )
        to_cancel.write({"state": "cancel"})
        to_cancel.filtered(
            lambda r: r.l10n_mx_edi_pac_status in ["to_sign", "retry"]
        ).write(
            {
                "l10n_mx_edi_pac_status": "cancelled",
                "l10n_mx_edi_error": False,
                "l10n_mx_edi_error_count": 0,
            }
        )
        res = super().action_payslip_cancel()
        return res

    def action_payroll_sent(self):
        """Open a window to compose an email, with the edi payslip template
        message loaded by default"""
        self.ensure_one()
        template = self.env.ref("hr_payroll.mail_template_new_payslip", False)
        compose_form = self.env.ref("mail.email_compose_message_wizard_form", False)
        ctx = self._context.copy()
        ctx["default_model"] = "hr.payslip"
        ctx["default_res_ids"] = self.ids
        ctx["default_use_template"] = bool(template)
        ctx["default_template_id"] = template.id or False
        ctx["default_composition_mode"] = "comment"
        return {
            "name": self.env._("Compose Email"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "mail.compose.message",
            "views": [(compose_form.id, "form")],
            "view_id": compose_form.id,
            "target": "new",
            "context": ctx,
        }

    def action_payslip_draft(self):
        for record in self.filtered("l10n_mx_edi_cfdi_uuid"):
            record.l10n_mx_edi_origin = "04|%s" % record.l10n_mx_edi_cfdi_uuid
        self.write(
            {
                "l10n_mx_edi_expedition_date": False,
                "l10n_mx_edi_time_payslip": False,
            }
        )
        return super().action_payslip_draft()

    def action_payslip_done(self):
        """Generates the cfdi attachments for mexican companies when validated."""
        if not self.env.user.has_group("l10n_mx_edi_payslip.allow_validate_payslip"):
            raise UserError(
                self.env._(
                    "Only Managers who are allow to validate payslip can perform this operation"
                )
            )
        result = super().action_payslip_done()
        version = self.l10n_mx_edi_get_pac_version()
        for record in self.filtered(lambda r: r.l10n_mx_edi_is_required()):
            if not record.net_wage and record.struct_id.type_id.l10n_mx_edi_type == "O":
                record.message_post(
                    body=self.env._(
                        "Stamp process omitted because the Net Salary is 0."
                    )
                )
                continue
            # Assign overtimes to avoid write in that records
            self.env["hr.payslip.overtime"].search(
                [
                    ("employee_id", "=", record.employee_id.id),
                    ("name", ">=", record.date_from),
                    ("name", "<=", record.date_to),
                ]
            ).write({"payslip_id": record.id})
            record._l10n_mx_edi_update_expedition_date()
            record.l10n_mx_edi_cfdi_name = "%s-MX-Payroll-%s.xml" % (
                (record.number).replace("/", ""),
                version,
            )
            # Prepare to send sign
            record.l10n_mx_edi_pac_status = "to_sign"
        return result

    def _get_extra_nodes(self):
        """Create the extra nodes dict(s)
        :return: a list with the extra nodes to apply
        :rtype: list
        """
        self.ensure_one()
        nodes = []
        categ_g = self.env.ref(
            "l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_taxed"
        ).id
        categ_e = self.env.ref(
            "l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_exempt"
        ).id
        perceptions = self.line_ids.search(
            [
                ("id", "in", self.line_ids.ids),
                ("category_id", "in", [categ_g, categ_e]),
                ("total", "!=", "0"),
                (
                    "salary_rule_id.l10n_mx_edi_code",
                    "in",
                    ["022", "023", "025", "039", "044"],
                ),
            ]
        )
        separation_line_ids = perceptions.search(
            [
                ("id", "in", perceptions.ids),
                ("salary_rule_id.l10n_mx_edi_code", "in", ("022", "023", "025")),
            ]
        )
        total = round(sum(separation_line_ids.mapped("total")), 2)
        if separation_line_ids and total:
            seniority = self.contract_id.get_seniority(date_to=self.date_to)
            years = (
                round(seniority.get("years"), 0)
                if seniority.get("months") > 6
                or (seniority.get("months") == 6 and seniority.get("days") > 1)
                else seniority.get("years")
            )
            nodes.append(
                {
                    "node": "separation",
                    "amount_total": total,
                    "last_salary": self.contract_id.wage,
                    "service_years": years,
                    "non_accumulable_income": (
                        (total - self.contract_id.wage)
                        if (total > self.contract_id.wage)
                        else 0
                    ),
                    "accumulable_income": (
                        self.contract_id.wage
                        if (total > self.contract_id.wage)
                        else total
                    ),
                }
            )
        retirement_line_ids = perceptions.filtered(
            lambda line: line.salary_rule_id.l10n_mx_edi_code == "039"
        )
        retirement_partial_ids = perceptions.filtered(
            lambda line: line.salary_rule_id.l10n_mx_edi_code == "044"
        )
        if retirement_line_ids and retirement_partial_ids:
            raise UserError(
                self.env._(
                    "You have perceptions with code 039 and 044. You can only have one of them."
                )
            )
        retirement_line_ids = retirement_line_ids or retirement_partial_ids
        total = round(sum(retirement_line_ids.mapped("total")), 2)
        if retirement_line_ids and total:
            nodes.append(
                {
                    "node": "retirement",
                    "amount_total": total,
                    "amount_daily": (
                        self.contract_id.wage / 30
                        if (
                            retirement_line_ids[0].salary_rule_id.l10n_mx_edi_code
                            == "044"
                        )
                        else 0
                    ),
                    "non_accumulable_income": (
                        (total - self.contract_id.wage)
                        if (total > self.contract_id.wage)
                        else 0
                    ),
                    "accumulable_income": (
                        self.contract_id.wage
                        if (total > self.contract_id.wage)
                        else total
                    ),
                }
            )
        self.l10n_mx_edi_extra_node_ids.unlink()
        return nodes

    def get_cfdi_related(self):
        """To node CfdiRelacionados get documents related with each payslip
        from l10n_mx_edi_origin, hope the next structure:
            relation type|UUIDs separated by ,"""
        # TODO - Same method that on invoice
        self.ensure_one()
        if not self.l10n_mx_edi_origin:
            return {}
        origin = self.l10n_mx_edi_origin.split("|")
        uuids = origin[1].split(",") if len(origin) > 1 else []
        return {
            "type": origin[0],
            "related": [u.strip() for u in uuids],
        }

    def l10n_mx_edi_is_required(self):
        self.ensure_one()
        company = self.company_id or self.contract_id.company_id
        return company.country_id == self.env.ref("base.mx")

    def l10n_mx_edi_log_error(self, message):
        # TODO - Same method that on invoice
        self.ensure_one()
        if not self.l10n_mx_edi_error:
            self.l10n_mx_edi_error = self.env._("Error during the process:")
        self.l10n_mx_edi_error = "%s%s" % (self.l10n_mx_edi_error, message)

    @api.model
    def _get_l10n_mx_edi_cadena(self):
        """Method used in the report"""
        self.ensure_one()
        # get the xslt path
        xslt_path = CFDI_XSLT_CADENA_40
        # get the cfdi as eTree
        cfdi = self.l10n_mx_edi_get_xml_etree()
        # return the cadena
        cadena_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(cadena_root)(cfdi))

    def _l10n_mx_edi_finkok_get_status(
        self, username, password, supplier_rfc, customer_rfc, uuid, total
    ):
        """Check the possible form of cancellation and the status of the CFDI.

        It allows to identify if the CFDI is cancellable.
        :param username: The username provided by the Finkok platform.
        :type str
        :param password: The password provided by the Finkok platform.
        :type str
        :param supplier_rfc: Taxpayer id - The RFC issuer of the invoices to consult.
        :type str
        :param customer_rfc: Rtaxpayer_id - The RFC receiver of the CFDI to consult.
        :type str
        :param uuid: The UUID of the CFDI to consult.
        :type str
        :param total:The value of the total attribute of the CFDI.
        :type float
        :returns: AcuseSatEstatus statusResponse  https://wiki.finkok.com/doku.php?id=get_sat_status
        :rtype: suds.sudsobject
        """
        self.ensure_one()
        url = self._l10n_mx_edi_finkok_info(self.company_id, "cancel")["url"]
        try:
            transport = Transport(timeout=20)
            client = Client(url, transport=transport)
            return client.service.get_sat_status(
                username, password, supplier_rfc, customer_rfc, uuid=uuid, total=total
            )
        except Exception as e:
            self.l10n_mx_edi_log_error(str(e))
        return False

    def _l10n_mx_edi_post_sign_process(self, xml_signed, code=None, msg=None):
        """Post process the results of the sign service.

        :param xml_signed: the xml signed datas codified in base64
        :type xml_signed: base64
        :param code: an eventual error code
        :type code: string
        :param msg: an eventual error msg
        :type msg: string
        """
        self.ensure_one()
        if xml_signed:
            body_msg = self.env._("The sign service has been called with success")
            # Update the pac status
            self.l10n_mx_edi_pac_status = "signed"
            # Update the content of the attachment
            attachment_id = self.l10n_mx_edi_retrieve_last_attachment()
            attachment_id.write({"datas": xml_signed, "mimetype": "application/xml"})
            post_msg = [self.env._("The content of the attachment has been updated")]
        else:
            self.l10n_mx_edi_pac_status = "retry"
            body_msg = self.env._("The sign service requested failed")
            post_msg = []
        if code:
            post_msg.extend([self.env._("Code: ") + str(code)])
        if msg:
            post_msg.extend([self.env._("Message: ") + msg])

        body = body_msg + create_list_html(post_msg)
        if xml_signed:
            self.message_post(body=body, body_is_html=True)
        else:
            self.l10n_mx_edi_log_error(body)

    def _l10n_mx_edi_post_cancel_process(self, cancelled, code=None, msg=None):
        """Post process the results of the cancel service.

        :param cancelled: is the cancel has been done with success
        :type cancelled: bool
        :param code: an eventual error code
        :type code: string
        :param msg: an eventual error msg
        :type msg: string
        """

        self.ensure_one()
        if cancelled:
            body_msg = self.env._("The cancel service has been called with success")
            self.l10n_mx_edi_pac_status = "cancelled"
        else:
            body_msg = self.env._("The cancel service requested failed")
        post_msg = []
        if code:
            post_msg.extend([self.env._("Code: ") + str(code)])
        if msg:
            post_msg.extend([self.env._("Message: ") + msg])

        body = body_msg + create_list_html(post_msg)
        if cancelled:
            self.message_post(body=body, body_is_html=True)
            self.action_payslip_cancel()
        else:
            self.l10n_mx_edi_error_count = 1
            self.l10n_mx_edi_log_error(body)

    @api.model
    def _l10n_mx_edi_process_payslip_web_services(self, job_count=50, cancel_job=10):
        self.search(
            [
                ("state", "=", "done"),
                ("l10n_mx_edi_pac_status", "=", "to_sign"),
            ],
            order="l10n_mx_edi_expedition_date",
            limit=job_count,
        ).l10n_mx_edi_update_pac_status()

        self.search(
            [
                ("state", "=", "done"),
                ("l10n_mx_edi_pac_status", "=", "to_cancel"),
            ],
            order="l10n_mx_edi_expedition_date",
            limit=cancel_job,
        ).l10n_mx_edi_update_pac_status()

    @api.model
    def l10n_mx_edi_generate_cadena(self, xslt_path, cfdi_as_tree):
        """Generate the cadena of the cfdi based on an xslt file.
        The cadena is the sequence of data formed with the information
        contained within the cfdi. This can be encoded with the certificate
        to create the digital seal. Since the cadena is generated with the
        payslip data, any change in it will be noticed resulting in a different
        cadena and so, ensure the payslip has not been modified.
        :param xslt_path: The path to the xslt file.
        :type xslt_path: str
        :param cfdi_as_tree: The cfdi converted as a tree
        :type cfdi_as_tree: etree
        :return: A string computed with the payslip data called the cadena
        :rtype: str
        """
        # TODO - Same method that on invoice
        self.ensure_one()
        xslt_root = etree.parse(tools.file_open(xslt_path))
        return str(etree.XSLT(xslt_root)(cfdi_as_tree))

    @api.model
    def l10n_mx_edi_get_tfd_etree(self, cfdi):
        """Get the TimbreFiscalDigital node from the cfdi.

        :param cfdi: The cfdi as etree
        :type cfdi: etree
        :return: the TimbreFiscalDigital node
        :rtype: etree
        """
        # TODO - This method is the same that invoice.
        if not hasattr(cfdi, "Complemento"):
            return None
        attribute = "tfd:TimbreFiscalDigital[1]"
        namespace = {"tfd": "http://www.sat.gob.mx/TimbreFiscalDigital"}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    @api.model
    def l10n_mx_edi_get_payroll_etree(self, cfdi):
        """Get the Complement node from the cfdi.
        :param cfdi: The cfdi as etree
        :type cfdi: etree
        :return: the Payment node
        :rtype: etree
        """
        if not hasattr(cfdi, "Complemento"):
            return None
        attribute = "//nomina12:Nomina"
        namespace = {"nomina12": "http://www.sat.gob.mx/nomina12"}
        node = cfdi.Complemento.xpath(attribute, namespaces=namespace)
        return node[0] if node else None

    # -------------------------------------------------------------------------
    # SAT/PAC service methods
    # -------------------------------------------------------------------------

    @api.model
    def _l10n_mx_edi_solfact_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.sudo().l10n_mx_edi_pac_username
        password = company_id.sudo().l10n_mx_edi_pac_password
        url = (
            "https://testing.solucionfactible.com/ws/services/Timbrado?wsdl"
            if test
            else "https://solucionfactible.com/ws/services/Timbrado?wsdl"
        )
        return {
            "url": url,
            "multi": False,  # TODO: implement multi
            "username": "testing@solucionfactible.com" if test else username,
            "password": "timbrado.SF.16672" if test else password,
        }

    def _l10n_mx_edi_solfact_sign(self, pac_info):
        """SIGN for Solucion Factible."""
        url = pac_info["url"]
        username = pac_info["username"]
        password = pac_info["password"]
        for record in self:
            cfdi = record.l10n_mx_edi_cfdi
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.timbrar(username, password, cfdi, False)
            except BaseException as e:
                record.l10n_mx_edi_log_error(str(e))
                continue
            msg = getattr(response.resultados[0], "mensaje", None)
            code = getattr(response.resultados[0], "status", None)
            xml_signed = getattr(response.resultados[0], "cfdiTimbrado", None)
            record._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

    def _l10n_mx_edi_solfact_cancel(self, pac_info):
        """CANCEL for Solucion Factible."""
        # TODO - Same method that on invoice
        url = pac_info["url"]
        username = pac_info["username"]
        password = pac_info["password"]
        for record in self:
            uuids = [record.l10n_mx_edi_cfdi_uuid]
            certificate = self._get_valid_certificate()
            cer_pem = base64.b64decode(certificate.pem_certificate)
            key_pem = base64.b64decode(certificate.private_key_id.pem_key)
            key_password = certificate.password
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.cancelar(
                    username, password, uuids, cer_pem, key_pem, key_password
                )
            except BaseException as e:
                record.l10n_mx_edi_log_error(str(e))
                continue
            msg = getattr(response.resultados[0], "mensaje", None)
            code = getattr(response.resultados[0], "statusUUID", None)
            cancelled = code in ("201", "202")
            record._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    def _l10n_mx_edi_finkok_info(self, company_id, service_type):
        test = company_id.l10n_mx_edi_pac_test_env
        username = company_id.sudo().l10n_mx_edi_pac_username
        password = company_id.sudo().l10n_mx_edi_pac_password
        if service_type == "sign":
            url = (
                "http://demo-facturacion.finkok.com/servicios/soap/stamp.wsdl"
                if test
                else "http://facturacion.finkok.com/servicios/soap/stamp.wsdl"
            )
        else:
            url = (
                "http://demo-facturacion.finkok.com/servicios/soap/cancel.wsdl"
                if test
                else "http://facturacion.finkok.com/servicios/soap/cancel.wsdl"
            )
        return {
            "url": url,
            "multi": False,  # TODO: implement multi
            "username": "cfdi@vauxoo.com" if test else username,
            "password": "vAux00__" if test else password,
        }

    def _l10n_mx_edi_finkok_sign(self, pac_info):
        """SIGN for Finkok."""
        # TODO - Same method that on invoice
        url = pac_info["url"]
        username = pac_info["username"]
        password = pac_info["password"]
        for record in self:
            cfdi = record.l10n_mx_edi_cfdi
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                response = client.service.stamp(cfdi, username, password)
            except BaseException as e:
                record.l10n_mx_edi_log_error(str(e))
                continue
            code = 0
            msg = None
            self.l10n_mx_edi_error_count = 0
            if response.Incidencias and not response.xml:
                code = getattr(response.Incidencias.Incidencia[0], "CodigoError", None)
                msg = getattr(
                    response.Incidencias.Incidencia[0], "MensajeIncidencia", None
                )
                if code == "301":
                    msg = "%s (%s)" % (
                        msg,
                        getattr(response.Incidencias.Incidencia[0], "ExtraInfo", None),
                    )
                self.l10n_mx_edi_error_count = len(response.Incidencias.Incidencia)
            xml_signed = getattr(response, "xml", None)
            if xml_signed:
                xml_signed = base64.b64encode(xml_signed.encode("utf-8"))
            record._l10n_mx_edi_post_sign_process(xml_signed, code, msg)

    def _l10n_mx_edi_finkok_cancel(self, pac_info):
        """CANCEL for Finkok."""
        url = pac_info["url"]
        username = pac_info["username"]
        password = pac_info["password"]
        for record in self:
            uuid = record.l10n_mx_edi_cfdi_uuid
            company_id = self.company_id or self.contract_id.company_id
            certificate = self._get_valid_certificate()
            cer_pem = certificate._get_pem_cer(certificate.content)
            key_pem = certificate._get_pem_key(certificate.key, certificate.password)
            cancelled = False
            code = False
            cancellation_data = (record.l10n_mx_edi_cancellation or "").split("|")
            try:
                transport = Transport(timeout=20)
                client = Client(url, transport=transport)
                factory = client.type_factory("apps.services.soap.core.views")
                uuid_type = factory.UUID()
                uuid_type.UUID = uuid or ""
                uuid_type.Motivo = cancellation_data[0]
                if (
                    cancellation_data[0] == "01"
                    and record.l10n_mx_edi_cancel_payslip_id
                    and record.l10n_mx_edi_cancel_payslip_id != record
                ):
                    uuid_type.FolioSustitucion = (
                        record.l10n_mx_edi_cancel_payslip_id.l10n_mx_edi_cfdi_uuid
                    )
                docs_list = factory.UUIDArray(uuid_type)
                response = client.service.cancel(
                    docs_list,
                    username,
                    password,
                    company_id.vat,
                    cer_pem,
                    key_pem,
                )
            except BaseException as e:
                record.l10n_mx_edi_log_error(str(e))
                continue

            if not getattr(response, "Folios", None):
                code = getattr(response, "CodEstatus", None)
                msg = (
                    self.env._("Cancelling got an error")
                    if code
                    else self.env._(
                        "A delay of 2 hours has to be respected before to cancel"
                    )
                )
            else:
                code = getattr(response.Folios.Folio[0], "EstatusUUID", None)
                cancelled = code in ("201", "202")  # cancelled or previously cancelled
                # no show code and response message if cancel was success
                code = "" if cancelled else code
                msg = "" if cancelled else self.env._("Cancelling got an error")

            if not cancelled:
                record._l10n_mx_edi_post_cancel_process(cancelled, code, msg)
                continue

            # Check if it is really cancelled, Could give a false positive if the original CFDI was not SAT valid
            sat_status = record._l10n_mx_edi_finkok_get_status(
                username,
                password,
                record.l10n_mx_edi_cfdi_supplier_rfc,
                record.l10n_mx_edi_cfdi_customer_rfc,
                record.l10n_mx_edi_cfdi_uuid,
                record.l10n_mx_edi_cfdi_amount,
            )
            status = (
                sat_status
                and getattr(sat_status, "sat", None)
                and getattr(sat_status["sat"], "EstatusCancelacion", None)
            )
            if not status or status == "None":
                code = "SAT"
                msg = self.env._(
                    "The PAC has sent this document to cancel, but the SAT has not processed it yet. "
                    "Please try again in a few minutes or wait for the automatic action. SAT status for "
                    "cancellation: %s",
                    getattr(sat_status, "EsCancelable", self.env._("Not defined")),
                )
                cancelled = False

            record._l10n_mx_edi_post_cancel_process(cancelled, code, msg)

    def _l10n_mx_edi_call_service(self, service_type):
        """Call the right method according to the pac_name,
        it's info returned by the '_l10n_mx_edi_%s_info' % pac_name'
        method and the service_type passed as parameter.
        :param service_type: sign or cancel
        :type service_type: string
        """
        # Regroup the payslip by company (= by pac)
        comp_x_records = groupby(
            self, lambda r: r.company_id or r.contract_id.company_id
        )
        for company_id, records in comp_x_records:
            pac_name = company_id.l10n_mx_edi_pac
            if not pac_name:
                continue
            # Get the informations about the pac
            pac_info_func = "_l10n_mx_edi_%s_info" % pac_name
            service_func = "_l10n_mx_edi_%s_%s" % (pac_name, service_type)
            pac_info = getattr(self, pac_info_func)(company_id, service_type)
            # Call the service with payslips one by one or all together according to the 'multi' value.
            multi = pac_info.pop("multi", False)
            if multi:
                # rebuild the recordset
                contract_ids = self.search([("company_id", "=", company_id.id)])
                records = self.search(
                    [
                        ("id", "in", self.ids),
                        "|",
                        ("company_id", "=", company_id.id),
                        ("contract_id", "in", contract_ids.ids),
                    ]
                )
                getattr(records, service_func)(pac_info)
            else:
                for record in records:
                    getattr(record, service_func)(pac_info)

    def _l10n_mx_edi_sign(self):
        """Call the sign service with records that can be signed."""
        records = self.search(
            [
                (
                    "l10n_mx_edi_pac_status",
                    "not in",
                    ["signed", "to_cancel", "cancelled", "retry"],
                ),
                ("id", "in", self.ids),
            ]
        )
        records._l10n_mx_edi_call_service("sign")

    def _l10n_mx_edi_cancel(self):
        """Call the cancel service with records that can be signed."""
        records = self.search(
            [
                (
                    "l10n_mx_edi_pac_status",
                    "in",
                    ["to_sign", "signed", "to_cancel", "retry"],
                ),
                ("id", "in", self.ids),
            ]
        )
        records.write({"l10n_mx_edi_error": False})
        for record in records:
            if record.l10n_mx_edi_pac_status in ["to_sign", "retry"]:
                record.l10n_mx_edi_pac_status = "cancelled"
                record.message_post(
                    body=self.env._("The cancel service has been called with success")
                )
            else:
                record.l10n_mx_edi_pac_status = "to_cancel"
        records = self.search(
            [("l10n_mx_edi_pac_status", "=", "to_cancel"), ("id", "in", self.ids)]
        )
        records._l10n_mx_edi_call_service("cancel")

    def _get_valid_certificate(self):
        """Get the valid certificate of the company"""
        company_id = self.company_id or self.contract_id.company_id
        certificate = company_id.sudo().l10n_mx_edi_certificate_ids.filtered(
            "is_valid"
        )[:1]
        return certificate

    # -------------------------------------------------------------------------
    # Payslip methods
    # -------------------------------------------------------------------------

    def l10n_mx_edi_action_request_edi_cancel(self):
        to_cancel = self.filtered(
            lambda r: r.state == "done"
            and r.l10n_mx_edi_pac_status == "signed"
            and r.l10n_mx_edi_is_required()
        )
        # Ensure that cancellation case is defined
        if to_cancel.filtered(lambda p: not p.l10n_mx_edi_cancellation):
            raise UserError(
                self.env._(
                    "In order to allow cancel, please define the cancellation case."
                )
            )
        if to_cancel.filtered(
            lambda p: p.l10n_mx_edi_cancellation.split("|")[0]
            not in ["01", "02", "03", "04"]
        ):
            raise UserError(
                self.env._(
                    "In order to allow cancel, please define a correct cancellation case."
                )
            )
        if to_cancel.mapped("move_id").filtered("posted_before"):
            raise UserError(
                self.env._(
                    "You have selected payslips whose journal entries are already validated or that were "
                    "validated. These payslips cannot be canceled, if you need to cancel just the CFDI, "
                    "please contact your administrator."
                )
            )
        to_cancel.write({"l10n_mx_edi_pac_status": "to_cancel"})
        to_cancel.filtered(
            lambda p: p.l10n_mx_edi_cancellation.split("|")[0] == "01"
        ).action_payslip_cancel()

    def _get_to_not_link_loans(self):
        """Add Payslip to loans when the payslip is validated"""
        # OVERRIDE
        self.ensure_one()
        if not self.l10n_mx_edi_is_required:
            return super()._get_to_not_link_loans()
        to_not_link_loans = self.env["hr.employee.loan"]
        loans = self.get_loans("all")
        # Ignore Company loans if there is not salary rule of it
        present_rules = self.mapped("line_ids.salary_rule_id")
        company_rule = self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_004_loan_company"
        )
        company_rule_bf = self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_004_loan_company_bf"
        )

        # TODO: Make this part more generic to include other types of loans
        if not (company_rule in present_rules or company_rule_bf in present_rules):
            input_types = [
                self.env.ref(
                    "l10n_mx_edi_payslip.hr_payslip_input_type_deduction_004_loan_company"
                ),
            ]

            to_not_link_loans |= loans.filtered(
                lambda loan: loan.input_type_id in input_types
            )

        return to_not_link_loans

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        # Adding payslip lines to account.move.line
        account_id = self._get_department_account(line, account_id)
        line_values = super()._prepare_line_values(
            line, account_id, date, debit, credit
        )
        line_values["l10n_mx_edi_payslip_line_ids"] = [Command.set(line.ids)]
        return line_values

    def _get_existing_lines(self, line_ids, line, account_id, debit, credit):
        if (
            line.slip_id.company_id.l10n_mx_edi_not_global_entry
            or not line.salary_rule_id.l10n_mx_group_entry
        ):
            return False
        account_id = self._get_department_account(line, account_id)
        existing_lines = super()._get_existing_lines(
            line_ids, line, account_id, debit, credit
        )
        first_line = next(existing_lines, False)
        if first_line:
            remaining_lines = list(existing_lines)
            existing_lines = [first_line] + remaining_lines
            existing_lines[0]["l10n_mx_edi_payslip_line_ids"][0][2].append(line.id)
        return existing_lines

    @api.model
    def _get_department_account(self, line, account_id):
        """Sets the department account, according departments fiscal position
        Get the same account if there is not fiscal position"""

        def _get_final_department(department):
            if not department.parent_id:
                return department
            return _get_final_department(department.parent_id)

        department = line.contract_id.department_id
        department = _get_final_department(department)
        fiscal_position = department.property_account_position_id
        if not fiscal_position:
            return account_id
        actual_account_id = self.env["account.account"].browse(account_id)
        return fiscal_position.map_account(actual_account_id).id

    def _l10n_mx_edi_retry(self):
        """Try to generate the CFDI attachment that will be signed by FINKOK."""
        for record in self:
            record.l10n_mx_edi_error = False
            cfdi_values = record._l10n_mx_edi_create_cfdi()
            error = cfdi_values.pop("error", None)
            if error:
                record.l10n_mx_edi_pac_status = "retry"
                record.l10n_mx_edi_log_error(error)
                continue
            # cfdi has been successfully generated
            record.l10n_mx_edi_pac_status = "to_sign"

            is_xml_signed = self._l10n_mx_edi_verify_or_update_cfdi(cfdi_values)
            cfdi = cfdi_values.pop("cfdi", None)
            ctx = self.env.context.copy()
            ctx.pop("default_type", False)

            attach_id = record.l10n_mx_edi_retrieve_last_attachment()
            if not attach_id:
                attach_id = (
                    self.env["ir.attachment"]
                    .with_context(**ctx)
                    .create(
                        {
                            "name": record.l10n_mx_edi_cfdi_name,
                            "res_id": record.id,
                            "res_model": record._name,
                            "datas": base64.encodebytes(cfdi),
                            "description": "Mexican payroll",
                        }
                    )
                )
                record.message_post(
                    body=self.env._("CFDI document generated (may be not signed)"),
                    attachment_ids=[attach_id.id],
                )
            else:
                attach_id.write(
                    {"datas": base64.encodebytes(cfdi), "mimetype": "application/xml"}
                )
            if not is_xml_signed:
                record._l10n_mx_edi_sign()

    @api.model
    def l10n_mx_edi_retrieve_attachments(self):
        """Retrieve all the CFDI attachments generated for this payroll.
        Returns:
            recordset: An ir.attachment recordset"""
        self.ensure_one()
        if not self.l10n_mx_edi_cfdi_name:
            return []
        domain = [
            ("res_id", "=", self.id),
            ("res_model", "=", self._name),
            ("name", "=", self.l10n_mx_edi_cfdi_name),
        ]
        return self.env["ir.attachment"].search(domain)

    @api.model
    def l10n_mx_edi_retrieve_last_attachment(self):
        attachment_ids = self.l10n_mx_edi_retrieve_attachments()
        return attachment_ids[0] if attachment_ids else None

    @api.model
    def l10n_mx_edi_get_xml_etree(self, cfdi=None):
        """Get an objectified tree representing the cfdi.
        If the cfdi is not specified, retrieve it from the attachment.
        :param str cfdi: The cfdi as string
        :type: str
        :return: An objectified tree
        :rtype: objectified"""
        # TODO helper which is not of too much help and should be removed
        self.ensure_one()
        if cfdi is None:
            cfdi = self.l10n_mx_edi_cfdi
        return objectify.fromstring(cfdi)

    @staticmethod
    def _l10n_mx_get_serie_and_folio(number):
        # TODO - Same method on invoice
        values = {"serie": None, "folio": None}
        number_matchs = list(re.finditer(r"\d+", number or ""))
        if number_matchs:
            last_number_match = number_matchs[-1]
            values["serie"] = number[: last_number_match.start()] or None
            values["folio"] = last_number_match.group().lstrip("0") or None
        return values

    @staticmethod
    def _get_string_cfdi(text, size=100):
        """Replace from text received the characters that are not found in the
        regex. This regex is taken from SAT documentation
        https://goo.gl/C9sKH6
        text: Text to remove extra characters
        size: Cut the string in size len
        Ex. 'Product ABC (small size)' - 'Product ABC small size'"""
        if not text:
            return None
        text = text.replace("|", " ")
        return text.strip()[:size]

    def _l10n_mx_edi_create_cfdi_values(self):
        """Create the values to fill the CFDI template."""
        self.ensure_one()
        payroll = self._l10n_mx_edi_create_payslip_values()
        if payroll.get("error", False):
            return payroll
        subtotal = payroll["total_other"] + payroll["total_perceptions"]
        deduction = payroll["total_deductions"]
        company = self.company_id or self.contract_id.company_id
        employee = self.employee_id
        if employee.private_country_id and employee.private_country_id.code != "MX":
            customer_rfc = "XEXX010101000"
        elif employee.l10n_mx_rfc:
            customer_rfc = employee.l10n_mx_rfc.strip()
        elif employee.private_country_id.code in (False, "MX"):
            customer_rfc = "XAXX010101000"
        else:
            customer_rfc = "XEXX010101000"
        values = {
            "record": self,
            "supplier": company.partner_id.commercial_partner_id,
            "amount_untaxed": "%.2f" % abs(subtotal or 0.0),
            "amount_discount": "%.2f" % abs(deduction or 0.0),
            "taxes": {},
            "outsourcing": [],  # TODO - How set the outsourcing?
            "customer_rfc": customer_rfc,
        }

        # values.update(self._l10n_mx_get_serie_and_folio(self.number))

        values.update(payroll)
        return values

    def _l10n_mx_edi_create_payslip_values(self):
        self.ensure_one()
        employee = self.employee_id
        if not self.contract_id:
            return {"error": self.env._("Employee has not a contract and is required")}
        seniority = self.contract_id.get_seniority(date_to=self.date_to)["days"] / 7
        perceptions_data = self.get_cfdi_perceptions_data()
        payroll = {
            "record": self,
            "company": self.company_id or self.contract_id.company_id,
            "employee": self.employee_id,
            "payslip_type": self.struct_id.type_id.l10n_mx_edi_type or "O",
            "number_of_days": int(
                sum(self.worked_days_line_ids.mapped("number_of_days"))
            ),
            "date_start": self.contract_id.date_start,
            "seniority_emp": "P%sW" % int(seniority),
            "is_settlement": bool(perceptions_data["total_compensation"]),
            "force_other_payments": self._l10n_mx_edi_force_other_payments(),
            "acc_number": self.employee_id.sudo().bank_account_id.acc_number,
        }
        payroll.update(employee.get_cfdi_employee_data(self.contract_id))
        payroll.update(perceptions_data)
        payroll.update(self.get_cfdi_deductions_data())
        payroll.update(self.get_cfdi_other_payments_data())
        payroll["inability_data"] = lambda i, p: p._get_inability_data(i)
        return payroll

    def _l10n_mx_edi_force_other_payments(self):
        """Return True if the other payments node must be added"""
        if self.struct_id == self.env.ref(
            "l10n_mx_edi_payslip.payroll_structure_data_04", False
        ):
            return False
        if self.employee_id.l10n_mx_edi_contract_regime_type == "02":
            return True
        return False

    @api.model
    def _l10n_mx_edi_get_isr_rules(self):
        """This method returns a 'hr.salary.rule' recordset with the ISR salary rules.
        Method mainly used for the ISR salary rules themself, to get know how much the employee
        has been paid of ISR in the payslips of the month.
        """
        rules = self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_isr"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_002_bf"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_finiquito_002_bf"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_002_ptu"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_finiquito_002_04"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_finiquito_002"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_aguinaldo_002"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_isr_bonus"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_isr_174"
        )
        rules |= self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_isr_174_bf"
        )
        return rules

    def get_cfdi_perceptions_data(self):
        categ_g = self.env.ref(
            "l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_taxed"
        )
        categ_e = self.env.ref(
            "l10n_mx_edi_payslip.hr_salary_rule_category_perception_mx_exempt"
        )
        perceptions = self.line_ids.filtered(
            lambda r: r.category_id in [categ_g, categ_e] and r.total
        )
        total_taxed = round(
            sum(
                perceptions.filtered(lambda r: r.category_id == categ_g).mapped("total")
            ),
            2,
        )
        total_exempt = round(
            sum(
                perceptions.filtered(lambda r: r.category_id == categ_e).mapped("total")
            ),
            2,
        )
        total_salaries = round(
            sum(
                perceptions.filtered(
                    lambda r: r.salary_rule_id.l10n_mx_edi_code
                    not in ["022", "023", "025", "039", "044"]
                ).mapped("total")
            ),
            2,
        )
        total_compensation = round(
            sum(
                perceptions.filtered(
                    lambda r: r.salary_rule_id.l10n_mx_edi_code in ["022", "023", "025"]
                ).mapped("total")
            ),
            2,
        )
        total_retirement = sum(
            perceptions.filtered(
                lambda r: r.salary_rule_id.l10n_mx_edi_code in ["039", "044"]
            ).mapped("total")
        )
        values = {
            "total_salaries": total_salaries,
            "total_compensation": total_compensation,
            "total_retirement": total_retirement,
            "total_taxed": total_taxed,
            "total_exempt": total_exempt,
            "total_perceptions": (
                total_salaries + total_compensation + total_retirement
            ),
            "category_taxed": categ_g,
            "category_exempt": categ_e,
            "perceptions": perceptions,
        }
        # if the payslip contains only bonus or separation payments,
        # it is of Type "E"
        if perceptions.filtered(
            lambda r: r.salary_rule_id.l10n_mx_edi_code in ["002", "023"]
        ) and not perceptions.filtered(
            lambda r: r.salary_rule_id.l10n_mx_edi_code in ["001"]
        ):
            values.update(
                {
                    "payslip_type": "E",
                }
            )
        return values

    def get_cfdi_deductions_data(self):
        categ = self.env.ref("hr_payroll.DED")
        deductions = self.line_ids.filtered(
            lambda r: r.category_id == categ and r.amount
        )
        total = sum(deductions.mapped("total"))
        total_other = sum(
            deductions.filtered(
                lambda r: r.salary_rule_id.l10n_mx_edi_code != "002"
            ).mapped("total")
        )
        total_withheld = sum(
            deductions.filtered(
                lambda r: r.salary_rule_id.l10n_mx_edi_code == "002"
            ).mapped("total")
        )
        return {
            "total_deductions": abs(total),
            "total_other_deductions": abs(total_other),
            "total_taxes_withheld": (
                "%.2f" % abs(total_withheld) if total_withheld else None
            ),  # noqa
            "deductions": deductions,
        }

    def _get_inability_data(self, line):
        # Incapacidad Riesgo de Trabajo
        if line.salary_rule_id in self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006_irt"
        ) | self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006_irt_bf"
        ):
            days = sum(
                self.worked_days_line_ids.filtered(
                    lambda w: w.code == "LEAVE112"
                ).mapped("number_of_days")
            )
            return {"days": days, "inability_type": "01"}
        # Incapacidad Enfermedad General
        if line.salary_rule_id in self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006"
        ) | self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006_bf"
        ):
            days = sum(
                self.worked_days_line_ids.filtered(
                    lambda w: w.code == "LEAVE110"
                ).mapped("number_of_days")
            )
            return {"days": days, "inability_type": "02"}
        # Incapacidad Maternidad
        if line.salary_rule_id in self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006_im"
        ) | self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006_im_bf"
        ):
            days = sum(
                self.worked_days_line_ids.filtered(
                    lambda w: w.code == "LEAVE111"
                ).mapped("number_of_days")
            )
            return {"days": days, "inability_type": "03"}
        # Licencia para Padres con Hijos con Cancer
        if line.salary_rule_id in self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006_lphc"
        ) | self.env.ref(
            "l10n_mx_edi_payslip.hr_rule_l10n_mx_payroll_deduction_006_lphc_bf"
        ):
            days = sum(
                self.worked_days_line_ids.filtered(
                    lambda w: w.code == "LEAVE113"
                ).mapped("number_of_days")
            )
            return {"days": days, "inability_type": "04"}
        return {"days": 0, "inability_type": ""}

    def get_cfdi_other_payments_data(self):
        """Records with category Other Payments are used in the node
        "OtrosPagos"."""
        categ = self.env.ref("l10n_mx_edi_payslip.hr_salary_rule_category_other_mx")
        other_payments = self.line_ids.filtered(
            lambda line: line.category_id == categ
            and (line.amount or line.salary_rule_id.l10n_mx_edi_code == "002")
        )
        return {
            "total_other": abs(sum(other_payments.mapped("total"))),
            "other_payments": other_payments,
        }

    def _l10n_mx_edi_create_cfdi(self):
        """Creates and returns a dictionary containing 'cfdi' if the cfdi is
        well created, 'error' otherwise."""
        self.ensure_one()
        qweb = self.env["ir.qweb"]
        error_log = []
        company_id = self.company_id or self.contract_id.company_id
        pac_name = company_id.l10n_mx_edi_pac
        values = self._l10n_mx_edi_create_cfdi_values()
        self.l10n_mx_edi_error_count = 0

        # -----------------------
        # Check the configuration
        # -----------------------
        # - Check not errors in values generation
        if values.get("error"):
            error_log.append(values.get("error"))

        # - Check certificate
        certificate = self._get_valid_certificate()
        if not certificate:
            error_log.append(self.env._("No valid certificate found."))

        # -Check PAC
        if pac_name:
            pac_test_env = company_id.sudo().l10n_mx_edi_pac_test_env
            pac_password = company_id.sudo().l10n_mx_edi_pac_password
            if not pac_test_env and not pac_password:
                error_log.append(self.env._("No PAC credentials specified."))
        else:
            error_log.append(self.env._("No PAC specified."))

        if error_log:
            self.l10n_mx_edi_error_count = len(error_log)
            return {
                "error": self.env._("Please check your configuration: ")
                + create_list_html(error_log)
            }

        # -----------------------
        # Create the EDI document
        # -----------------------

        # - Compute certificate data
        time_payslip = datetime.strptime(
            self.l10n_mx_edi_time_payslip, DEFAULT_SERVER_TIME_FORMAT
        ).time()
        values.update(
            {
                "date": datetime.combine(
                    fields.Datetime.from_string(self.l10n_mx_edi_expedition_date),
                    time_payslip,
                ).strftime("%Y-%m-%dT%H:%M:%S"),
                "certificate_number": ("%x" % int(certificate.serial_number))[1::2],
                "certificate": certificate.sudo()
                ._get_der_certificate_bytes(formatting="base64")
                .decode(),
            }
        )

        # - Compute cfdi
        template = PAYSLIP_TEMPLATE_40
        xslt = CFDI_XSLT_CADENA_40
        cfdi = qweb._render(template, values=values)

        # - Compute cadena
        tree = self.l10n_mx_edi_get_xml_etree(cfdi)
        cadena = self.l10n_mx_edi_generate_cadena(xslt, tree)

        # Post append cadena
        tree.attrib["Sello"] = certificate.sudo()._sign(cadena, formatting="base64")

        # Check with xsd
        attachment = self.env.ref("l10n_mx_edi.xsd_cached_cfdv40_xsd", False)
        xsd_datas = base64.b64decode(attachment.datas) if attachment else b""
        if xsd_datas:
            try:
                with BytesIO(xsd_datas) as xsd:
                    _check_with_xsd(tree, xsd)
            except (OSError, ValueError):
                _logger.info(
                    "The xsd file to validate the XML structure was not found."
                )
            except BaseException as e:
                return {
                    "error": (
                        self.env._("The cfdi generated is not valid")
                        + create_list_html(str(e).split("\\n"))
                    )
                }

        return {
            "cfdi": etree.tostring(
                tree, pretty_print=True, xml_declaration=True, encoding="UTF-8"
            )
        }

    def l10n_mx_edi_update_pac_status(self):
        """Synchronize both systems: Odoo & PAC if the payrolls need to be
        signed or cancelled."""
        for record in self.filtered(lambda r: r.l10n_mx_edi_is_required()):
            if record.l10n_mx_edi_pac_status in ("to_sign", "retry"):
                record._l10n_mx_edi_retry()
            elif record.l10n_mx_edi_pac_status == "to_cancel":
                record._l10n_mx_edi_cancel()

    def l10n_mx_edi_update_sat_status(self):
        """Synchronize both systems: Odoo & SAT to make sure the payroll is
        valid."""
        for record in self:
            if record.l10n_mx_edi_pac_status not in ["signed", "cancelled"]:
                continue
            supplier_rfc = record.l10n_mx_edi_cfdi_supplier_rfc
            customer_rfc = record.l10n_mx_edi_cfdi_customer_rfc
            total = record.l10n_mx_edi_cfdi_amount
            uuid = record.l10n_mx_edi_cfdi_uuid
            status = self.env["l10n_mx_edi.document"]._fetch_sat_status(
                supplier_rfc, customer_rfc, total, uuid
            )
            record.l10n_mx_edi_sat_status = status["value"]

    def _get_worked_day_lines(self, domain=None, check_out_of_contract=True):
        """Overwrite WORK100 to get all days in the period"""
        result = super()._get_worked_day_lines(
            domain=domain, check_out_of_contract=check_out_of_contract
        )
        result = self._set_leaves_calendar_days_count(result)
        hours_per_day = (
            result[0]["number_of_hours"] / result[0]["number_of_days"]
            if result and result[0]["number_of_days"]
            else 0
        )
        total = sum(line["number_of_days"] for line in result)
        work_entry = self.env.ref("hr_work_entry.work_entry_type_attendance")
        out_contract = self.env.ref("hr_payroll.hr_work_entry_type_out_of_contract")
        date_from = max(self.date_from, self.contract_id.date_start)
        days = self.contract_id.get_seniority(date_from, self.date_to, "a")["days"]
        days_out_start, days_out_end = self._get_out_of_contract_days()
        total -= sum(
            line["number_of_days"]
            for line in result
            if line["work_entry_type_id"] == out_contract.id
        )
        absences = 0
        if self.employee_id.l10n_mx_edi_force_attendances:
            absences = self._get_absences()
        # Adjust Attendances
        for line in result:
            if line["work_entry_type_id"] == work_entry.id:
                line["number_of_days"] = (
                    line["number_of_days"] + days - total - days_out_end - absences
                )

        # Include Absences
        if absences:
            absence_entry = self.env.ref(
                "l10n_mx_edi_payslip.work_entry_type_absence_l10n_mx_payroll"
            )
            vals = {
                "sequence": absence_entry.sequence,
                "work_entry_type_id": absence_entry.id,
                "number_of_days": absences,
                "number_of_hours": hours_per_day * absences,
            }
            result.append(vals)

        # Include Out of contract line
        out_of_contract_days = days_out_start + days_out_end
        if out_of_contract_days:
            out_contract_line = [
                line for line in result if line["work_entry_type_id"] == out_contract.id
            ]
            vals = {
                "sequence": out_contract.sequence,
                "work_entry_type_id": out_contract.id,
                "number_of_days": out_of_contract_days,
                "number_of_hours": hours_per_day * out_of_contract_days,
            }
            if out_contract_line:
                out_contract_line[0].update(vals)
            else:
                result.append(vals)

        # Check there are all days in the period, refill with attendences if not
        payslip_period_days = (self.date_to - self.date_from).days + 1
        worked_days = sum(line["number_of_days"] for line in result)
        if worked_days < payslip_period_days and result:
            days = payslip_period_days - worked_days
            result.append(
                {
                    "sequence": work_entry.sequence,
                    "work_entry_type_id": work_entry.id,
                    "number_of_days": days,
                    "number_of_hours": hours_per_day * days,
                }
            )

        return result

    def _get_absences(self):
        """Return the days that the employee have not attendance and is required"""
        self.ensure_one()
        tz = pytz_timezone(self.employee_id.tz or self.env.user.tz)
        dt_from = max(self.date_from, self.contract_id.date_start)
        date_from = datetime.combine(dt_from, dt_time(0, 0), tz)
        date_to = datetime.combine(self.date_to, dt_time(23, 59, 59), tz)
        resources = self.contract_id.resource_calendar_id._get_resources_day_total(
            date_from, date_to
        )[False]
        absences = 0
        for day in range((self.date_to - dt_from).days + 1):
            date = dt_from + timedelta(days=day)
            if date not in resources:
                continue
            if self.employee_id.attendance_ids.filtered(
                lambda a: a.check_in.date() == date
            ):
                continue
            # Used SUPERUSER_ID to forcefully get status of other user's leave, to bypass record rule
            if (
                self.env["hr.leave"]
                .sudo()
                .search(
                    [
                        ("employee_id", "=", self.employee_id.id),
                        ("date_from", "<=", date),
                        ("date_to", ">=", date),
                        ("state", "not in", ("cancel", "refuse")),
                    ]
                )
            ):
                continue
            absences += 1
        # TODO: Improve to return the number of hours
        return absences

    def _get_out_of_contract_days(self):
        """If the contract doesn't cover the whole payslip period, get how many days are out of contract period"""
        contract = self.contract_id
        if not contract:
            return 0, 0
        days_out_start = (
            (contract.date_start - self.date_from).days
            if contract.date_start > self.date_from
            else 0
        )
        days_out_end = (
            0
            if not contract.date_end or contract.date_end >= self.date_to
            else (self.date_to - contract.date_end).days
        )
        return days_out_start, days_out_end

    def _set_leaves_calendar_days_count(self, worked_day_lines):
        """This method sets on the worked_day_lines the missing days that are out of normal employee's work schedule
        in the period of hr.leaves that uses calendar days

        - Get which days the employee does not work being 0 Monday and 6 Sunday
        - Get week days that normally the employee does not work
        - Get the specific dates when the employee does not work in the payslip period
        - for each date, search if there is at least one hr.leave that:
            Uses calendar days
            The date is between leave period
            Is for the payslip employee
        If there is at least one, count a day, save the count grouping by hr.leave hr.work.entry.type
        - For each group, check in worked_day_lines. If there is a dict with work_entry_type_id set,
        add the days count to its number_of_days and number_of_hours. If not, create a new dict in the
        worked_day_lines list to create a new worked day on the payslip.
        """
        work_days = self.contract_id.resource_calendar_id.attendance_ids.mapped(
            "dayofweek"
        )
        not_work_days = list({"0", "1", "2", "3", "4", "5", "6"} - set(work_days))

        leave_days = {}
        for day in range((self.date_to - self.date_from).days + 1):
            date = self.date_from + timedelta(days=day)
            if str(date.weekday()) not in not_work_days:
                continue
            leave = self.env["hr.leave"].search(
                [
                    (
                        "holiday_status_id.l10n_mx_edi_payslip_use_calendar_days",
                        "=",
                        True,
                    ),
                    ("employee_id", "=", self.employee_id.id),
                    ("state", "=", "validate"),
                    ("request_date_from", "<=", date),
                    ("request_date_to", ">=", date),
                ],
                limit=1,
            )
            if not leave:
                continue
            # Use entry type as key and count as value
            # If the entry type is already set, sum 1, if not set the count as 1
            entry_type_id = leave.holiday_status_id.work_entry_type_id.id
            leave_days[entry_type_id] = (
                leave_days[entry_type_id] + 1 if leave_days.get(entry_type_id) else 1
            )

        # Add the work entry type and count to the result/worked_day_lines dict
        for work_entry_type, days_count in leave_days.items():
            is_entry_set = False
            for line in worked_day_lines:
                if line["work_entry_type_id"] == work_entry_type:
                    line["number_of_days"] = line["number_of_days"] + days_count
                    line["number_of_hours"] = line["number_of_hours"] + days_count * 8
                    is_entry_set = True
                    break

            if is_entry_set:
                continue
            worked_day_lines.append(
                {
                    "sequence": 25,
                    "work_entry_type_id": work_entry_type,
                    "number_of_days": days_count,
                    "number_of_hours": 8.0 * days_count,
                }
            )
        return worked_day_lines

    def l10n_mx_edi_is_last_payslip(self):
        """Determine whether the current payslip is the last of the month.

        This method evaluates several conditions to identify if a payslip should
        be considered the last one of the month:

        1. If the `date_to` field matches the last day of the month (biweekly case).
        2. If the range of days in the payslip results in a projection (`next_date`)
        that falls in the next month. This accounts for irregular or overlapping
        periods.
        3. If the `date_to` field matches the `date_end` of the associated contract,
        indicating a contract termination (final payslip).

        Returns:
            bool: True if the payslip meets any of the above conditions,
                indicating it is the last payslip of the month; False otherwise.
        """
        if not self:
            return False
        self.ensure_one()
        if not self.date_to:
            return False
        if self.date_to.day == monthrange(self.date_to.year, self.date_to.month)[1]:
            return True
        dbtw = abs((self.date_to - self.date_from).days) + 1
        next_date = self.date_to + timedelta(days=dbtw)
        if self.date_from.month not in (self.date_to.month, next_date.month):
            return True
        if self.contract_id.date_end and self.date_to == self.contract_id.date_end:
            return True
        return False

    def l10n_mx_edi_name(self, payslip_line):
        self.ensure_one()
        if not self.company_id.l10n_mx_edi_dynamic_name:
            return payslip_line.name
        # Getting salary rule code on input code form, to know if this payslip line has input lines.
        code = payslip_line.salary_rule_id.code
        code = "%s_%s" % (code[:2].lower(), code[2:])
        inputs = self.input_line_ids.filtered(lambda line, code=code: line.code == code)

        if not inputs:
            return payslip_line.name

        details = self.env["hr.payslip.extra.detail"].search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("extra_id.state", "=", "approved"),
                ("extra_id.date", ">=", self.date_from),
                ("extra_id.date", "<=", self.date_to),
                ("extra_id.input_id", "in", inputs.input_type_id.ids),
            ]
        )
        if details and details.filtered("name"):
            return "%s: %s" % (payslip_line.name, ", ".join(details.mapped("name")))

        return payslip_line.name

    def l10n_mx_edi_update_extras(self):
        """Update the extra inputs defined for the employees"""
        if not self:
            return False
        extras = self.env["hr.payslip.extra"].search(
            [
                ("state", "=", "approved"),
                (
                    "date",
                    "=",
                    self.mapped("payslip_run_id").l10n_mx_edi_payment_date
                    or self[0].l10n_mx_edi_payment_date,
                ),
            ]
        )
        for slip in self.filtered("contract_id"):
            slip_extras = extras.mapped("detail_ids").filtered(
                lambda e: e.employee_id == slip.employee_id and e.amount
            )
            slip.input_line_ids.filtered(
                lambda line: line.code in slip_extras.mapped("extra_id.input_id.code")
            ).unlink()
            for extra, _records in groupby(slip_extras, lambda r: r.extra_id):
                slip.input_line_ids = [
                    Command.create(
                        {
                            "amount": sum(
                                slip_extras.filtered(
                                    lambda e: e.extra_id == extra
                                ).mapped("amount")
                            ),
                            "code": extra.input_id.code,
                            "contract_id": slip.contract_id.id,
                            "input_type_id": extra.input_id.id,
                        },
                    )
                ]
            slip.compute_sheet()
        return True

    def _get_inability_bonus(self, only_days=False):
        """If only_days, return the leave days that must be paid in this payslip as inability"""
        contract = self.contract_id
        leave = self.env.ref("hr_work_entry_contract.work_entry_type_sick_leave")
        domain = [("work_entry_type_id", "=", leave.id)]
        work_entry = self.env["hr.work.entry"].search(
            contract._get_work_hours_domain(
                self.date_from, self.date_to, domain=domain, inside=True
            )
        )
        result = 0
        for leave in work_entry.mapped("leave_id"):
            days = number_of_days = 0
            for day in range(
                3 if leave.number_of_days >= 3 else int(leave.number_of_days)
            ):
                if (
                    leave.date_from + timedelta(days=day)
                ).date() >= self.date_from and (
                    leave.date_from + timedelta(days=day)
                ).date() <= self.date_to:
                    days += 1
            if only_days:
                return days
            for day in range((self.date_to - self.date_from).days + 1):
                date = self.date_from + timedelta(days=day)
                if leave.date_from.date() <= date <= leave.date_to.date():
                    number_of_days += 1
            if number_of_days > days > 3:
                result += (
                    contract.l10n_mx_edi_daily_wage - (contract.l10n_mx_edi_sbc * 0.60)
                ) * (number_of_days - days)
        return result

    def _get_dates_on_datetime(self, timezone=None):
        """Cast payslips dates to datetime considering time zone. Used to compare dates on salary rules."""
        tz = timezone or pytz_timezone(self.employee_id.tz or self.env.user.tz)
        # Creating dates with Timezone, 'imitating' odoo behavior.
        date_from = datetime.combine(self.date_from, dt_time(0, 0), tz)
        date_to = datetime.combine(self.date_to, dt_time(23, 59, 59), tz)
        # Storing datetime equivalent in UTC. 'Imitating' odoo
        date_from = date_from.astimezone()
        date_to = date_to.astimezone()
        # Removing tzinfo. datetime with tzinfo can't be used to compare, the values are not affected.
        date_from = date_from.replace(tzinfo=None)
        date_to = date_to.replace(tzinfo=None)
        return date_from, date_to

    def _get_attendances(self):
        """Get the attendances of the employee in the period of payslip,
        return Attendances where check_in is between payslips dates, date_from and date_to
        Using the employee timezone or user timezone
        If the module Attendances is not installed return an empty list."""
        if not self:
            return []
        # Cast payslip dates to datetime to be available to compare on the filtered
        date_from, date_to = self._get_dates_on_datetime()
        attendances = self.employee_id.attendance_ids.filtered(
            lambda att: att.check_in >= date_from and att.check_in <= date_to
        )
        return attendances

    def _get_attendances_weekdays(self):
        """Get a list of worked days gotten from attendances
        Days converted considering timezone
        return weekdays represented by int. Monday as 0, sunday as 6.
        If the module Attendances is not installed return an empty list."""
        attendances = self._get_attendances()
        tz = pytz_timezone(self.employee_id.tz or self.env.user.tz)
        days = []
        for attendance in attendances:
            date = attendance.check_in.astimezone(tz)
            days.append(date.weekday())
        return days

    def auto_generate_overtimes(self):
        overtime = self.env["hr.payslip.overtime"]
        for record in self:
            for day in range((record.date_to - record.date_from).days + 1):
                date = record.date_from + timedelta(days=day)
                if overtime.search_count(
                    [("name", "=", date), ("employee_id", "=", record.employee_id.id)]
                ):
                    continue
                overtime.create(
                    {
                        "name": record.date_from + timedelta(days=day),
                        "employee_id": record.employee_id.id,
                    }
                )

    def get_overtime_data(self, is_simple=False):
        """Get the overtimes for the salary rule, if receive is_simple will to search the overtimes with that check"""
        self.ensure_one()
        overtimes = self.env["hr.payslip.overtime"].search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("name", ">=", self.date_from),
                ("name", "<=", self.date_to),
                ("hours", "!=", 0),
                ("is_simple", "=", is_simple),
            ]
        )
        if not overtimes:
            return {}
        detail = {}
        weeks_overtimes = overtimes.search(
            [
                ("employee_id", "=", self.employee_id.id),
                ("week", "in", overtimes.mapped("week")),
                ("hours", "!=", 0),
                ("name", ">=", self.date_from - timedelta(days=7)),
                ("name", "<=", self.date_to + timedelta(days=7)),
            ]
        )
        for overtime in weeks_overtimes.sorted("name"):
            if overtime.week not in detail:
                detail[overtime.week] = {
                    "paid": 0,
                    "no_paid": 0,
                    "triple_paid": 0,
                    "triple_no_paid": 0,
                }
            if overtime.id not in overtimes.ids:
                detail[overtime.week]["paid"] += (
                    overtime.hours if (overtime.hours <= 3 or is_simple) else 3
                )
                detail[overtime.week]["triple_paid"] += (
                    overtime.hours - 3 if (overtime.hours > 3 and not is_simple) else 0
                )
                continue

            detail[overtime.week]["no_paid"] += (
                overtime.hours if (overtime.hours <= 3 or is_simple) else 3
            )
            detail[overtime.week]["triple_no_paid"] += (
                overtime.hours - 3 if (overtime.hours > 3 and not is_simple) else 0
            )
        return detail

    def _l10n_mx_edi_sat_synchronously(self, batch_size=10):
        """Update the SAT status synchronously
        This method Calls :meth:`~.l10n_mx_edi_update_sat_status` by batches,
        ensuring changes are committed after processing each batch. This is
        intended to be able to process a lot of records on a safely manner,
        avoiding a possible sistematic failure withoud any invoice updated.
        This is especially useful when running crons.
        :param batch_size: the number of invoices to process by batch
        :type batch_size: int
        """
        for idx in range(0, len(self), batch_size):
            with self.env.cr.savepoint():
                self[idx : idx + batch_size].l10n_mx_edi_update_sat_status()

    @api.model
    def l10n_mx_edi_get_pac_version(self):
        """Returns the cfdi version to generate the CFDI."""
        return (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("l10n_mx_edi_payroll_version", "4.0")
        )

    def _l10n_mx_edi_verify_or_update_cfdi(self, cfdi_values):
        """Checks the expedition date of the CFDI and verifies if the CFDI has been previously signed.

        :param cfdi_values: XML with current with the data of the payslip
        :type cfdi_values: dict
        :return: boolean that indicates if the expedition date has been updated

        This method takes into account the following:
        - Verify if the expedition date has been updated.
        - Verify if the CFDI created has not been previously signed to avoid
          trying to sign it again.
        """
        if not self._l10n_mx_edi_update_expedition_date():
            return False

        is_xml_signed = self._l10n_mx_edi_finkok_verify_is_stamped(cfdi_values)
        if not is_xml_signed:
            cfdi_values["cfdi"] = self._l10n_mx_edi_create_cfdi()["cfdi"]
            return False
        return True

    def _l10n_mx_edi_update_expedition_date(self):
        """Updates the date and time of the CFDI expedition if current
        expedition date is out of stamping period.

        Consider the payment date as the expedition date only if it is within
        the stamping period allowed by Finkok (72 hours).

        This method takes into account the following:
        - Get the current date and time to verify the stamping period and use them by default
          if it is necessary.
        - Use the payment date and current time if it is within the stamping period allowed.
        - Use the payment date and the last time of day to extend the stamp period.
        - If the expedition date has been computed, verify if the date is still in the stamping
          period and keep the computed values if they are valid.
        """
        company = self.company_id or self.contract_id.company_id
        time_zone = (
            company.partner_id.commercial_partner_id._l10n_mx_edi_get_cfdi_timezone()
        )
        date_time_mx = datetime.now(time_zone)
        date_in_range = self.l10n_mx_edi_payment_date + timedelta(days=3)
        time_mx = date_time_mx.time()
        l10n_mx_edi_expedition_date = date_time_mx.date()
        l10n_mx_edi_time_payslip = time_mx.strftime(DEFAULT_SERVER_TIME_FORMAT)
        date_time_mx = datetime.strftime(
            date_time_mx, DEFAULT_SERVER_DATETIME_FORMAT
        )

        if not self.l10n_mx_edi_expedition_date:
            if self.l10n_mx_edi_payment_date > l10n_mx_edi_expedition_date:
                self.l10n_mx_edi_expedition_date = l10n_mx_edi_expedition_date
                self.l10n_mx_edi_time_payslip = l10n_mx_edi_time_payslip
                return False
            if l10n_mx_edi_expedition_date.month > self.l10n_mx_edi_payment_date.month:
                l10n_mx_edi_expedition_date = fields.Date.from_string(
                    "%s-%s-01"
                    % (
                        l10n_mx_edi_expedition_date.year,
                        l10n_mx_edi_expedition_date.month,
                    )
                ) - timedelta(days=1)
                l10n_mx_edi_time_payslip = "23:59:00"
            elif date_time_mx < datetime.strftime(
                datetime.combine(date_in_range, time_mx, time_zone),
                DEFAULT_SERVER_DATETIME_FORMAT,
            ):
                l10n_mx_edi_expedition_date = self.l10n_mx_edi_payment_date
            elif date_time_mx <= datetime.strftime(
                datetime.combine(
                    date_in_range,
                    datetime.strptime(
                        "23:59:00", DEFAULT_SERVER_TIME_FORMAT
                    ).time(),
                    time_zone,
                ),
                DEFAULT_SERVER_DATETIME_FORMAT,
            ):
                l10n_mx_edi_expedition_date = self.l10n_mx_edi_payment_date
                l10n_mx_edi_time_payslip = "23:59:00"
            self.l10n_mx_edi_expedition_date = l10n_mx_edi_expedition_date
            self.l10n_mx_edi_time_payslip = l10n_mx_edi_time_payslip
            return False

        date_in_range = self.l10n_mx_edi_expedition_date + timedelta(days=3)
        date_in_range = datetime.strftime(
            datetime.combine(
                date_in_range,
                datetime.strptime(
                    self.l10n_mx_edi_time_payslip, DEFAULT_SERVER_TIME_FORMAT
                ).time(),
                time_zone,
            ),
            DEFAULT_SERVER_DATETIME_FORMAT,
        )
        if date_time_mx > date_in_range:
            self.l10n_mx_edi_expedition_date = l10n_mx_edi_expedition_date
            self.l10n_mx_edi_time_payslip = l10n_mx_edi_time_payslip
            return True
        return False

    def _get_inability_days(self, leave):
        """Method to get the sum of the number of days from leaves into the payroll period."""
        contract = self.contract_id
        domain = [("work_entry_type_id", "=", leave.id)]
        work_entry = self.env["hr.work.entry"].search(
            contract._get_work_hours_domain(
                self.date_from, self.date_to, domain=domain, inside=True
            )
        )
        return sum(work_entry.mapped("leave_id.number_of_days"))
