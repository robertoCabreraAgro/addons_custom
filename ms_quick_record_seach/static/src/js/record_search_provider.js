/**
 * Command Palette Record Search Provider
 */
import { registry } from "@web/core/registry";
import { DefaultCommandItem } from "@web/core/commands/command_palette";

const commandProviderRegistry = registry.category("command_provider");

commandProviderRegistry.add("record_search", {
  namespace: "/",
  async provide(env, options = {}) {
    const searchValue = options.searchValue || "";
    const match = searchValue.match(/^([\w\.]+)(?:\s+(.*))?$/);
    if (!match) {
      return [];
    }
    const model = match[1];
    const term = (match[2] || "").trim();
    let results = [];
    try {
      results = await env.services.orm.call(
        "quick.record.search",
        "record_search",
        [model, term]
      );
    } catch (e) {
      console.error("Error fetching records:", e);
    }
    return results.map((rec) => ({
      Component: DefaultCommandItem,
      action: () => {
        env.services.action.doAction({
          type: "ir.actions.act_window",
          res_model: model,
          res_id: rec.id,
          view_mode: "form",
          views: [[false, "form"]],
          target: "current",
        });
      },
      category: "default",
      name: rec.name,
    }));
  },
});
