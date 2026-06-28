/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";

/**
 * Definition of every chart shown on the jewelry analytics dashboard.
 * Each entry points at an existing graph view (by XML id) so the dashboard
 * reuses the exact charts configured in the view files.
 */
const DASHBOARD_CHARTS = [
    { key: "pipeline", title: "Order Pipeline", model: "custom.jewelry.order", view: "view_jewelry_order_graph_pipeline" },
    { key: "customer", title: "Orders by Customer", model: "custom.jewelry.order", view: "view_jewelry_order_graph_customer" },
    { key: "manufacturer", title: "Orders by Manufacturer", model: "custom.jewelry.order", view: "view_custom_jewelry_order_graph" },
    { key: "item_type", title: "Orders by Item Type", model: "custom.jewelry.order", view: "view_jewelry_order_graph_item_type" },
    { key: "seal", title: "Seal & Melting Mix", model: "custom.jewelry.order", view: "view_jewelry_order_graph_seal" },
    { key: "trend", title: "Monthly Trend", model: "custom.jewelry.order", view: "view_jewelry_order_graph_trend" },
    { key: "visits", title: "Portal Visits Over Time", model: "jewelry.order.visit", view: "view_jewelry_order_visit_graph" },
    { key: "engagement", title: "Visits by Customer", model: "jewelry.order.visit", view: "view_jewelry_order_visit_graph_partner" },
    { key: "showcase", title: "Design Showcase Views", model: "jewelry.carousel.interaction", view: "view_jewelry_carousel_interaction_graph" },
];

export class JewelryAnalyticsDashboard extends Component {
    static template = "custom_jewelry_order.AnalyticsDashboard";
    static components = { View };
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.state = useState({ charts: [] });

        onWillStart(async () => {
            // Resolve the graph view XML ids to their database ids in one call.
            const names = DASHBOARD_CHARTS.map((c) => c.view);
            const data = await this.orm.searchRead(
                "ir.model.data",
                [
                    ["module", "=", "custom_jewelry_order"],
                    ["model", "=", "ir.ui.view"],
                    ["name", "in", names],
                ],
                ["name", "res_id"]
            );
            const idByName = Object.fromEntries(data.map((d) => [d.name, d.res_id]));
            this.state.charts = DASHBOARD_CHARTS
                .map((c) => ({ ...c, viewId: idByName[c.view] }))
                .filter((c) => c.viewId);
        });
    }

    getViewProps(chart) {
        return {
            type: "graph",
            resModel: chart.model,
            viewId: chart.viewId,
            display: { controlPanel: false },
        };
    }
}

registry.category("actions").add("jewelry_analytics_dashboard", JewelryAnalyticsDashboard);
