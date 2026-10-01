/** @odoo-module */

/**
 * Recording indicator in the systray (odoo-meeting-window): visible while a
 * meeting is being recorded or uploaded, so a recording that keeps running
 * across navigation is never forgotten. Clicking it reopens the meeting
 * window of the activity being recorded.
 */

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { formatElapsed, openMeetingWindow } from "./meeting_window";

export class MeetingRecordingIndicator extends Component {
    static template = "evie_meetings.MeetingRecordingIndicator";
    static props = {};

    setup() {
        this.action = useService("action");
        this.recorder = useService("evie_meeting_recorder");
        this.state = useState(this.recorder.state);
    }

    get visible() {
        return this.state.phase === "recording" || this.state.phase === "uploading";
    }

    get elapsed() {
        return formatElapsed(this.state.elapsedSec);
    }

    onClick() {
        if (this.state.activityId) {
            openMeetingWindow(this.action, this.state.activityId);
        }
    }
}

registry
    .category("systray")
    .add("evie_meetings.recording_indicator", { Component: MeetingRecordingIndicator }, { sequence: 24 });
