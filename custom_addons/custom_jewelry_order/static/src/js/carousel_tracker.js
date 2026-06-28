/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { rpc } from "@web/core/network/rpc";

/**
 * Tracks how customers engage with the design-showcase carousel on the
 * portal order page. Every time a slide becomes active (auto-advance,
 * next/prev click, or swipe), we log it so the back office can see which
 * collections and slides actually get viewed.
 */
publicWidget.registry.JewelryCarouselTracker = publicWidget.Widget.extend({
    selector: ".js_jewelry_carousel",

    start() {
        this._onSlide = this._onSlide.bind(this);
        this.el.addEventListener("slid.bs.carousel", this._onSlide);
        return this._super(...arguments);
    },

    destroy() {
        if (this.el) {
            this.el.removeEventListener("slid.bs.carousel", this._onSlide);
        }
        this._super(...arguments);
    },

    _onSlide(ev) {
        const collectionId = this.el.dataset.collectionId;
        const orderToken = this.el.dataset.orderToken;
        if (!collectionId || !orderToken) {
            return;
        }
        const slideIndex = ev.to !== undefined ? ev.to : 0;
        // Fire-and-forget: tracking must never disrupt the visitor experience.
        rpc("/jewelry/track_carousel", {
            collection_id: collectionId,
            slide_index: slideIndex,
            order_token: orderToken,
        }).catch(() => {});
    },
});

export default publicWidget.registry.JewelryCarouselTracker;
