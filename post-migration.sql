-- Delete cron

WITH deleted_extid AS (
    DELETE FROM
        ir_model_data
    WHERE
        model = 'ir.cron'
        AND module IN (
            'l10n_mx_partner_blocklist',
            'droggol_theme_common'
        )
    RETURNING
        res_id
)
DELETE FROM
    ir_cron AS cron
USING
    deleted_extid AS extid
WHERE
    cron.id = extid.res_id;

-- Delete views

WITH deleted_extid AS (
    DELETE FROM
        ir_model_data
    WHERE
        model = 'ir.ui.view'
        AND module IN (
            'marin_account',
            'marin_account_fleet',
            'marin_base',
            'marin_documents',
            'marin_documents_account',
            'marin_hr',
            'marin_l10n_mx_edi',
            'marin_mrp',
            'marin_pos',
            'marin_purchase',
            'marin_sale',
            'marin_stock',
            'marin_stock_barcode',
            'stock_location_removal_priority'
        )
    RETURNING
        res_id
)
DELETE FROM
    ir_ui_view AS view
USING
    deleted_extid AS extid
WHERE
    view.id = extid.res_id;

-- Delete views

WITH deleted_extid AS (
    DELETE FROM
        ir_model_data
    WHERE
        model = 'ir.ui.menu'
        AND module IN (
            'marin_account',
            'marin_account_fleet',
            'marin_base',
            'marin_documents',
            'marin_documents_account',
            'marin_hr',
            'marin_l10n_mx_edi',
            'marin_mrp',
            'marin_pos',
            'marin_purchase',
            'marin_sale',
            'marin_stock',
            'marin_stock_barcode',
            'stock_location_removal_priority'
        )
    RETURNING
        res_id
)
DELETE FROM
    ir_ui_menu AS menu
USING
    deleted_extid AS extid
WHERE
    menu.id = extid.res_id;

-- Delete window actions

WITH deleted_extid AS (
    DELETE FROM
        ir_model_data
    WHERE
        model = 'ir.actions.act_window'
        AND module IN (
            'marin_account',
            'marin_account_fleet',
            'marin_base',
            'marin_documents',
            'marin_documents_account',
            'marin_hr',
            'marin_l10n_mx_edi',
            'marin_mrp',
            'marin_pos',
            'marin_purchase',
            'marin_sale',
            'marin_stock',
            'marin_stock_barcode',
            'stock_location_removal_priority'
        )
    RETURNING
        res_id
)
DELETE FROM
    ir_act_window AS iaw
USING
    deleted_extid AS extid
WHERE
    iaw.id = extid.res_id;

-- Delete model xml_ids

DELETE FROM
    ir_model_data
WHERE
    model = 'ir.model'
    AND module IN (
        'marin_account',
        'marin_account_fleet',
        'marin_base',
        'marin_documents',
        'marin_documents_account',
        'marin_hr',
        'marin_l10n_mx_edi',
        'marin_mrp',
        'marin_pos',
        'marin_purchase',
        'marin_sale',
        'marin_stock',
        'marin_stock_barcode',
        'stock_location_removal_priority'
    );

-- UPDATE xml_ids of fused modules

CREATE PROCEDURE rename_module_xml_id(old_module char, new_module char)
LANGUAGE SQL
AS $$
    WITH to_update_xml_ids AS (
        SELECT
            imd.id,
            imd.module,
            imd.name
        FROM
            ir_model_data AS imd
        LEFT OUTER JOIN
            ir_model_data AS imd2
            ON imd.id != imd2.id
            AND imd.module = old_module
            AND imd2.module = new_module
            AND imd.name = imd2.name
        WHERE
            imd.module = old_module
            AND imd2.id IS NULL
    )
    UPDATE
        ir_model_data
    SET
        module = new_module
    WHERE
        ir_model_data.id IN (SELECT id FROM to_update_xml_ids);
$$;

CALL rename_module_xml_id('marin_account', 'xiuman');
CALL rename_module_xml_id('marin_account_fleet', 'xiuman');
CALL rename_module_xml_id('marin_base', 'xiuman');
CALL rename_module_xml_id('marin_documents', 'xiuman');
CALL rename_module_xml_id('marin_documents_account', 'xiuman');
CALL rename_module_xml_id('marin_hr', 'xiuman');
CALL rename_module_xml_id('marin_l10n_mx_edi', 'xiuman');
CALL rename_module_xml_id('marin_mrp', 'xiuman');
CALL rename_module_xml_id('marin_pos', 'xiuman');
CALL rename_module_xml_id('marin_purchase', 'xiuman');
CALL rename_module_xml_id('marin_sale', 'xiuman');
CALL rename_module_xml_id('marin_stock', 'xiuman');
CALL rename_module_xml_id('marin_stock_barcode', 'xiuman');
CALL rename_module_xml_id('stock_location_removal_priority', 'xiuman');

