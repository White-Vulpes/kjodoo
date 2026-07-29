/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";
import { KanbanRecord, CANCEL_GLOBAL_CLICK } from "@web/views/kanban/kanban_record";

/**
 * Card (kanban) picker for choosing jewelry designs by photo.
 *
 * A field opts in with:
 *   context="{'force_dialog_view_type': 'kanban'}"
 *
 * Two scoped patches, both inert unless that flag is present:
 *
 *  1. SelectCreateDialog normally opens as a LIST on desktop. We flip it to
 *     the kanban (card) view so staff recognise pieces by their image.
 *
 *  2. In that card picker a single click normally *picks one design and
 *     closes*. Here we want plain multi-select: every click just toggles the
 *     card in/out of the selection, and the footer "Select" button confirms
 *     the whole batch. No selection-mode toggle to hunt for.
 */
patch(SelectCreateDialog.prototype, {
    get viewProps() {
        const props = super.viewProps;
        const forced = this.props.context && this.props.context.force_dialog_view_type;
        if (forced && !this.env.isSmall && props.type !== forced) {
            props.type = forced;
            if (forced === "kanban") {
                props.forceGlobalClick = true;
                delete props.allowSelectors;
                delete props.allowOpenAction;
            }
        }
        return props;
    },
});

patch(KanbanRecord.prototype, {
    onGlobalClick(ev) {
        const ctx = this.props.record && this.props.record.context;
        if (ctx && ctx.force_dialog_view_type === "kanban") {
            // Ignore clicks on inner links / action buttons.
            if (ev.target.closest(CANCEL_GLOBAL_CLICK)) {
                return;
            }
            // Plain toggle — click to add, click again to remove.
            ev.stopPropagation();
            ev.preventDefault();
            this.props.toggleSelection(this.props.record, ev.shiftKey);
            return;
        }
        return super.onGlobalClick(...arguments);
    },
});
