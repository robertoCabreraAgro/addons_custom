from odoo import Command


def post_init_hook(env):
    env.ref("hr_payroll.mail_template_new_payslip").write(
        {
            "report_template_ids": [Command.link(env.ref("hr_payroll.action_report_payslip").id)],
        }
    )
