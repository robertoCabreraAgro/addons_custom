def enable_multi_locations(env):
    ResConfig = env["res.config.settings"]
    default_values = ResConfig.default_get(list(ResConfig.fields_get()))
    default_values.update({"group_stock_multi_locations": True})
    ResConfig.create(default_values).execute()
