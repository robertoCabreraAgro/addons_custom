import { registry } from "@web/core/registry";
import { EstateOwlWidget } from "@estate_owl/js/estate_widget";

// Registrar el client action
registry.category("actions").add("estate_owl_widget", EstateOwlWidget);

console.log("Estate OWL client action registered");