/*
Remove all but certified modules, so inexisting ones don't  trigger warnings and only
explicitly specified ones are kept.
*/
WITH deleted_module AS (
    DELETE FROM
        ir_module_module
    WHERE
        author NOT IN ('Odoo S.A.', 'Odoo SA', 'Odoo')
        -- CoA modules are generally not authored by Odoo
        AND name NOT LIKE 'l10n\___'
        AND name NOT IN (
            'account_move_template',
            'account_move_name_sequence',
            'account_move_operation',
            -- 'account_move_print',
            -- 'base_geoengine',
            'documents_expiry',
            'documents_partner',
            'l10n_mx_edi',
            'l10n_mx_edi_40',
            'l10n_mx_edi_avoid_reversal_entry',
            'documents_l10n_mx_edi',
            -- 'l10n_mx_edi_partner_defaults',
            'l10n_mx_edi_payslip',
            -- 'l10n_mx_edi_related_documents',
            -- 'l10n_mx_edi_supplier_defaults',
            -- 'l10n_mx_partner_blocklist',
            'l10n_mx_reports',
            'marin_l10n_mx_edi_payslip',
            'muk_product',
            -- 'pos_lot_selection',
            -- 'project_agriculture',
            'stock_picking_batch_fleet',
            'users_working_hours',
            'xiuman',
            'sentry'
        )
    RETURNING
        id,
        name
)
DELETE FROM
    ir_model_data AS imd
USING
    deleted_module AS module
WHERE
    ( -- Remove module's external ID
        imd.model = 'ir.module.module'
        AND imd.res_id = module.id
    ) OR ( -- Models and fields's external IDs, to catch orphan ones later
        imd.module = module.name
        AND imd.model IN ('ir.model', 'ir.model.fields')
    );

-- Remove views, they will be re-created when updating all modules anyway
WITH deleted_view AS (
    DELETE FROM
        ir_ui_view
    WHERE
        id NOT IN (SELECT view_id FROM report_layout)
        AND id NOT IN (SELECT view_id FROM website_page)
        AND id NOT IN (SELECT redirect_form_view_id FROM payment_provider WHERE redirect_form_view_id IS NOT NULL)
        AND id NOT IN (SELECT inline_form_view_id FROM payment_provider WHERE inline_form_view_id IS NOT NULL)
        AND id NOT IN (SELECT token_inline_form_view_id FROM payment_provider WHERE token_inline_form_view_id IS NOT NULL)
        AND id NOT IN (SELECT express_checkout_form_view_id FROM payment_provider WHERE express_checkout_form_view_id IS NOT NULL)
        AND id NOT IN (SELECT address_view_id FROM res_country WHERE address_view_id IS NOT NULL)
        AND id NOT IN (SELECT view_id FROM geoengine_raster_layer WHERE view_id IS NOT NULL)
        AND name != 'My Dashboard'
        AND l10n_mx_edi_addenda_flag IS NOT TRUE
    RETURNING
        id
)
DELETE FROM
    ir_model_data AS imd
USING
    deleted_view AS view
WHERE
    imd.model = 'ir.ui.view'
    AND imd.res_id = view.id;

-- Remove orphan data, only models and fields. The rest will be taken care of by Python scripts
DELETE FROM
    ir_model_fields AS field
USING
    ir_model_fields AS orphan
LEFT OUTER JOIN
    ir_model_data AS imd
    ON imd.res_id = orphan.id
    AND imd.model = 'ir.model.fields'
WHERE
    field.id = orphan.id
    AND imd.id IS NULL;

DELETE FROM
    ir_model AS model
USING
    ir_model AS orphan
LEFT OUTER JOIN
    ir_model_data AS imd
    ON imd.res_id = orphan.id
    AND imd.model = 'ir.model'
WHERE
    model.id = orphan.id
    AND imd.id IS NULL;

/*
Remove all selections from fields (ir.model.fields.selection).
Not removing only orphan ones because it's not easy to know which ones actually are,
because, every time a selection field is inherited, external IDs are created for all selections,
even if they are from other modules.
*/
DELETE FROM ir_model_fields_selection;

DELETE FROM
    ir_model_data
WHERE
    model = 'ir.model.fields.selection';

-- Remove ir.model.access in order to get rid of records created functionally
DELETE FROM ir_model_access;

DELETE FROM
    ir_model_data
WHERE
    model = 'ir.model.access';

-- Renamed xml_ids

CREATE PROCEDURE rename_xml_id(module_name char, old_name char, new_name char)
LANGUAGE SQL
AS $$
    UPDATE
        ir_model_data
    SET
        name = new_name
    WHERE
        module = module_name
        AND name = old_name;
$$;

CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_folder_edi_doc', 'documents_l10n_mx_edi_folder');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_facet_fiscal_year', 'documents_l10n_mx_edi_facet_fiscal_year');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_facet_fiscal_month', 'documents_l10n_mx_edi_facet_fiscal_month');
CALL rename_xml_id('documents_l10n_mx_edi', 'l10n_mx_edi_to_process', 'documents_l10n_mx_edi_tag_to_process');
CALL rename_xml_id('documents_l10n_mx_edi', 'l10n_mx_edi_processed', 'documents_l10n_mx_edi_tag_processed');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_ingreso', 'documents_l10n_mx_edi_tag_ingreso');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_egreso', 'documents_l10n_mx_edi_tag_egreso');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_traslado', 'documents_l10n_mx_edi_tag_traslado');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_nomina', 'documents_l10n_mx_edi_tag_nomina');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_pago', 'documents_l10n_mx_edi_tag_pago');
CALL rename_xml_id('documents_l10n_mx_edi', 'documents_l10n_mx_edi_retencion', 'documents_l10n_mx_edi_tag_retencion');

-- Renamed xml_ids and changed of module

-- CREATE PROCEDURE rename_xml_id(old_module char, new_module char, old_name char, new_name char)
-- LANGUAGE SQL
-- AS $$
--     UPDATE
--         ir_model_data
--     SET
--         name = new_name,
--         module = new_module
--     WHERE
--         module = old_module
--         AND name = old_name;
-- $$;

