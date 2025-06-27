import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { BankRecKanbanController } from "@account_accountant/components/bank_reconciliation/kanban";

patch(BankRecKanbanController.prototype, {
    async actionOpenOperationWizard() {
        await this.execProtectedBankRecAction(async () => {
            await this.withNewState(async (newState) => {
                const data = newState.bankRecRecordData;
                const stLineId = data?.st_line_id?.[0];

                if (!stLineId) {
                    console.warn("No se pudo determinar st_line_id desde:", data);
                    return;
                }

                const approvals = await this.orm.searchRead(
                    "approval.request",
                    [["bank_statement_line_id", "=", stLineId]],
                    ["id", "name", "telegram_data"]
                );

                console.log("Aprobaciones relacionadas con esta línea:", approvals);

                const baseContext = {
                    default_st_line_id: stLineId,
                    st_line_id: stLineId,
                    active_id: stLineId,
                    active_model: "account.bank.statement.line",
                    default_partner_id: data.partner_id?.[0],
                    default_journal_id: data.st_line_journal_id?.[0],
                    default_move_id: data.move_id?.[0],
                    default_amount: data.amount,
                };

                if (approvals.length > 0 && approvals[0].telegram_data) {
                    const telegram = approvals[0].telegram_data;

                    const CFDI_USAGE_MAP = {
                        "ADQUISICION DE MERCANCIAS": "G01",
                        "GASTOS EN GENERAL": "G03",
                    };

                    baseContext.default_diff_partner_id = telegram.partner_cn_id;

                    baseContext.l10n_mx_edi_usage = CFDI_USAGE_MAP[telegram.cfdi_use] || null;
                    baseContext.l10n_mx_edi_payment_method = telegram.payment_method;
                }

                console.log("Contexto base para la acción:", baseContext);

                this.action.doAction({
                    name: _t("Crear operación desde línea"),
                    type: "ir.actions.act_window",
                    res_model: "account.move.operation.from.entry",
                    view_mode: "form",
                    views: [[false, "form"]],
                    target: "new",
                    context: baseContext,
                });
            });
        });
    },
});
