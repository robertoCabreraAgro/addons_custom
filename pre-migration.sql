-- Delete all module categories to avoid errors due to their unique constraints
-- DELETE FROM ir_module_category;

-- DELETE FROM
--     ir_model_data
-- WHERE
--     model = 'ir.module.category';

-- Delete Record rules to avoid possible access errors during migration
-- DELETE FROM ir_rule;

-- DELETE FROM
--     ir_model_data
-- WHERE
--     model = 'ir.rule';

-- Delete menus that are causing trouble during migration

WITH deleted_extid AS (
    DELETE FROM
        ir_model_data
    WHERE
        model = 'ir.ui.menu'
        AND (
            (
                module = 'project_agriculture'
                AND name = 'menu_pdws'
            ) OR
            (
                module = 'project_agriculture'
                AND name = 'menu_crops'
            ) OR
            (
                module = 'project_agriculture'
                AND name = 'menu_lands'
            ) OR
            (
                module = 'project_agriculture'
                AND name = 'child_lands'
            ) OR
            (
                module = 'project_agriculture'
                AND name = 'menu_projects'
            ) OR
            (
                module = 'project_agriculture'
                AND name = 'menu_livestock'
            ) OR
            (
                module = 'stock'
                AND name = 'stock_picking_type_menu'
            ) OR
            (
                module = 'droggol_theme_common'
                AND name = 'menu_dr_product_brand_values'
            ) OR
            (
                module = 'droggol_theme_common'
                AND name = 'menu_dr_website_content'
            ) OR
            (
                module = 'base_geoengine'
                AND name = 'geoengine_vector_layer_menu'
            ) OR
            (
                module = 'l10n_mx_edi_payslip'
                AND name = 'l10n_mx_overtime'
            )
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
