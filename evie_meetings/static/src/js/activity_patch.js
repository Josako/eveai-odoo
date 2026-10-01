/** @odoo-module */

/**
 * "Meeting window" button on Meeting and Call activities in the chatter
 * (odoo-meeting-window). Only shown once the activity is linked to its Evie
 * capsule (x_evie_capsule_id, sent along by _to_store_defaults), since
 * recordings and notes are stored on that capsule.
 */

import { Activity } from "@mail/core/web/activity";
import { patch } from "@web/core/utils/patch";
import { openMeetingWindow } from "./meeting_window";

const MEETING_CATEGORIES = ["meeting", "phonecall"];

patch(Activity.prototype, {
    get hasEvieMeetingWindow() {
        const activity = this.props.activity;
        return Boolean(activity.x_evie_capsule_id) && MEETING_CATEGORIES.includes(activity.activity_category);
    },

    openEvieMeetingWindow() {
        const activity = this.props.activity;
        openMeetingWindow(this.env.services.action, activity.id, activity.summary || activity.display_name);
    },
});
