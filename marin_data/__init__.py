from odoo import tools


def _post_init_marin(env):
    env.cr.execute(
        """
        SELECT setval('"public"."res_partner_id_seq"', 100, true);
        SELECT setval('"public"."resource_calendar_id_seq"', 100, true);
        SELECT setval('"public"."resource_calendar_attendance_id_seq"', 1000, true);
        """
    )
    tools.convert.convert_file(env, "marin_data", "data/res_company_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/resource_calendar_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/date.range.type.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/date.range.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/room.office.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/room.room.csv", None, mode="init", kind="data")

    model = "resource.calendar"
    calendars = env[model].sudo().search(
        [("active", "in", [True, False]), ("id", ">", 100)], order="id ASC"
    )
    for cc in calendars:
        exist = env["ir.model.data"].sudo().search([("model", "=", model), ("res_id", "=", cc.id)])
        if not exist:
            env["ir.model.data"].create(
                {
                    "module": "marin_data",
                    "model": model,
                    "name": "resource_calendar_%s" % cc.id,
                    "res_id": cc.id,
                    "noupdate": True,
                }
            )

    env.cr.execute("""SELECT setval('"public"."res_partner_id_seq"', 200, true);""")
    env.cr.execute("""SELECT setval('"public"."res_users_id_seq"', 200, true);""")
    tools.convert.convert_file(env, "marin_data", "data/website_data.xml", None, mode="init", kind="data")

    env.cr.execute("""SELECT setval('"public"."res_partner_id_seq"', 1000, true);""")
    env.cr.execute("""SELECT setval('"public"."res_users_id_seq"', 999, true);""")
    tools.convert.convert_file(env, "marin_data", "data/res.partner.csv", None, mode="init", kind="data")

    env.cr.execute(
        """
        SELECT setval('"public"."crm_team_id_seq"', 100, true);
        SELECT setval('"public"."res_partner_bank_id_seq"', 1000, true);
        SELECT setval('"public"."res_partner_id_seq"', 5000, true);
        SELECT setval('"public"."product_category_id_seq"', 100, true);
        SELECT setval('"public"."product_pricelist_id_seq"', 100, true);
        SELECT setval('"public"."product_pricelist_item_id_seq"', 1000, true);
        SELECT setval('"public"."stock_location_id_seq"', 1000, true);
        SELECT setval('"public"."stock_picking_type_id_seq"', 1000, true);
        SELECT setval('"public"."stock_route_id_seq"', 1000, true);
        SELECT setval('"public"."stock_rule_id_seq"', 1000, true);
        SELECT setval('"public"."stock_warehouse_id_seq"', 100, true);
        """
    )
    tools.convert.convert_file(env, "marin_data", "data/crm_team_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/res.partner-2.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/res.partner.bank.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/mrp.workcenter.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/res.users.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/stock.package.type.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/stock.storage.category.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/product.category.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/product_pricelist_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/product.tag.csv", None, mode="init", kind="data")

    model = "stock.warehouse"
    warehouses = env[model].sudo().search(
        [("active", "in", [True, False])], order="id ASC"
    )
    for wh in warehouses:
        exist = env["ir.model.data"].sudo().search([("model", "=", model), ("res_id", "=", wh.id)])
        if not exist:
            env["ir.model.data"].create(
                {
                    "module": "marin_data",
                    "model": model,
                    "name": "warehouse_%s" % wh.id,
                    "res_id": wh.id,
                    "noupdate": True,
                }
            )
    tools.convert.convert_file(env, "marin_data", "data/stock.warehouse.csv", None, mode="init", kind="data")

    model = "stock.location"
    locations = (
        env[model]
        .sudo()
        .search([("active", "in", [True, False])], order="id ASC")
    )
    for ln in locations:
        exist = env["ir.model.data"].sudo().search([("model", "=", model), ("res_id", "=", ln.id)])
        if not exist:
            env["ir.model.data"].create(
                {
                    "module": "marin_data",
                    "model": model,
                    "name": "stock_location_%s" % ln.id,
                    "res_id": ln.id,
                    "noupdate": True,
                }
            )
    env.cr.execute("""SELECT setval('"public"."stock_location_id_seq"', 5000, true);""")
    tools.convert.convert_file(env, "marin_data", "data/stock.location.csv", None, mode="init", kind="data")

    model = "stock.picking.type"
    types = env[model].sudo().search(
        [("active", "in", [True, False])], order="id ASC"
    )
    for spt in types:
        exist = env["ir.model.data"].sudo().search([("model", "=", model), ("res_id", "=", spt.id)])
        if not exist:
            env["ir.model.data"].create(
                {
                    "module": "marin_data",
                    "model": model,
                    "name": "picking_type_%s" % spt.id,
                    "res_id": spt.id,
                    "noupdate": True,
                }
            )

    env.cr.execute(
        """
        SELECT setval('"public"."stock_picking_type_id_seq"', 5000, true);
        SELECT setval('"public"."stock_route_id_seq"', 5000, true);
        SELECT setval('"public"."stock_rule_id_seq"', 5000, true);

        SELECT setval('"public"."account_account_id_seq"', 1000, true);
        SELECT setval('"public"."account_analytic_plan_id_seq"', 200, true);
        SELECT setval('"public"."account_journal_id_seq"', 1000, true);
        SELECT setval('"public"."account_payment_method_line_id_seq"', 1000, true);
        SELECT setval('"public"."account_payment_term_id_seq"', 100, true);
        SELECT setval('"public"."account_payment_term_line_id_seq"', 100, true);
        SELECT setval('"public"."account_tax_group_id_seq"', 1000, true);
        SELECT setval('"public"."account_tax_id_seq"', 1000, true);
        SELECT setval('"public"."account_tax_repartition_line_id_seq"', 5000, true);
        """
    )

    tools.convert.convert_file(env, "marin_data", "data/stock.picking.type.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/stock.route.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/stock.rule.csv", None, mode="init", kind="data")
    queries = [
        """UPDATE stock_picking_type SET sequence=100  WHERE name->>'en_US' = 'Delivery Orders'""",
        """UPDATE stock_picking_type SET sequence=150  WHERE name->>'en_US' = 'Ship orders'""",
        """UPDATE stock_picking_type SET sequence=150  WHERE name->>'en_US' = 'Ship orders 3P'""",
        """UPDATE stock_picking_type SET sequence=200  WHERE name->>'en_US' = 'PoS Orders'""",
        """UPDATE stock_picking_type SET sequence=300  WHERE name->>'en_US' ilike 'receipts'""",
        """UPDATE stock_picking_type SET sequence=350  WHERE name->>'en_US' ilike 'internal transfers'""",
        """UPDATE stock_picking_type SET sequence=400  WHERE name->>'en_US' ilike 'interwarehouse%'""",
        """UPDATE stock_picking_type SET sequence=500  WHERE name->>'en_US' ilike 'Returns from customers'""",
        """UPDATE stock_picking_type SET sequence=550  WHERE name->>'en_US' ilike 'Returns to suppliers'""",
        """UPDATE stock_picking_type SET sequence=600  WHERE name->>'en_US' ilike 'manufacturing'""",
        """UPDATE stock_picking_type SET sequence=700  WHERE name->>'en_US' ilike 'pick'""",
        """UPDATE stock_picking_type SET sequence=800  WHERE name->>'en_US' ilike 'pick components'""",
        """UPDATE stock_picking_type SET sequence=900  WHERE name->>'en_US' ilike 'pack'""",
        """UPDATE stock_picking_type SET sequence=1000 WHERE name->>'en_US' ilike 'store finished product'""",
        """UPDATE stock_picking_type SET sequence=1100 WHERE name->>'en_US' ilike 'subcontracting'""",
        """UPDATE stock_picking_type SET sequence=1200 WHERE name->>'en_US' ilike 'resupply subcontractor'""",
        """UPDATE stock_picking_type SET sequence=1300 WHERE name->>'en_US' ilike 'dropship'""",
        """UPDATE stock_picking_type SET sequence=1400 WHERE name->>'en_US' ilike 'dropship subcontractor'""",
        """UPDATE stock_picking_type SET sequence=1500 WHERE name->>'en_US' ilike 'intercompany%'""",
        """UPDATE stock_picking_type SET sequence=1600 WHERE name->>'en_US' ilike 'Quality Control'""",
        """UPDATE stock_picking_type SET sequence=1700 WHERE name->>'en_US' ilike 'Storage'""",
        """UPDATE stock_picking_type SET sequence=1800 WHERE name->>'en_US' ilike 'Cross Dock'""",
    ]
    for q in queries:
        env.cr.execute(q)

    tools.convert.convert_file(env, "marin_data", "data/account.account.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.analytic.plan.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.journal.group.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.journal.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.asset.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.payment.term.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.tax.group.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.tax.csv", None, mode="init", kind="data")

    env.cr.execute("""UPDATE account_payment_method_line SET id=id+10000 WHERE id>=1000""")
    env.cr.execute("""SELECT id FROM account_payment_method_line WHERE id>=10000 ORDER BY journal_id, payment_method_id""")
    records = env.cr.fetchall()
    start = 1001
    for r in records:
        env.cr.execute("""UPDATE account_payment_method_line SET id=%s WHERE id=%s""" % (start, r[0]))
        start += 1

    env.cr.execute("""UPDATE account_tax_repartition_line SET id=id+10000 WHERE id>=5000""")
    env.cr.execute("""SELECT id FROM account_tax_repartition_line WHERE id>=10000 ORDER BY tax_id, document_type, repartition_type""")
    records = env.cr.fetchall()
    start = 5001
    for r in records:
        env.cr.execute("""UPDATE account_tax_repartition_line SET id=%s WHERE id=%s""" % (start, r[0]))
        start += 1
    model = "account.tax.repartition.line"
    records = env[model].sudo().search(
        [("id", ">=", "5000")], order="id ASC"
    )
    for r in records:
        exist = env["ir.model.data"].sudo().search([("model", "=", model), ("res_id", "=", r.id)])
        if not exist:
            name = "tax_repartition_line_%s" % r.id
            env["ir.model.data"].create(
               {
                    "module": "marin_data",
                    "model": model,
                    "name": name,
                    "res_id": r.id,
                    "noupdate": True,
                }
            )

    model = "account.account.tag"
    aat = env[model].sudo().search(
        [("name", "ilike", "DIOT:")], order="id ASC"
    )
    for at in aat:
        exist = env["ir.model.data"].sudo().search([("model", "=", model), ("res_id", "=", at.id)])
        if not exist:
            env["ir.model.data"].create(
                {
                    "module": "l10n_mx",
                    "model": model,
                    "name": "l10n_mx_%s" % (at.name.replace(" ","_").replace("%","").replace(":","").replace("-","in_").replace("+","out_").lower()),
                    "res_id": at.id,
                    "noupdate": True,
                }
            )

    tools.convert.convert_file(env, "marin_data", "data/account.account.tag.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/account.tax.repartition.line.csv", None, mode="init", kind="data")

    env.cr.execute(
        """
        SELECT setval('"public"."product_packaging_id_seq"', 1000, true);
        SELECT setval('"public"."product_product_id_seq"', 1000, true);
        SELECT setval('"public"."product_template_id_seq"', 1000, true);

        SELECT setval('"public"."mrp_bom_id_seq"', 1000, true);
        SELECT setval('"public"."mrp_bom_line_id_seq"', 1000, true);

        SELECT setval('"public"."hr_contract_id_seq"', 1000, true);
        SELECT setval('"public"."hr_payroll_structure_type_id_seq"', 100, true);
        SELECT setval('"public"."hr_payroll_structure_id_seq"', 100, true);
        SELECT setval('"public"."hr_salary_rule_id_seq"', 1000, true);

        SELECT setval('"public"."pos_config_id_seq"', 97, true);
        SELECT setval('"public"."pos_payment_method_id_seq"', 100, true);

        SELECT setval('"public"."fleet_vehicle_model_brand_id_seq"', 100, true);
        SELECT setval('"public"."fleet_vehicle_model_id_seq"', 100, true);
        SELECT setval('"public"."account_analytic_account_id_seq"', 999, true);
        SELECT setval('"public"."account_analytic_distribution_model_id_seq"', 1000, true);
        """
    )

    tools.convert.convert_file(env, "marin_data", "data/pos.category.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/pos.payment.method.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/pos.config.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/product.template.csv", None, mode="init", kind="data")

    model = "product.product"
    products = env[model].sudo().search(
        [("active", "in", [True, False]), ("id", ">", 1000)], order="id ASC"
    )
    for pp in products:
        exist = env["ir.model.data"].sudo().search([("model", "=", model), ("res_id", "=", pp.id)])
        if not exist:
            env["ir.model.data"].create(
                {
                    "module": "marin_data",
                    "model": model,
                    "name": f"product_product_{pp.id}",
                    "res_id": pp.id,
                    "noupdate": True,
                }
            )
    tools.convert.convert_file(env, "marin_data", "data/product.packaging.csv", None, mode="init", kind="data")

    tools.convert.convert_file(env, "marin_data", "data/mrp.bom.csv", None, mode="init", kind="data")

    tools.convert.convert_file(env, "marin_data", "data/hr.department.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr.job.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/l10n_mx_edi_employer_registration_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr.employee.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr_payroll_structure_type_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr_payroll_structure_nomina_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr_payroll_structure_nomina_christmas_bonus_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr_payroll_structure_nomina_finiquito_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr_payroll_structure_misc_data.xml", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/hr.contract.csv", None, mode="init", kind="data")

    tools.convert.convert_file(env, "marin_data", "data/fleet.vehicle.model.brand.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/fleet.vehicle.model.category.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/fleet.vehicle.model.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/fleet.vehicle.csv", None, mode="init", kind="data")
    tools.convert.convert_file(env, "marin_data", "data/documents_document_data.xml", None, mode="init", kind="data")

#    tools.convert.convert_file(env, "marin_data", "data/account.analytic.account.csv", None, mode="init", kind="data")
#    tools.convert.convert_file(env, "marin_data", "data/account.analytic.distribution.model.csv", None, mode="init", kind="data")
#
#    tools.convert.convert_file(env, "marin_data", "data/project.project.csv", None, mode="init", kind="data")
#    tools.convert.convert_file(env, "marin_data", "data/project.task.type.csv", None, mode="init", kind="data")
#
#    tools.convert.convert_file(env, "marin_data", "data/res.company.csv", None, mode="init", kind="data")
#
#    env.cr.execute(
#        """
#        UPDATE account_account SET deprecated='t' WHERE id<1000;
#        UPDATE account_journal SET active='f' WHERE id<1000;
#        UPDATE account_tax SET active='f' WHERE id<1000;
#
#        UPDATE res_company SET font='Roboto';
#        UPDATE res_company SET product_folder_id=7;
#        UPDATE res_company SET documents_product_settings='t';
#        UPDATE res_company SET documents_hr_settings='t';
#        UPDATE res_company SET documents_recruitment_settings='t';
#        UPDATE res_company SET recruitment_extract_show_ocr_option_selection='manual_send';
#        UPDATE res_company SET stock_move_sms_validation='f';
#        UPDATE res_company SET account_purchase_tax_id=NULL;
#        UPDATE res_company SET account_sale_tax_id=NULL;
#        UPDATE res_company SET predict_bill_product='t';
#        UPDATE res_company SET l10n_mx_edi_pac='finkok';
#        UPDATE res_company SET l10n_mx_edi_pac_username='marin.guadarrama@gmail.com';
#        UPDATE res_company SET extract_in_invoice_digitalization_mode='manual_send';
#        UPDATE res_company SET extract_out_invoice_digitalization_mode='manual_send';
#        UPDATE res_company SET documents_account_settings='t';
#        UPDATE res_company SET expense_extract_show_ocr_option_selection='manual_send';
#        UPDATE res_company SET po_double_validation='two_step';
#        UPDATE res_company SET portal_confirmation_sign='f';
#        UPDATE res_company SET quotation_validity_days=7;
#        UPDATE res_company SET l10n_mx_edi_minimum_wage=248.93;
#        UPDATE res_company SET l10n_mx_edi_uma=108.57;
#        """
#    )
#