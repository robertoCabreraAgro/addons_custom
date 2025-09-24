import {domainFromTreeDateRange, treeFromDomainDateRange} from "./condition_tree.esm";
import {onWillStart, onWillUpdateProps} from "@odoo/owl";
import {Domain} from "@web/core/domain";
import {DomainSelector} from "@web/core/domain_selector/domain_selector";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

const ARCHIVED_DOMAIN = `[("active", "in", [True, False])]`;

patch(DomainSelector.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");

        // Only initialize services if they exist in Odoo 19.0
        try {
            this.fieldService = useService("field");
            this.treeProcessor = useService("tree_processor");
        } catch (e) {
            console.warn("Some services not available, using fallback:", e);
        }

        this.dateRanges = [];
        this.dateRangeTypes = [];

        onWillStart(async () => {
            try {
                this.dateRanges = await this.orm.searchRead(
                    "date.range",
                    [],
                    ["id", "name", "date_start", "date_end", "type_id"]
                );
                this.dateRangeTypes = await this.orm.searchRead(
                    "date.range.type",
                    [],
                    ["id", "name", "date_ranges_exist"]
                );
            } catch (error) {
                console.warn("Failed to load date ranges:", error);
                this.dateRanges = [];
                this.dateRangeTypes = [];
            }
        });
    },

    async onPropsUpdated(p) {
        await super.onPropsUpdated.apply(this, arguments);

        let domain = null;
        let isSupported = true;

        try {
            domain = new Domain(p.domain);
        } catch {
            isSupported = false;
        }

        if (!isSupported) {
            this.tree = null;
            this.showArchivedCheckbox = false;
            this.includeArchived = false;
            return;
        }

        try {
            // Try to use tree processor service if available
            let tree;
            if (this.treeProcessor) {
                tree = await this.treeProcessor.treeFromDomain(
                    p.resModel,
                    domain,
                    !p.isDebugMode
                );
            } else {
                // Fallback to direct import
                const { treeFromDomain } = await import("@web/core/tree_editor/tree_from_domain");
                tree = treeFromDomain(domain, { distributeNot: !p.isDebugMode });
            }

            // Apply date range transformation
            this.tree = treeFromDomainDateRange(domain, {
                getFieldDef: (path) => {
                    // Try to get field definition
                    if (this.fieldService) {
                        return this.fieldService.getFieldDef(p.resModel, path);
                    }
                    // Fallback: return basic field info
                    return { name: path, type: "char" };
                },
                distributeNot: !p.isDebugMode,
            });
        } catch (error) {
            console.warn("Failed to process domain:", error);
            // Try basic fallback
            this.tree = null;
        }
    },
    getOperatorEditorInfo(fieldDef) {
        const info = super.getOperatorEditorInfo(fieldDef);
        const dateRanges = this.dateRanges;
        const dateRangeTypes = this.dateRangeTypes.filter((dt) => dt.date_ranges_exist);
        patch(info, {
            extractProps({value: [operator]}) {
                const props = super.extractProps.apply(this, arguments);
                const isDateField =
                    fieldDef &&
                    (fieldDef.type === "date" || fieldDef.type === "datetime");
                const hasDateRanges = isDateField && dateRanges.length;
                const hasDateRangeTypes = isDateField && dateRangeTypes.length;

                if (hasDateRanges) {
                    if (operator.includes("daterange")) {
                        props.options.pop();
                    }
                    if (operator === "daterange") {
                        props.value = "daterange";
                    }
                    props.options.push(["daterange", "daterange"]);
                }

                if (hasDateRangeTypes) {
                    const selectedDateRange = dateRangeTypes.find(
                        (rangeType) =>
                            rangeType.id === Number(operator.split("daterange_")[1])
                    );

                    if (selectedDateRange) {
                        props.value = operator;
                    }

                    props.options.push(
                        ...dateRangeTypes.map((rangeType) => [
                            `daterange_${rangeType.id}`,
                            `in ${rangeType.name}`,
                        ])
                    );
                }

                return props;
            },
        });
        return info;
    },
    update(tree) {
        const archiveDomain = this.includeArchived ? ARCHIVED_DOMAIN : `[]`;
        const domain = tree
            ? Domain.and([domainFromTreeDateRange(tree), archiveDomain]).toString()
            : archiveDomain;
        this.props.update(domain);
    },
});