-- CALL rename_xml_id('marin_account', 'xiuman', 'marin_rebollo_company', 'data_res_company_lmmr');

UPDATE
    ir_model_data
SET
    name = 'data_res_company_lmmr',
    module = 'xiuman'
WHERE
    module = 'marin_account'
    AND name = 'marin_rebollo_company';

-- Set xml_ids to manually created records that now have data

INSERT INTO
    ir_model_data (
        name,
        res_id,
        module,
        model,
        noupdate
    )
VALUES
    ('team_lmmg', 5, 'xiuman', 'crm.team', TRUE),
    ('team_lmmg_website', 6, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_sub', 10, 'xiuman', 'crm.team', TRUE),
    ('team_tjgl', 11, 'xiuman', 'crm.team', TRUE),
    ('team_glmm', 12, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_1', 13, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_2', 14, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_3', 15, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_4', 16, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_5', 17, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_6', 18, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_7', 19, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_8', 20, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_9', 21, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_10', 22, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_11', 23, 'xiuman', 'crm.team', TRUE),
    ('team_lmmr_12', 24, 'xiuman', 'crm.team', TRUE),
    ('data_res_company_tjgl', 3, 'xiuman', 'res.company', TRUE),
    ('data_res_company_ammg', 4, 'xiuman', 'res.company', TRUE),
    ('data_res_company_cfmg', 5, 'xiuman', 'res.company', TRUE),
    ('data_res_company_glmm', 6, 'xiuman', 'res.company', TRUE),
    ('data_res_partner_lmmr', 101, 'xiuman', 'res.partner', TRUE),
    ('data_res_partner_tjgl', 102, 'xiuman', 'res.partner', TRUE),
    ('data_res_partner_ammg', 103, 'xiuman', 'res.partner', TRUE),
    ('data_res_partner_cfmg', 104, 'xiuman', 'res.partner', TRUE),
    ('data_res_partner_glmm', 105, 'xiuman', 'res.partner', TRUE),
    ('cuenta101_01_001_base', 901, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_001_base', 902, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_002_base', 903, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_003_base', 904, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_004_base', 905, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_005_base', 906, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_006_base', 907, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_001_base', 908, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_002_base', 909, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_001_base', 910, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_002_base', 911, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_02_001_base', 912, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_002_base', 913, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_099_base', 914, 'xiuman_data', 'account.account', TRUE),
    ('cuenta206_01_001_base', 915, 'xiuman_data', 'account.account', TRUE),
    ('cuenta208_01_001_base', 916, 'xiuman_data', 'account.account', TRUE),
    ('cuenta208_02_001_base', 917, 'xiuman_data', 'account.account', TRUE),
    ('cuenta209_01_001_base', 918, 'xiuman_data', 'account.account', TRUE),
    ('cuenta209_02_001_base', 919, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_01_001_base', 920, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_03_001_base', 921, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_05_001_base', 922, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_01_001_base', 923, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_10_002_base', 924, 'xiuman_data', 'account.account', TRUE),
    ('cuenta252_07_001_base', 925, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_001_base', 926, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_000_base', 927, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_111_base', 928, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_01_001_base', 929, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_02_001_base', 930, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_08_001_base', 931, 'xiuman_data', 'account.account', TRUE),
    ('cuenta114_01_001_base', 932, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_001_base', 933, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_002_base', 934, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_01_001_base', 935, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_03_001_base', 936, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_01_001_base', 937, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_01_002_base', 938, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_03_001_base', 939, 'xiuman_data', 'account.account', TRUE),
    ('cuenta120_01_001_base', 940, 'xiuman_data', 'account.account', TRUE),
    ('cuenta120_01_002_base', 941, 'xiuman_data', 'account.account', TRUE),
    ('cuenta151_01_001_base', 942, 'xiuman_data', 'account.account', TRUE),
    ('cuenta151_01_002_base', 943, 'xiuman_data', 'account.account', TRUE),
    ('cuenta153_01_001_base', 944, 'xiuman_data', 'account.account', TRUE),
    ('cuenta153_01_002_base', 945, 'xiuman_data', 'account.account', TRUE),
    ('cuenta154_01_001_base', 946, 'xiuman_data', 'account.account', TRUE),
    ('cuenta154_01_002_base', 947, 'xiuman_data', 'account.account', TRUE),
    ('cuenta155_01_001_base', 948, 'xiuman_data', 'account.account', TRUE),
    ('cuenta155_01_002_base', 949, 'xiuman_data', 'account.account', TRUE),
    ('cuenta156_01_001_base', 950, 'xiuman_data', 'account.account', TRUE),
    ('cuenta160_01_001_base', 951, 'xiuman_data', 'account.account', TRUE),
    ('cuenta165_01_001_base', 952, 'xiuman_data', 'account.account', TRUE),
    ('cuenta165_01_002_base', 953, 'xiuman_data', 'account.account', TRUE),
    ('cuenta179_01_001_base', 954, 'xiuman_data', 'account.account', TRUE),
    ('cuenta402_02_003_base', 955, 'xiuman_data', 'account.account', TRUE),
    ('cuenta402_02_004_base', 956, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_001_base', 957, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_002_base', 958, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_003_base', 959, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_15_002_base', 960, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_17_001_base', 961, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_17_002_base', 962, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_63_001_base', 963, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_83_001_base', 964, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_83_008_base', 965, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_84_001_base', 966, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_84_002_base', 967, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_01_002_base', 968, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_16_001_base', 969, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_16_002_base', 970, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_48_001_base', 971, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_48_002_base', 972, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_49_001_base', 973, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_49_002_base', 974, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_50_001_base', 975, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_50_002_base', 976, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_51_001_base', 977, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_52_001_base', 978, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_52_002_base', 979, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_54_001_base', 980, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_54_002_base', 981, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_56_001_base', 982, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_56_002_base', 983, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_57_001_base', 984, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_61_001_base', 985, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_61_002_base', 986, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_62_001_base', 987, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_72_001_base', 988, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_72_002_base', 989, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_74_001_base', 990, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_74_002_base', 991, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_77_001_base', 992, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_001_base', 993, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_002_base', 994, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_003_base', 995, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_004_base', 996, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_005_base', 997, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_007_base', 998, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_008_base', 999, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_84_001_base', 1000, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_84_002_base', 1001, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_100_001_base', 1002, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_100_002_base', 1003, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_101_001_base', 1004, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_101_002_base', 1005, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_102_001_base', 1006, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_102_002_base', 1007, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_32_001_base', 1008, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_32_002_base', 1009, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_34_001_base', 1010, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_34_002_base', 1011, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_45_001_base', 1012, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_45_002_base', 1013, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_55_001_base', 1014, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_55_002_base', 1015, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_58_001_base', 1016, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_58_002_base', 1017, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_59_001_base', 1018, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_62_001_base', 1019, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_83_006_base', 1020, 'xiuman_data', 'account.account', TRUE),
    ('cuenta611_01_001_base', 1021, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_01_001_base', 1022, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_04_001_base', 1023, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_08_001_base', 1024, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_10_001_base', 1025, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_001_base', 1026, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_002_base', 1027, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_003_base', 1028, 'xiuman_data', 'account.account', TRUE),
    ('cuenta899_01_099_base', 1029, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_08_001_base', 1030, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_08_002_base', 1031, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_09_001_base', 1032, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_10_001_base', 1033, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_11_001_base', 1034, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_12_001_base', 1035, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_14_001_base', 1036, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_14_002_base', 1037, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_01_001_base', 1038, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_000_base', 1039, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_001_base', 1040, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_002_base', 1041, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_003_base', 1042, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_004_base', 1043, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_005_base', 1044, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_006_base', 1045, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_007_base', 1046, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_008_base', 1047, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_009_base', 1048, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_010_base', 1049, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_22_001_base', 1050, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_22_002_base', 1051, 'xiuman_data', 'account.account', TRUE),
    ('cuenta503_01_004_base', 1052, 'xiuman_data', 'account.account', TRUE),
    ('cuenta503_01_005_base', 1053, 'xiuman_data', 'account.account', TRUE),
    ('cuenta503_01_006_base', 1054, 'xiuman_data', 'account.account', TRUE),
    ('cuenta702_01_001_base', 1055, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_01_001_base', 1056, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_03_001_base', 1057, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_04_001_base', 1058, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_04_002_base', 1059, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_22_001_base', 1060, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_001_base', 1061, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_002_base', 1062, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_003_base', 1063, 'xiuman_data', 'account.account', TRUE),
    ('cuenta302_01_001_base', 1064, 'xiuman_data', 'account.account', TRUE),
    ('cuenta302_01_002_base', 1065, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_001_base', 1066, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_002_base', 1067, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_001_base', 1068, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_002_base', 1069, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_001_base', 1070, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_002_base', 1071, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_02_001_base', 1072, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_02_002_base', 1073, 'xiuman_data', 'account.account', TRUE),
    ('cuenta101_01_001_lmmr', 1074, 'xiuman_data', 'account.account', TRUE),
    ('cuenta101_01_003_lmmr', 1075, 'xiuman_data', 'account.account', TRUE),
    ('cuenta101_01_005_lmmr', 1076, 'xiuman_data', 'account.account', TRUE),
    ('cuenta101_01_007_lmmr', 1077, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_001_lmmr', 1078, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_002_lmmr', 1079, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_003_lmmr', 1080, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_004_lmmr', 1081, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_006_lmmr', 1082, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_001_lmmr', 1083, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_002_lmmr', 1084, 'xiuman_data', 'account.account', TRUE),
    ('cuenta107_01_001_lmmr', 1085, 'xiuman_data', 'account.account', TRUE),
    ('cuenta107_01_002_lmmr', 1086, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_001_lmmr', 1087, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_002_lmmr', 1088, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_02_001_lmmr', 1089, 'xiuman_data', 'account.account', TRUE),
    ('cuenta000_00_000_lmmr', 1090, 'xiuman_data', 'account.account', TRUE),
    ('cuenta000_00_001_lmmr', 1091, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_01_002_lmmr', 1092, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_008_lmmr', 1093, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_099_lmmr', 1094, 'xiuman_data', 'account.account', TRUE),
    ('cuenta206_01_001_lmmr', 1095, 'xiuman_data', 'account.account', TRUE),
    ('cuenta208_01_001_lmmr', 1096, 'xiuman_data', 'account.account', TRUE),
    ('cuenta208_02_001_lmmr', 1097, 'xiuman_data', 'account.account', TRUE),
    ('cuenta209_01_001_lmmr', 1098, 'xiuman_data', 'account.account', TRUE),
    ('cuenta209_02_001_lmmr', 1099, 'xiuman_data', 'account.account', TRUE),
    ('cuenta210_01_001_lmmr', 1100, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_01_001_lmmr', 1101, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_03_001_lmmr', 1102, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_05_001_lmmr', 1103, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_01_001_lmmr', 1104, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_03_001_lmmr', 1105, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_03_002_lmmr', 1106, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_10_002_lmmr', 1107, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_10_010_lmmr', 1108, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_10_020_lmmr', 1109, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_11_001_lmmr', 1110, 'xiuman_data', 'account.account', TRUE),
    ('cuenta252_01_001_lmmr', 1111, 'xiuman_data', 'account.account', TRUE),
    ('cuenta252_07_001_lmmr', 1112, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_001_lmmr', 1113, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_002_lmmr', 1114, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_003_lmmr', 1115, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_004_lmmr', 1116, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_005_lmmr', 1117, 'xiuman_data', 'account.account', TRUE),
    ('cuenta202_03_006_lmmr', 1118, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_000_lmmr', 1119, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_005_lmmr', 1120, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_110_lmmr', 1121, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_111_lmmr', 1122, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_01_001_lmmr', 1123, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_02_001_lmmr', 1124, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_06_001_lmmr', 1125, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_08_001_lmmr', 1126, 'xiuman_data', 'account.account', TRUE),
    ('cuenta114_01_001_lmmr', 1127, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_001_lmmr', 1128, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_002_lmmr', 1129, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_01_001_lmmr', 1130, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_03_001_lmmr', 1131, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_01_001_lmmr', 1132, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_03_001_lmmr', 1133, 'xiuman_data', 'account.account', TRUE),
    ('cuenta120_01_001_lmmr', 1134, 'xiuman_data', 'account.account', TRUE),
    ('cuenta120_01_002_lmmr', 1135, 'xiuman_data', 'account.account', TRUE),
    ('cuenta151_01_001_lmmr', 1136, 'xiuman_data', 'account.account', TRUE),
    ('cuenta151_01_002_lmmr', 1137, 'xiuman_data', 'account.account', TRUE),
    ('cuenta153_01_001_lmmr', 1138, 'xiuman_data', 'account.account', TRUE),
    ('cuenta153_01_002_lmmr', 1139, 'xiuman_data', 'account.account', TRUE),
    ('cuenta154_01_001_lmmr', 1140, 'xiuman_data', 'account.account', TRUE),
    ('cuenta154_01_002_lmmr', 1141, 'xiuman_data', 'account.account', TRUE),
    ('cuenta155_01_001_lmmr', 1142, 'xiuman_data', 'account.account', TRUE),
    ('cuenta156_01_001_lmmr', 1143, 'xiuman_data', 'account.account', TRUE),
    ('cuenta160_01_001_lmmr', 1144, 'xiuman_data', 'account.account', TRUE),
    ('cuenta165_01_001_lmmr', 1145, 'xiuman_data', 'account.account', TRUE),
    ('cuenta165_01_002_lmmr', 1146, 'xiuman_data', 'account.account', TRUE),
    ('cuenta179_01_001_lmmr', 1147, 'xiuman_data', 'account.account', TRUE),
    ('cuenta402_02_003_lmmr', 1148, 'xiuman_data', 'account.account', TRUE),
    ('cuenta402_02_004_lmmr', 1149, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_000_lmmr', 1150, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_001_lmmr', 1151, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_003_lmmr', 1152, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_01_001_lmmr', 1153, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_01_002_lmmr', 1154, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_06_001_lmmr', 1155, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_07_001_lmmr', 1156, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_07_002_lmmr', 1157, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_12_001_lmmr', 1158, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_12_002_lmmr', 1159, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_15_001_lmmr', 1160, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_15_002_lmmr', 1161, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_16_001_lmmr', 1162, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_16_002_lmmr', 1163, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_17_001_lmmr', 1164, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_17_002_lmmr', 1165, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_26_001_lmmr', 1166, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_34_001_lmmr', 1167, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_34_002_lmmr', 1168, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_38_001_lmmr', 1169, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_38_002_lmmr', 1170, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_48_001_lmmr', 1171, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_48_002_lmmr', 1172, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_49_001_lmmr', 1173, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_49_002_lmmr', 1174, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_50_001_lmmr', 1175, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_50_002_lmmr', 1176, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_51_001_lmmr', 1177, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_51_002_lmmr', 1178, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_52_001_lmmr', 1179, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_52_002_lmmr', 1180, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_54_001_lmmr', 1181, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_54_002_lmmr', 1182, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_56_001_lmmr', 1183, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_56_002_lmmr', 1184, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_57_001_lmmr', 1185, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_58_001_lmmr', 1186, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_58_002_lmmr', 1187, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_59_001_lmmr', 1188, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_63_001_lmmr', 1189, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_63_002_lmmr', 1190, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_77_001_lmmr', 1191, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_77_002_lmmr', 1192, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_78_001_lmmr', 1193, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_78_002_lmmr', 1194, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_80_001_lmmr', 1195, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_80_002_lmmr', 1196, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_83_001_lmmr', 1197, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_83_008_lmmr', 1198, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_84_001_lmmr', 1199, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_84_002_lmmr', 1200, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_01_001_lmmr', 1201, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_01_002_lmmr', 1202, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_02_001_lmmr', 1203, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_06_001_lmmr', 1204, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_06_002_lmmr', 1205, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_07_001_lmmr', 1206, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_07_002_lmmr', 1207, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_10_002_lmmr', 1208, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_12_001_lmmr', 1209, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_12_002_lmmr', 1210, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_15_001_lmmr', 1211, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_15_002_lmmr', 1212, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_16_001_lmmr', 1213, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_16_002_lmmr', 1214, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_17_002_lmmr', 1215, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_19_002_lmmr', 1216, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_25_001_lmmr', 1217, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_25_002_lmmr', 1218, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_26_001_lmmr', 1219, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_26_002_lmmr', 1220, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_27_001_lmmr', 1221, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_30_001_lmmr', 1222, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_34_001_lmmr', 1223, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_34_002_lmmr', 1224, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_38_001_lmmr', 1225, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_38_002_lmmr', 1226, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_45_001_lmmr', 1227, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_45_002_lmmr', 1228, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_46_001_lmmr', 1229, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_46_002_lmmr', 1230, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_48_001_lmmr', 1231, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_48_002_lmmr', 1232, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_49_001_lmmr', 1233, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_49_002_lmmr', 1234, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_50_001_lmmr', 1235, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_50_002_lmmr', 1236, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_51_001_lmmr', 1237, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_51_002_lmmr', 1238, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_52_001_lmmr', 1239, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_52_002_lmmr', 1240, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_53_002_lmmr', 1241, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_54_001_lmmr', 1242, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_54_002_lmmr', 1243, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_56_001_lmmr', 1244, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_56_002_lmmr', 1245, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_57_001_lmmr', 1246, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_58_002_lmmr', 1247, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_61_001_lmmr', 1248, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_61_002_lmmr', 1249, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_62_001_lmmr', 1250, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_62_002_lmmr', 1251, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_72_001_lmmr', 1252, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_72_002_lmmr', 1253, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_74_001_lmmr', 1254, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_74_002_lmmr', 1255, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_77_001_lmmr', 1256, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_77_002_lmmr', 1257, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_78_001_lmmr', 1258, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_78_002_lmmr', 1259, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_80_001_lmmr', 1260, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_80_002_lmmr', 1261, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_001_lmmr', 1262, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_002_lmmr', 1263, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_003_lmmr', 1264, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_004_lmmr', 1265, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_005_lmmr', 1266, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_007_lmmr', 1267, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_83_008_lmmr', 1268, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_84_001_lmmr', 1269, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_84_002_lmmr', 1270, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_84_003_lmmr', 1271, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_84_004_lmmr', 1272, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_84_005_lmmr', 1273, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_01_001_lmmr', 1274, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_01_002_lmmr', 1275, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_06_001_lmmr', 1276, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_06_002_lmmr', 1277, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_07_001_lmmr', 1278, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_07_002_lmmr', 1279, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_10_002_lmmr', 1280, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_100_001_lmmr', 1281, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_100_002_lmmr', 1282, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_101_001_lmmr', 1283, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_101_002_lmmr', 1284, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_102_001_lmmr', 1285, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_102_002_lmmr', 1286, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_12_001_lmmr', 1287, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_12_002_lmmr', 1288, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_15_001_lmmr', 1289, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_15_002_lmmr', 1290, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_16_001_lmmr', 1291, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_16_002_lmmr', 1292, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_17_002_lmmr', 1293, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_19_002_lmmr', 1294, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_25_001_lmmr', 1295, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_25_002_lmmr', 1296, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_26_001_lmmr', 1297, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_26_002_lmmr', 1298, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_27_001_lmmr', 1299, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_30_001_lmmr', 1300, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_32_001_lmmr', 1301, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_32_002_lmmr', 1302, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_34_001_lmmr', 1303, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_34_002_lmmr', 1304, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_38_001_lmmr', 1305, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_38_002_lmmr', 1306, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_45_001_lmmr', 1307, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_45_002_lmmr', 1308, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_48_001_lmmr', 1309, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_48_002_lmmr', 1310, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_49_001_lmmr', 1311, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_49_002_lmmr', 1312, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_50_001_lmmr', 1313, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_50_002_lmmr', 1314, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_51_001_lmmr', 1315, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_51_002_lmmr', 1316, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_52_001_lmmr', 1317, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_52_002_lmmr', 1318, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_53_002_lmmr', 1319, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_54_001_lmmr', 1320, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_54_002_lmmr', 1321, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_55_001_lmmr', 1322, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_55_002_lmmr', 1323, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_56_001_lmmr', 1324, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_56_002_lmmr', 1325, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_57_011_lmmr', 1326, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_58_001_lmmr', 1327, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_58_002_lmmr', 1328, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_59_001_lmmr', 1329, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_61_001_lmmr', 1330, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_61_002_lmmr', 1331, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_62_001_lmmr', 1332, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_62_002_lmmr', 1333, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_63_002_lmmr', 1334, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_75_001_lmmr', 1335, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_75_002_lmmr', 1336, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_76_002_lmmr', 1337, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_80_001_lmmr', 1338, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_80_002_lmmr', 1339, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_82_002_lmmr', 1340, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_83_006_lmmr', 1341, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_83_008_lmmr', 1342, 'xiuman_data', 'account.account', TRUE),
    ('cuenta611_01_001_lmmr', 1343, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_01_001_lmmr', 1344, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_04_001_lmmr', 1345, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_08_001_lmmr', 1346, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_10_001_lmmr', 1347, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_10_002_lmmr', 1348, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_001_lmmr', 1349, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_002_lmmr', 1350, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_003_lmmr', 1351, 'xiuman_data', 'account.account', TRUE),
    ('cuenta899_01_099_lmmr', 1352, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_08_001_lmmr', 1353, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_08_002_lmmr', 1354, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_09_001_lmmr', 1355, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_10_001_lmmr', 1356, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_11_001_lmmr', 1357, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_12_001_lmmr', 1358, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_14_001_lmmr', 1359, 'xiuman_data', 'account.account', TRUE),
    ('cuenta504_14_002_lmmr', 1360, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_01_001_lmmr', 1361, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_000_lmmr', 1362, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_001_lmmr', 1363, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_002_lmmr', 1364, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_003_lmmr', 1365, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_004_lmmr', 1366, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_005_lmmr', 1367, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_006_lmmr', 1368, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_007_lmmr', 1369, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_008_lmmr', 1370, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_009_lmmr', 1371, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_010_lmmr', 1372, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_011_lmmr', 1373, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_22_001_lmmr', 1374, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_22_002_lmmr', 1375, 'xiuman_data', 'account.account', TRUE),
    ('cuenta503_01_004_lmmr', 1376, 'xiuman_data', 'account.account', TRUE),
    ('cuenta503_01_005_lmmr', 1377, 'xiuman_data', 'account.account', TRUE),
    ('cuenta503_01_007_lmmr', 1378, 'xiuman_data', 'account.account', TRUE),
    ('cuenta702_01_001_lmmr', 1379, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_01_001_lmmr', 1380, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_03_001_lmmr', 1381, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_04_001_lmmr', 1382, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_04_002_lmmr', 1383, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_22_001_lmmr', 1384, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_001_lmmr', 1385, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_002_lmmr', 1386, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_003_lmmr', 1387, 'xiuman_data', 'account.account', TRUE),
    ('cuenta302_01_001_lmmr', 1388, 'xiuman_data', 'account.account', TRUE),
    ('cuenta302_01_002_lmmr', 1389, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_001_lmmr', 1390, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_002_lmmr', 1391, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_001_lmmr', 1392, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_002_lmmr', 1393, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_001_lmmr', 1394, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_002_lmmr', 1395, 'xiuman_data', 'account.account', TRUE),
    ('cuenta101_01_001_tjgl', 1396, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_001_tjgl', 1397, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_003_tjgl', 1398, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_004_tjgl', 1399, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_005_tjgl', 1400, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_001_tjgl', 1401, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_002_tjgl', 1402, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_001_tjgl', 1403, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_002_tjgl', 1404, 'xiuman_data', 'account.account', TRUE),
    ('cuenta208_01_001_tjgl', 1405, 'xiuman_data', 'account.account', TRUE),
    ('cuenta209_01_001_tjgl', 1406, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_05_001_tjgl', 1407, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_01_001_tjgl', 1408, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_002_tjgl', 1409, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_111_tjgl', 1410, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_01_001_tjgl', 1411, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_02_001_tjgl', 1412, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_001_tjgl', 1413, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_002_tjgl', 1414, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_01_001_tjgl', 1415, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_03_001_tjgl', 1416, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_01_001_tjgl', 1417, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_03_001_tjgl', 1418, 'xiuman_data', 'account.account', TRUE),
    ('cuenta151_01_001_tjgl', 1419, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_001_tjgl', 1420, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_002_tjgl', 1421, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_06_001_tjgl', 1422, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_08_001_tjgl', 1423, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_84_002_tjgl', 1424, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_32_001_tjgl', 1425, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_49_001_tjgl', 1426, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_50_001_tjgl', 1427, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_52_001_tjgl', 1428, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_52_002_tjgl', 1429, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_55_001_tjgl', 1430, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_56_001_tjgl', 1431, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_57_001_tjgl', 1432, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_01_001_tjgl', 1433, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_10_001_tjgl', 1434, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_002_tjgl', 1435, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_003_tjgl', 1436, 'xiuman_data', 'account.account', TRUE),
    ('cuenta899_01_099_tjgl', 1437, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_001_tjgl', 1438, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_002_tjgl', 1439, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_22_002_tjgl', 1440, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_38_002_tjgl', 1441, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_01_001_tjgl', 1442, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_03_001_tjgl', 1443, 'xiuman_data', 'account.account', TRUE),
    ('cuenta702_01_001_tjgl', 1444, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_22_001_tjgl', 1445, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_002_tjgl', 1446, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_001_tjgl', 1447, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_002_tjgl', 1448, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_001_tjgl', 1449, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_002_tjgl', 1450, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_001_tjgl', 1451, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_002_tjgl', 1452, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_02_001_tjgl', 1453, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_02_002_tjgl', 1454, 'xiuman_data', 'account.account', TRUE),
    ('cuenta101_01_001_glmm', 1455, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_002_glmm', 1456, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_003_glmm', 1457, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_004_glmm', 1458, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_001_glmm', 1459, 'xiuman_data', 'account.account', TRUE),
    ('cuenta105_01_002_glmm', 1460, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_001_glmm', 1461, 'xiuman_data', 'account.account', TRUE),
    ('cuenta201_01_002_glmm', 1462, 'xiuman_data', 'account.account', TRUE),
    ('cuenta210_01_001_glmm', 1463, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_01_001_glmm', 1464, 'xiuman_data', 'account.account', TRUE),
    ('cuenta213_03_001_glmm', 1465, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_01_001_glmm', 1466, 'xiuman_data', 'account.account', TRUE),
    ('cuenta216_04_001_glmm', 1467, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_000_glmm', 1468, 'xiuman_data', 'account.account', TRUE),
    ('cuenta102_01_111_glmm', 1469, 'xiuman_data', 'account.account', TRUE),
    ('cuenta109_01_001_glmm', 1470, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_01_001_glmm', 1471, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_02_001_glmm', 1472, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_06_001_glmm', 1473, 'xiuman_data', 'account.account', TRUE),
    ('cuenta113_08_001_glmm', 1474, 'xiuman_data', 'account.account', TRUE),
    ('cuenta114_01_001_glmm', 1475, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_001_glmm', 1476, 'xiuman_data', 'account.account', TRUE),
    ('cuenta115_01_002_glmm', 1477, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_01_001_glmm', 1478, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_01_002_glmm', 1479, 'xiuman_data', 'account.account', TRUE),
    ('cuenta118_03_001_glmm', 1480, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_01_001_glmm', 1481, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_01_002_glmm', 1482, 'xiuman_data', 'account.account', TRUE),
    ('cuenta119_03_001_glmm', 1483, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_001_glmm', 1484, 'xiuman_data', 'account.account', TRUE),
    ('cuenta501_01_002_glmm', 1485, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_01_001_glmm', 1486, 'xiuman_data', 'account.account', TRUE),
    ('cuenta601_83_001_glmm', 1487, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_01_001_glmm', 1488, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_26_001_glmm', 1489, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_34_001_glmm', 1490, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_48_001_glmm', 1491, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_49_001_glmm', 1492, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_50_001_glmm', 1493, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_56_001_glmm', 1494, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_57_001_glmm', 1495, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_58_001_glmm', 1496, 'xiuman_data', 'account.account', TRUE),
    ('cuenta602_72_001_glmm', 1497, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_101_001_glmm', 1498, 'xiuman_data', 'account.account', TRUE),
    ('cuenta603_101_002_glmm', 1499, 'xiuman_data', 'account.account', TRUE),
    ('cuenta611_01_001_glmm', 1500, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_01_001_glmm', 1501, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_04_001_glmm', 1502, 'xiuman_data', 'account.account', TRUE),
    ('cuenta701_10_001_glmm', 1503, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_001_glmm', 1504, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_002_glmm', 1505, 'xiuman_data', 'account.account', TRUE),
    ('cuenta703_21_003_glmm', 1506, 'xiuman_data', 'account.account', TRUE),
    ('cuenta899_01_099_glmm', 1507, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_01_001_glmm', 1508, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_001_glmm', 1510, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_002_glmm', 1511, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_010_glmm', 1513, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_011_glmm', 1509, 'xiuman_data', 'account.account', TRUE),
    ('cuenta401_04_012_glmm', 1582, 'xiuman_data', 'account.account', TRUE),
    ('cuenta503_01_004_glmm', 1517, 'xiuman_data', 'account.account', TRUE),
    ('cuenta702_01_001_glmm', 1518, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_22_001_glmm', 1519, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_001_glmm', 1520, 'xiuman_data', 'account.account', TRUE),
    ('cuenta704_23_002_glmm', 1521, 'xiuman_data', 'account.account', TRUE),
    ('cuenta302_01_001_glmm', 1522, 'xiuman_data', 'account.account', TRUE),
    ('cuenta302_01_002_glmm', 1523, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_001_glmm', 1524, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_01_002_glmm', 1525, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_001_glmm', 1526, 'xiuman_data', 'account.account', TRUE),
    ('cuenta304_02_002_glmm', 1527, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_001_glmm', 1528, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_01_002_glmm', 1529, 'xiuman_data', 'account.account', TRUE),
    ('cuenta305_02_001_glmm', 1530, 'xiuman_data', 'account.account', TRUE),
    ('data_res_partner_user1', 202, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user2', 203, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user3', 204, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user4', 205, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user5', 206, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user6', 207, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user7', 208, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user8', 209, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user9', 210, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user10', 211, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user11', 212, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user12', 213, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user13', 214, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user14', 215, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user15', 216, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user16', 217, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user17', 218, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user18', 219, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user19', 220, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user20', 221, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user21', 222, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user22', 223, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user23', 224, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user24', 225, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user25', 226, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user26', 227, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user27', 228, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user28', 229, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user29', 230, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user30', 5754, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user31', 5753, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user32', 5852, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_partner_user33', 5816, 'xiuman_data', 'res.partner', TRUE),
    ('data_res_users_user_1', 102, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_2', 103, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_3', 104, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_4', 105, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_5', 106, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_6', 107, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_7', 108, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_8', 109, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_9', 110, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_10', 111, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_11', 112, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_12', 113, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_13', 114, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_14', 115, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_15', 116, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_16', 117, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_17', 118, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_18', 119, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_19', 120, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_20', 121, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_21', 122, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_22', 123, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_23', 124, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_24', 125, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_25', 126, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_26', 127, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_27', 128, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_28', 129, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_29', 130, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_30', 131, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_31', 132, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_32', 137, 'xiuman_data', 'res.users', TRUE),
    ('data_res_users_user_33', 139, 'xiuman_data', 'res.users', TRUE);

-- Renamed fields

ALTER TABLE res_partner ADD COLUMN birthdate date;
UPDATE res_partner SET birthdate = birthdate_date;
ALTER TABLE res_partner DROP COLUMN IF EXISTS birthdate_date;
