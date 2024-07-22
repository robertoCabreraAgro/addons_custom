from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    set_vehicle_fuel_card(cr)
    set_vehicle_highway_pass(cr)


def set_vehicle_fuel_card(cr):
    """Set the fuel cards to corresponding vehicles."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    vehicle_obj = env["fleet.vehicle"]
    tag = env.ref("marin.documents_fleet_fuel_card")
    fuel_cards = env["documents.document"].search([("tag_ids", "in", tag.ids), ("res_model", "=", "fleet.vehicle")])
    for fuel_card in fuel_cards:
        vehicle = vehicle_obj.browse(fuel_card.res_id)
        if vehicle:
            vehicle.write({"fuel_card_id": fuel_card.id})


def set_vehicle_highway_pass(cr):
    """Set the highway pass to corresponding vehicles."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    vehicle_obj = env["fleet.vehicle"]
    tag = env.ref("marin.documents_fleet_highway_pass")
    highway_pass = env["documents.document"].search([("tag_ids", "in", tag.ids), ("res_model", "=", "fleet.vehicle")])
    for hp in highway_pass:
        vehicle = vehicle_obj.browse(hp.res_id)
        if vehicle:
            vehicle.write({"highway_pass_id": hp.id})
