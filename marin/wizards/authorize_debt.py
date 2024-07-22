from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class AuthorizeDebt(models.TransientModel):
    _name = "authorize.debt.wizard"
    _description = "Partner authorize debt wizard"

    company_id = fields.Many2one("res.company", compute="_compute_from_record_ids", store=True)
    company_currency_id = fields.Many2one("res.currency", related="company_id.currency_id")
    partner_id = fields.Many2one("res.partner", "Partner", compute="_compute_from_record_ids", store=True)
    flag = fields.Char(compute="_compute_from_record_ids", store=True)
    credit = fields.Monetary("Total receivable", "company_currency_id", related="partner_id.credit")
    credit_limit = fields.Float("Credit limit", related="partner_id.credit_limit")
    credit_limit_available = fields.Monetary(
        "Credit limit available", "company_currency_id", related="partner_id.credit_limit_available"
    )
    debt_request = fields.Monetary(
        "Exceeded debit amount", "company_currency_id", compute="_compute_from_record_ids", store=True
    )
    amount_authorize = fields.Monetary(
        "Amount", "company_currency_id", compute="_compute_from_record_ids", store=True, readonly=False
    )
    move_ids = fields.Many2many(
        "account.move",
        readonly=True,
        copy=False,
    )
    count_move = fields.Integer(compute="_compute_count_move")
    so_ids = fields.Many2many(
        "sale.order",
        string="Sale Orders",
        readonly=True,
        copy=False,
    )
    count_so = fields.Integer(compute="_compute_count_so")

    # pylint: disable=too-complex
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self._context.get("active_model")
        if active_model not in ["account.move", "sale.order"]:
            return res
        # if "move_ids" in fields_list and "move_ids" not in res:
        if active_model == "account.move":
            moves = self.env["account.move"].browse(self._context.get("active_ids", []))
            sanitized_moves = self.env["account.move"]
            for move in moves:
                if move.state != "draft":
                    raise UserError(_("You can only authorize debt for draft journal entries."))
                if move.move_type not in ("in_invoice", "out_invoice"):
                    continue
                if move.company_currency_id.is_zero(move.amount_residual):
                    continue
                sanitized_moves |= move
            if not sanitized_moves:
                raise UserError(_("You can't authorize debt because the records dont match the criteria."))
            if len(sanitized_moves.company_id) > 1:
                raise UserError(_("You cant authorize debt for records belonging to different companies."))
            if len(sanitized_moves.commercial_partner_id) > 1:
                raise UserError(_("You cant authorize debt for records belonging to different partners."))
            if len(set(sanitized_moves.mapped("move_type"))) > 1:
                raise UserError(
                    _("You can't authorize debt for records being either all inbound, either all outbound.")
                )
            res["move_ids"] = [Command.set(sanitized_moves.ids)]
            return res
        orders = self.env["sale.order"].browse(self._context.get("active_ids", []))
        sanitized_orders = self.env["sale.order"]
        for order in orders:
            if order.state not in ("draft", "sent"):
                raise UserError(_("You can only authorize debt for quotations."))
            if order.currency_id.is_zero(order.amount_total):
                continue
            sanitized_orders |= order
        if not sanitized_orders:
            raise UserError(_("You can't authorize debt because the records dont match the criteria."))
        if len(sanitized_orders.company_id) > 1:
            raise UserError(_("You cant authorize debt for records belonging to different companies."))
        if len(sanitized_orders.partner_id) > 1:
            raise UserError(_("You cant authorize debt for records belonging to different partners."))
        res["so_ids"] = [Command.set(sanitized_orders.ids)]
        return res

    @api.depends("move_ids", "so_ids")
    def _compute_from_record_ids(self):
        for wizard in self:
            if wizard.move_ids._origin:
                batches = wizard._get_move_ids_batches()
                wizard_values_from_batch = wizard._get_wizard_values_from_batch(batches)
                wizard.update(wizard_values_from_batch)
                continue
            if wizard.so_ids._origin:
                batches = wizard._get_so_ids_batches()
                wizard_values_from_batch = wizard._get_wizard_values_from_batch(batches)
                wizard.update(wizard_values_from_batch)
                continue
            wizard.update(
                {
                    "flag": False,
                    "partner_id": False,
                    "debt_request": 0.0,
                    "amount_authorize": 0.0,
                }
            )

    @api.depends("so_ids")
    def _compute_count_so(self):
        for rec in self:
            rec.count_so = len(rec.so_ids)

    @api.depends("move_ids")
    def _compute_count_move(self):
        for rec in self:
            rec.count_move = len(rec.move_ids)

    @api.model
    def _get_so_batch_key(self, order):
        partner = order.partner_id
        amount = order.amount_total
        vals = {
            "company_id": order.company_id.id,
            "credit_current": partner.credit,
            "credit_available": partner.credit_limit_available,
            "debt_request": abs(partner.credit_limit_available - amount),
            "flag": "credit",
        }
        return vals

    def _get_so_ids_batches(self):
        self.ensure_one()
        orders = self.so_ids._origin
        batches = {}
        for order in orders:
            if order.commercial_partner_id.id not in batches:
                batches[order.commercial_partner_id.id] = self._get_so_batch_key(order)
            elif order.commercial_partner_id.id in batches:
                batches[order.commercial_partner_id.id]["debt_request"] += abs(order.amount_total)
        return batches

    @api.model
    def _get_move_batch_key(self, move):
        partner = move.commercial_partner_id
        amount = abs(move.amount_total_in_currency_signed)
        vals = {
            "company_id": move.company_id.id,
        }
        if move.move_type == "in_invoice":
            vals.update(
                {
                    "debit_current": partner.debit,
                    "debit_available": partner.debit_limit_available,
                    "debt_request": abs(partner.debit_limit_available - amount),
                    "flag": "debit",
                }
            )
        elif move.move_type == "out_invoice":
            vals.update(
                {
                    "credit_current": partner.credit,
                    "credit_available": partner.credit_limit_available,
                    "debt_request": abs(partner.credit_limit_available - amount),
                    "flag": "credit",
                }
            )
        return vals

    def _get_move_ids_batches(self):
        self.ensure_one()
        moves = self.move_ids._origin
        batches = {}
        for move in moves:
            if move.commercial_partner_id.id not in batches:
                batches[move.commercial_partner_id.id] = self._get_move_batch_key(move)
            elif move.commercial_partner_id.id in batches:
                batches[move.commercial_partner_id.id]["debt_request"] += abs(move.amount_total_in_currency_signed)
        return batches

    @api.model
    def _get_wizard_values_from_batch(self, batches):
        first_key = list(batches.keys())[0]
        debt_request_total = 0
        for _k, vals in batches.items():
            debt_request_total += vals["debt_request"]
        res = {
            "flag": batches[first_key]["flag"],
            "partner_id": first_key if len(batches) == 1 else False,
            "debt_request": debt_request_total,
            "amount_authorize": debt_request_total,
        }
        company_id = batches[first_key]["company_id"]
        if company_id:
            res.update(
                {
                    "company_id": company_id,
                }
            )
        return res

    def action_increase_debt_limit(self):
        self._compute_from_record_ids()
        if self.partner_id and self.flag == "credit":
            self.partner_id.credit_limit += self.amount_authorize
        elif self.partner_id and self.flag == "debit":
            self.partner_id.debit_limit += self.amount_authorize

    def action_move_increase_debt_limit_and_post(self):
        self.action_increase_debt_limit()
        self.move_ids.with_context(debt_authorized=True).action_post()

    def action_so_increase_credit_limit_and_confirm(self):
        self.action_increase_debt_limit()
        for so in self.so_ids:
            so.action_confirm()
