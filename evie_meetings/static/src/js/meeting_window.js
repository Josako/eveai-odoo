/** @odoo-module */

/**
 * Meeting window (odoo-meeting-window): the "cockpit" of one Meeting or Call
 * activity — details and preparation, participants, recording, and notes — opened from the
 * activity in the chatter or via /odoo/evie-meeting/<activity id> (the link
 * in the activity's "done" message).
 *
 * Details come from Odoo; recordings, transcripts and notes live in Evie and
 * are reached through the evie_meeting_* methods on mail.activity. Recording
 * itself is done by the evie_meeting_recorder service so it survives leaving
 * this window.
 *
 * Notes: every save creates a new notes version in Evie, so the window keeps
 * a draft in localStorage on every keystroke and only saves to Evie after a
 * pause in typing, on blur, when leaving the window, or on "Save".
 */

import { Component, markup, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import {
    deserializeDate,
    deserializeDateTime,
    formatDate,
    formatDateTime,
} from "@web/core/l10n/dates";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { errorMessage } from "./meeting_recorder_service";

const { DateTime } = luxon;

const MODEL = "mail.activity";
const ACTION_TAG = "evie_meetings.meeting_window";
const POLL_INTERVAL_MS = 5000;
const NOTES_AUTOSAVE_MS = 10000;
const DRAFT_KEY_PREFIX = "evie_meetings.notes_draft.";
const PLAN_POLL_INTERVAL_MS = 3000;
const PLAN_POLL_MAX = 30; // ~90s for the composed plan mirrors to land

export function formatElapsed(totalSec) {
    const sec = Math.max(0, Math.floor(totalSec || 0));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = String(sec % 60).padStart(2, "0");
    return h ? `${h}:${String(m).padStart(2, "0")}:${s}` : `${m}:${s}`;
}

/**
 * One live note as a markdown list item stamped with its recording time.
 * Same format as the Workspace client's formatLiveNote (workspace-meetings.js).
 */
export function formatLiveNote(atSec, text) {
    const [first, ...rest] = String(text).trim().split("\n");
    return `- **[${formatElapsed(atSec)}]** ${first}${rest.map((part) => `  \n  ${part}`).join("")}`;
}

export function openMeetingWindow(actionService, activityId, name) {
    return actionService.doAction({
        type: "ir.actions.client",
        tag: ACTION_TAG,
        name: name || _t("Meeting"),
        params: { resId: activityId },
    });
}

/** Headings and paragraphs of a markdown transcript, rendered as text (no HTML). */
function transcriptBlocks(markdown) {
    const blocks = [];
    let paragraph = [];
    const flush = () => {
        if (paragraph.length) {
            blocks.push({ type: "text", text: paragraph.join("\n") });
            paragraph = [];
        }
    };
    for (const line of (markdown || "").split("\n")) {
        const heading = line.match(/^#{1,6}\s+(.*)$/);
        if (heading) {
            flush();
            blocks.push({ type: "heading", text: heading[1].replace(/\*\*/g, "") });
        } else if (!line.trim()) {
            flush();
        } else {
            paragraph.push(line.replace(/\*\*/g, ""));
        }
    }
    flush();
    return blocks.map((block, index) => ({ ...block, id: index }));
}

/**
 * Case-insensitive whole-word matches, the same rule Evie replaces with.
 * Same as the Workspace client's transcriptMatchRegex (workspace-meetings.js).
 */
function transcriptMatchRegex(find) {
    const term = String(find || "").trim();
    if (!term) {
        return null;
    }
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return new RegExp(`(?<![\\p{L}\\p{N}_])${escaped}(?![\\p{L}\\p{N}_])`, "giu");
}

/** `text` split into [{text, match}] parts; `match` is the 0-based occurrence index or -1. */
function splitTranscriptMatches(text, regex) {
    const source = String(text || "");
    if (!regex) {
        return [{ text: source, match: -1 }];
    }
    const parts = [];
    let last = 0;
    let index = 0;
    for (const found of source.matchAll(regex)) {
        if (found.index > last) {
            parts.push({ text: source.slice(last, found.index), match: -1 });
        }
        parts.push({ text: found[0], match: index++ });
        last = found.index + found[0].length;
    }
    if (last < source.length) {
        parts.push({ text: source.slice(last), match: -1 });
    }
    return parts;
}

function base64ToBlob(base64, mimeType) {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    return new Blob([bytes], { type: mimeType });
}

export class MeetingWindow extends Component {
    static template = "evie_meetings.MeetingWindow";
    static props = ["*"];
    static path = "evie-meeting";
    static displayName = _t("Meeting");

    static extractProps(action) {
        return { resId: action.params?.resId || action.context?.active_id };
    }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.recorder = useService("evie_meeting_recorder");
        this.recorderState = useState(this.recorder.state);

        this.activityId = parseInt(this.props.resId, 10) || false;
        this.draftKey = `${DRAFT_KEY_PREFIX}${this.activityId}`;
        this.state = useState({
            loading: true,
            error: "",
            activity: null,
            recordings: [],
            evieError: "",
            selectedId: false,
            audioUrls: {},
            transcripts: {},
            transcribing: {},
            savingSpeakers: false,
            notes: "",
            notesSaved: "",
            notesStatus: "saved", // saved | dirty | saving | error
            notesError: "",
            draftRestored: false,
            participants: [],
            participantsSupported: true,
            participantsReason: "",
            participantsSaving: false,
            participantsError: "",
            participantForm: null,
            documentTypes: [],
            notesDocument: { id: false, type: "", label: "" },
            savingType: {},
            // Meeting plan (add-odoo-meeting-library-sync): local mirrors
            plan: null,
            planTemplates: [],
            planPickerOpen: false,
            planComposing: false,
            planPollCount: 0,
            objectiveForm: null, // {label, objective_type, intent, success_criterion}
            objectiveError: "",
            repNotes: {}, // objective id -> edited note (until saved)
            repNoteStatus: {}, // objective id -> "saving" | "error" | ""
            liveDraft: "",
            liveDraftAt: null,
            find: "",
            replaceWith: "",
            matchIndex: 0,
            replacing: false,
            transcriptStatus: "",
            transcriptStatusError: false,
            speaking: null, // { documentId, segment, loading }
        });
        this.pollTimer = null;
        this.notesTimer = null;
        this.planPollTimer = null;
        this.liveInput = useRef("liveNoteInput");
        this.transcriptList = useRef("transcriptList");
        this.speechUrls = new Map();
        this.speechAudio = null;
        this.speechToken = 0;

        onWillStart(() => this.load());
        onWillUnmount(() => {
            browser.clearTimeout(this.pollTimer);
            browser.clearTimeout(this.notesTimer);
            browser.clearTimeout(this.planPollTimer);
            this.stopSpeaking();
            this.clearSpeechCache();
            this.commitLiveNote();
            if (this.state.notesStatus === "dirty") {
                this.saveNotes();
            }
        });
        useEffect(
            (uploadCount) => {
                if (uploadCount && this.recorderState.lastUploadActivityId === this.activityId) {
                    this.refreshRecordings({ selectNewest: true });
                }
            },
            () => [this.recorderState.uploadCount]
        );
        useEffect(
            (active) => {
                if (active) {
                    this.liveInput.el?.focus();
                }
            },
            () => [this.liveNotesActive]
        );
    }

    // ------------------------------------------------------------------
    // Loading
    // ------------------------------------------------------------------

    async load() {
        if (!this.activityId) {
            this.state.error = _t("No activity was given to open.");
            this.state.loading = false;
            return;
        }
        try {
            const data = await this.orm.silent.call(MODEL, "evie_meeting_window_data", [
                [this.activityId],
            ]);
            this.state.activity = data.activity;
            this.state.evieError = data.evie_error || "";
            this.applyPlan(data.plan || { plan: false, templates: [] });
            if (data.evie) {
                this.applyOverview(data.evie, { selectNewest: true });
                this.initNotes(data.evie.notes?.content || "");
            } else {
                this.initNotes("");
            }
            this.env.config?.setDisplayName?.(this.title);
        } catch (error) {
            this.state.error = errorMessage(error);
        } finally {
            this.state.loading = false;
        }
    }

    initNotes(savedContent) {
        const draft = browser.localStorage.getItem(this.draftKey);
        this.state.notesSaved = savedContent;
        if (draft !== null && draft !== savedContent) {
            this.state.notes = draft;
            this.state.notesStatus = "dirty";
            this.state.draftRestored = true;
        } else {
            this.state.notes = savedContent;
            browser.localStorage.removeItem(this.draftKey);
        }
    }

    applyOverview(overview, { selectNewest = false } = {}) {
        if (overview.participants && !this.state.participantsSaving) {
            this.applyParticipants(overview.participants);
        }
        this.state.documentTypes = overview.document_types || [];
        if (overview.notes) {
            this.applyNotesDocument(overview.notes);
        }
        const recordings = overview.recordings || [];
        const previous = new Map(this.state.recordings.map((r) => [r.document_id, r]));
        this.state.recordings = recordings;
        const ids = recordings.map((r) => r.document_id);
        if (selectNewest || !ids.includes(this.state.selectedId)) {
            this.state.selectedId = ids[0] || false;
        }
        for (const recording of recordings) {
            const before = previous.get(recording.document_id);
            if (before && !before.has_transcript && recording.has_transcript) {
                delete this.state.transcripts[recording.document_id];
            }
        }
        this.ensureSelectedLoaded();
        this.schedulePoll();
    }

    async refreshRecordings(options = {}) {
        try {
            const overview = await this.orm.silent.call(MODEL, "evie_meeting_overview", [
                [this.activityId],
            ]);
            this.state.evieError = "";
            this.applyOverview(overview, options);
        } catch (error) {
            this.state.evieError = errorMessage(error);
        }
    }

    schedulePoll() {
        browser.clearTimeout(this.pollTimer);
        if (this.state.recordings.some((r) => r.processing)) {
            this.pollTimer = browser.setTimeout(() => this.refreshRecordings(), POLL_INTERVAL_MS);
        }
    }

    // ------------------------------------------------------------------
    // Meeting plan (local mirrors; edits flow back via the mirror sync)
    // ------------------------------------------------------------------

    applyPlan(payload) {
        this.state.plan = payload.plan || null;
        this.state.planTemplates = payload.templates || [];
        if (this.state.plan) {
            this.state.planComposing = false;
            browser.clearTimeout(this.planPollTimer);
            const notes = {};
            for (const objective of this.state.plan.objectives) {
                if (!(objective.id in this.state.repNotes)) {
                    notes[objective.id] = objective.rep_note;
                }
            }
            Object.assign(this.state.repNotes, notes);
        }
    }

    async refreshPlan() {
        try {
            const payload = await this.orm.silent.call(MODEL, "evie_meeting_plan_data", [
                [this.activityId],
            ]);
            this.applyPlan(payload);
        } catch (error) {
            // A failed refresh never breaks the window; the next poll retries.
        }
    }

    schedulePlanPoll() {
        browser.clearTimeout(this.planPollTimer);
        if (!this.state.planComposing || this.state.plan) {
            return;
        }
        if (this.state.planPollCount >= PLAN_POLL_MAX) {
            this.state.planComposing = false;
            this.notification.add(
                _t("The plan is taking longer than expected to arrive. It will appear after the next synchronisation."),
                { type: "warning" }
            );
            return;
        }
        this.planPollTimer = browser.setTimeout(async () => {
            this.state.planPollCount += 1;
            await this.refreshPlan();
            this.schedulePlanPoll();
        }, PLAN_POLL_INTERVAL_MS);
    }

    async composePlan(templateMirrorId) {
        this.state.planPickerOpen = false;
        this.state.planComposing = true;
        this.state.planPollCount = 0;
        try {
            await this.orm.call(MODEL, "evie_meeting_compose_plan", [
                [this.activityId],
                templateMirrorId || false,
            ]);
            this.schedulePlanPoll();
        } catch (error) {
            this.state.planComposing = false;
            this.notification.add(errorMessage(error), { type: "danger" });
        }
    }

    openObjectiveForm() {
        this.state.objectiveForm = {
            label: "",
            objective_type: "INFORMATION",
            intent: "",
            success_criterion: "",
        };
        this.state.objectiveError = "";
    }

    async saveObjectiveForm() {
        const form = this.state.objectiveForm;
        if (!form.label.trim() || !form.intent.trim() || !form.success_criterion.trim()) {
            this.state.objectiveError = _t("Label, intent and success criterion are required.");
            return;
        }
        try {
            await this.orm.create("meeting.objective", [{
                name: form.label.trim(),
                objective_type: form.objective_type,
                intent: form.intent.trim(),
                success_criterion: form.success_criterion.trim(),
                plan_id: this.state.plan.id,
            }]);
            this.state.objectiveForm = null;
            this.notification.add(
                _t("Ad-hoc objective added — it syncs to Evie in the background."),
                { type: "success" }
            );
            await this.refreshPlan();
        } catch (error) {
            this.state.objectiveError = errorMessage(error);
        }
    }

    async removeObjective(objective) {
        try {
            await this.orm.call("meeting.objective", "action_archive", [[objective.id]]);
            delete this.state.repNotes[objective.id];
            await this.refreshPlan();
        } catch (error) {
            this.notification.add(errorMessage(error), { type: "danger" });
        }
    }

    repNoteValue(objective) {
        return objective.id in this.state.repNotes
            ? this.state.repNotes[objective.id]
            : objective.rep_note;
    }

    onRepNoteInput(objective, ev) {
        this.state.repNotes[objective.id] = ev.target.value;
    }

    async saveRepNote(objective) {
        const value = this.repNoteValue(objective);
        if (value === objective.rep_note) {
            return;
        }
        this.state.repNoteStatus[objective.id] = "saving";
        try {
            await this.orm.write("meeting.objective", [objective.id], { rep_note: value });
            this.state.repNoteStatus[objective.id] = "";
            objective.rep_note = value;
        } catch (error) {
            this.state.repNoteStatus[objective.id] = "error";
            this.notification.add(errorMessage(error), { type: "danger" });
        }
    }

    get objectiveTypeLabels() {
        return {
            INFORMATION: _t("Information"),
            COMMITMENT: _t("Commitment"),
            PERCEPTION: _t("Perception"),
            RELATIONSHIP: _t("Relationship"),
        };
    }

    priorityBadgeClass(priority) {
        return {
            LOW: "text-bg-secondary",
            MEDIUM: "text-bg-info",
            HIGH: "text-bg-warning",
            CRITICAL: "text-bg-danger",
        }[priority] || "text-bg-secondary";
    }

    // ------------------------------------------------------------------
    // Details
    // ------------------------------------------------------------------

    get title() {
        const activity = this.state.activity;
        return activity ? activity.summary || activity.type_name || _t("Meeting") : _t("Meeting");
    }

    get isCall() {
        return this.state.activity?.category === "phonecall";
    }

    get stateBadge() {
        const labels = {
            done: [_t("Done"), "text-bg-secondary"],
            overdue: [_t("Overdue"), "text-bg-danger"],
            today: [_t("Today"), "text-bg-warning"],
            planned: [_t("Planned"), "text-bg-success"],
        };
        const [label, className] = labels[this.state.activity?.state] || labels.planned;
        return { label, className };
    }

    get when() {
        const activity = this.state.activity;
        const event = activity?.event;
        if (event?.start) {
            if (event.allday) {
                return formatDate(deserializeDateTime(event.start));
            }
            const start = deserializeDateTime(event.start);
            const stop = event.stop && deserializeDateTime(event.stop);
            const sameDay = stop && start.hasSame(stop, "day");
            return stop
                ? `${formatDateTime(start)} – ${sameDay ? stop.toFormat("HH:mm") : formatDateTime(stop)}`
                : formatDateTime(start);
        }
        return activity?.date_deadline ? formatDate(deserializeDate(activity.date_deadline)) : "";
    }

    get doneOn() {
        const activity = this.state.activity;
        return activity?.date_done ? formatDate(deserializeDate(activity.date_done)) : "";
    }

    html(value) {
        return value ? markup(value) : "";
    }

    openRecord() {
        const { res_model, res_id } = this.state.activity || {};
        if (res_model && res_id) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model,
                res_id,
                views: [[false, "form"]],
            });
        }
    }

    // ------------------------------------------------------------------
    // Recording
    // ------------------------------------------------------------------

    get recordingHere() {
        return this.recorderState.activityId === this.activityId;
    }

    get recorderBusyElsewhere() {
        return this.recorderState.phase !== "idle" && !this.recordingHere;
    }

    get failedUpload() {
        const failed = this.recorderState.failedUpload;
        return failed && failed.activityId === this.activityId ? failed : null;
    }

    get elapsed() {
        return formatElapsed(this.recorderState.elapsedSec);
    }

    get canRecord() {
        return this.state.activity?.can_write !== false && !this.state.evieError;
    }

    startRecording() {
        this.recorder.start({ activityId: this.activityId, title: this.title });
    }

    stopRecording() {
        this.commitLiveNote();
        this.recorder.stop();
    }

    onFileChosen(ev) {
        const file = ev.target.files?.[0];
        ev.target.value = "";
        if (file) {
            this.recorder.uploadFile({ activityId: this.activityId, title: this.title, file });
        }
    }

    retryUpload() {
        this.recorder.retryUpload();
    }

    downloadFailedUpload() {
        this.recorder.downloadFailedUpload();
    }

    discardFailedUpload() {
        this.recorder.discardFailedUpload();
    }

    get selected() {
        return this.state.recordings.find((r) => r.document_id === this.state.selectedId) || null;
    }

    get selectedTranscript() {
        return this.state.transcripts[this.state.selectedId] || null;
    }

    selectRecording(recording) {
        this.state.selectedId = recording.document_id;
        this.state.matchIndex = 0;
        this.setTranscriptStatus("");
        this.stopSpeaking();
        this.ensureSelectedLoaded();
    }

    ensureSelectedLoaded() {
        const recording = this.selected;
        if (!recording) {
            return;
        }
        if (recording.has_recording && !this.state.audioUrls[recording.document_id]) {
            this.loadAudioUrl(recording.document_id);
        }
        if (recording.has_transcript && !this.state.transcripts[recording.document_id]) {
            this.loadTranscript(recording.document_id);
        }
    }

    async loadAudioUrl(documentId) {
        this.state.audioUrls[documentId] = "pending";
        try {
            const { audio_url } = await this.orm.silent.call(MODEL, "evie_meeting_audio_url", [
                [this.activityId],
                documentId,
            ]);
            this.state.audioUrls[documentId] = audio_url;
        } catch {
            delete this.state.audioUrls[documentId];
        }
    }

    audioUrl(recording) {
        const url = this.state.audioUrls[recording.document_id];
        return url && url !== "pending" ? url : "";
    }

    async loadTranscript(documentId) {
        this.state.transcripts[documentId] = {
            loading: true,
            error: "",
            blocks: [],
            segments: [],
            speakers: [],
        };
        try {
            const data = await this.orm.silent.call(MODEL, "evie_meeting_transcript", [
                [this.activityId],
                documentId,
            ]);
            const labels = data.speaker_labels || {};
            this.state.transcripts[documentId] = {
                loading: false,
                error: "",
                speakers: (data.speakers || []).map((key) => ({ key, name: labels[key] || "" })),
                savedLabels: { ...labels },
            };
            this.applyTranscriptContent(documentId, data);
        } catch (error) {
            this.state.transcripts[documentId] = {
                loading: false,
                error: errorMessage(error),
                blocks: [],
                segments: [],
                speakers: [],
            };
        }
    }

    /** New transcript text (after loading or a replace); cached speech is stale from here on. */
    applyTranscriptContent(documentId, data) {
        const transcript = this.state.transcripts[documentId];
        transcript.blocks = transcriptBlocks(data.markdown_content);
        transcript.segments = data.segments || [];
        if (this.state.speaking?.documentId === documentId) {
            this.stopSpeaking();
        }
        this.clearSpeechCache(documentId);
    }

    // ------------------------------------------------------------------
    // Transcript: listen to a fragment, find and replace
    // ------------------------------------------------------------------

    get transcriptRegex() {
        return transcriptMatchRegex(this.state.find);
    }

    get transcriptSegments() {
        const regex = this.transcriptRegex;
        return (this.selectedTranscript?.segments || []).map((segment) => ({
            ...segment,
            parts: splitTranscriptMatches(segment.text, regex),
        }));
    }

    get transcriptMatches() {
        return this.transcriptSegments.flatMap((segment) =>
            segment.parts
                .filter((part) => part.match >= 0)
                .map((part) => ({ segment: segment.index, occurrence: part.match }))
        );
    }

    get matchCountLabel() {
        const total = this.transcriptMatches.length;
        if (!total) {
            return _t("No matches");
        }
        return _t("%(current)s of %(total)s", {
            current: Math.min(this.state.matchIndex, total - 1) + 1,
            total,
        });
    }

    get canEditTranscript() {
        return this.state.activity?.can_write !== false && !this.state.evieError;
    }

    isCurrentMatch(segmentIndex, occurrence) {
        const match = this.transcriptMatches[this.state.matchIndex];
        return Boolean(match) && match.segment === segmentIndex && match.occurrence === occurrence;
    }

    setTranscriptStatus(message, isError = false) {
        this.state.transcriptStatus = message;
        this.state.transcriptStatusError = isError;
    }

    onFindInput(ev) {
        this.state.find = ev.target.value;
        this.state.matchIndex = 0;
        this.setTranscriptStatus("");
        this.scrollToMatch();
    }

    onFindKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.stepMatch(ev.shiftKey ? -1 : 1);
        }
    }

    onReplaceKeydown(ev) {
        if (ev.key === "Enter") {
            ev.preventDefault();
            this.replaceInTranscript(true);
        }
    }

    stepMatch(delta) {
        const total = this.transcriptMatches.length;
        if (total) {
            this.state.matchIndex = (this.state.matchIndex + delta + total) % total;
            this.scrollToMatch();
        }
    }

    scrollToMatch() {
        browser.requestAnimationFrame(() => {
            const match = this.transcriptMatches[this.state.matchIndex];
            if (match) {
                this.transcriptList.el
                    ?.querySelector(`[data-match="${match.segment}-${match.occurrence}"]`)
                    ?.scrollIntoView({ block: "center", behavior: "smooth" });
            }
        });
    }

    async replaceInTranscript(once) {
        const documentId = this.state.selectedId;
        const match = this.transcriptMatches[this.state.matchIndex];
        if (!match || this.state.replacing) {
            return;
        }
        this.state.replacing = true;
        this.setTranscriptStatus("");
        try {
            const data = await this.orm.silent.call(MODEL, "evie_meeting_replace_in_transcript", [
                [this.activityId],
                documentId,
                this.state.find,
                this.state.replaceWith,
                once ? match.segment : null,
                once ? match.occurrence : null,
            ]);
            this.applyTranscriptContent(documentId, data);
            const total = this.transcriptMatches.length;
            this.state.matchIndex = total ? Math.min(this.state.matchIndex, total - 1) : 0;
            const count = data.replaced || 0;
            this.setTranscriptStatus(
                count === 1
                    ? _t("Replaced 1 occurrence.")
                    : _t("Replaced %s occurrences.", count)
            );
        } catch (error) {
            this.setTranscriptStatus(errorMessage(error), true);
        } finally {
            this.state.replacing = false;
        }
    }

    clock(seconds) {
        return formatElapsed(seconds);
    }

    speakLabel(speech) {
        return speech ? _t("Stop") : _t("Listen to this part");
    }

    speakingState(segmentIndex) {
        const speaking = this.state.speaking;
        if (speaking?.documentId !== this.state.selectedId || speaking.segment !== segmentIndex) {
            return "";
        }
        return speaking.loading ? "loading" : "playing";
    }

    async toggleSpeak(segmentIndex) {
        const documentId = this.state.selectedId;
        const wasThis = this.speakingState(segmentIndex);
        this.stopSpeaking();
        if (wasThis) {
            return;
        }
        this.setTranscriptStatus("");
        const key = `${documentId}:${segmentIndex}`;
        const token = this.speechToken;
        this.state.speaking = { documentId, segment: segmentIndex, loading: true };
        try {
            let url = this.speechUrls.get(key);
            if (!url) {
                const { audio_base64, mime_type } = await this.orm.silent.call(
                    MODEL,
                    "evie_meeting_speak_segment",
                    [[this.activityId], documentId, segmentIndex]
                );
                url = URL.createObjectURL(base64ToBlob(audio_base64, mime_type));
                this.speechUrls.set(key, url);
            }
            if (token !== this.speechToken) {
                return;
            }
            this.speechAudio = new Audio(url);
            this.speechAudio.onended = () => this.stopSpeaking();
            this.state.speaking.loading = false;
            await this.speechAudio.play();
        } catch (error) {
            if (token === this.speechToken) {
                this.stopSpeaking();
                this.setTranscriptStatus(errorMessage(error), true);
            }
        }
    }

    stopSpeaking() {
        this.speechToken++;
        this.speechAudio?.pause();
        this.speechAudio = null;
        this.state.speaking = null;
    }

    clearSpeechCache(documentId = null) {
        for (const [key, url] of this.speechUrls) {
            if (documentId === null || key.startsWith(`${documentId}:`)) {
                URL.revokeObjectURL(url);
                this.speechUrls.delete(key);
            }
        }
    }

    recordingLabel(recording) {
        const parts = [];
        if (recording.recorded_at) {
            const recordedAt = DateTime.fromISO(recording.recorded_at);
            if (recordedAt.isValid) {
                parts.push(formatDateTime(recordedAt));
            }
        }
        if (recording.duration_sec) {
            parts.push(formatElapsed(recording.duration_sec));
        }
        if (recording.document_type_label) {
            parts.push(recording.document_type_label);
        }
        return parts.join(" · ");
    }

    recordingStatus(recording) {
        if (recording.processing) {
            return { label: _t("Transcribing…"), className: "text-bg-info" };
        }
        if (recording.processing_error) {
            return { label: _t("Transcription failed"), className: "text-bg-danger" };
        }
        if (recording.has_transcript) {
            return { label: _t("Transcript ready"), className: "text-bg-success" };
        }
        return { label: _t("No transcript"), className: "text-bg-light" };
    }

    transcribeLabel(recording) {
        if (this.state.transcribing[recording.document_id] || recording.processing) {
            return _t("Transcribing…");
        }
        if (recording.processing_error) {
            return _t("Retry transcription");
        }
        return recording.has_transcript ? _t("Regenerate transcript") : _t("Generate transcript");
    }

    async transcribe(recording) {
        const documentId = recording.document_id;
        this.state.transcribing[documentId] = true;
        try {
            await this.orm.call(MODEL, "evie_meeting_transcribe", [[this.activityId], documentId]);
            delete this.state.transcripts[documentId];
            await this.refreshRecordings();
        } finally {
            delete this.state.transcribing[documentId];
        }
    }

    get speakersDirty() {
        const transcript = this.selectedTranscript;
        if (!transcript?.speakers?.length) {
            return false;
        }
        const saved = transcript.savedLabels || {};
        return transcript.speakers.some((row) => (row.name || "").trim() !== (saved[row.key] || ""));
    }

    async saveSpeakers() {
        const documentId = this.state.selectedId;
        const transcript = this.selectedTranscript;
        if (!transcript) {
            return;
        }
        const labels = {};
        for (const row of transcript.speakers) {
            const name = (row.name || "").trim();
            if (name) {
                labels[row.key] = name;
            }
        }
        this.state.savingSpeakers = true;
        try {
            await this.orm.call(MODEL, "evie_meeting_save_speakers", [
                [this.activityId],
                documentId,
                labels,
            ]);
            await this.loadTranscript(documentId);
        } finally {
            this.state.savingSpeakers = false;
        }
    }

    // ------------------------------------------------------------------
    // Document types (recordings and notes)
    // ------------------------------------------------------------------

    applyNotesDocument(notes) {
        this.state.notesDocument = {
            id: notes.document_id || false,
            type: notes.document_type || "",
            label: notes.document_type_label || "",
        };
    }

    get canEditDocumentTypes() {
        return (
            this.state.activity?.can_write !== false &&
            !this.state.evieError &&
            this.state.documentTypes.length > 0
        );
    }

    /** The active types, plus the current one when it has since been deactivated. */
    documentTypeOptions(current, currentLabel) {
        const options = this.state.documentTypes;
        if (current && !options.some((option) => option.value === current)) {
            return [...options, { value: current, label: currentLabel || current }];
        }
        return options;
    }

    documentTypeLabel(label) {
        return label || _t("Not set");
    }

    async setDocumentType(documentId, documentType) {
        this.state.savingType[documentId] = true;
        try {
            const result = await this.orm.silent.call(MODEL, "evie_meeting_set_document_type", [
                [this.activityId],
                documentId,
                documentType,
            ]);
            const recording = this.state.recordings.find((r) => r.document_id === documentId);
            if (recording) {
                recording.document_type = result.document_type;
                recording.document_type_label = result.document_type_label;
            }
            if (this.state.notesDocument.id === documentId) {
                this.applyNotesDocument(result);
            }
        } catch (error) {
            this.notification.add(
                _t("The document type could not be saved: %s", errorMessage(error)),
                { type: "danger" }
            );
        } finally {
            delete this.state.savingType[documentId];
        }
    }

    // ------------------------------------------------------------------
    // Participants
    // ------------------------------------------------------------------

    applyParticipants(participants) {
        this.state.participants = participants.items || [];
        this.state.participantsSupported = participants.supported !== false;
        this.state.participantsReason = participants.unsupported_reason || "";
    }

    participantKey(participant) {
        return (participant.email || participant.name || "").trim().toLowerCase();
    }

    get canEditParticipants() {
        return (
            this.state.activity?.can_write !== false &&
            !this.state.evieError &&
            this.state.participantsSupported
        );
    }

    get participantSuggestions() {
        const known = new Set(this.state.participants.map((p) => this.participantKey(p)));
        return (this.state.activity?.participant_suggestions || []).filter(
            (s) => !known.has(this.participantKey(s))
        );
    }

    get participantNames() {
        return this.state.participants.map((p) => p.name);
    }

    participantDetail(participant) {
        return [participant.role, participant.company, participant.email].filter(Boolean).join(" · ");
    }

    async saveParticipants(participants) {
        this.state.participantsSaving = true;
        this.state.participantsError = "";
        try {
            const result = await this.orm.silent.call(MODEL, "evie_meeting_save_participants", [
                [this.activityId],
                participants,
            ]);
            this.applyParticipants(result);
            return true;
        } catch (error) {
            this.state.participantsError = errorMessage(error);
            return false;
        } finally {
            this.state.participantsSaving = false;
        }
    }

    addSuggestedParticipant(suggestion) {
        this.saveParticipants([...this.state.participants, suggestion]);
    }

    addAllSuggestedParticipants() {
        this.saveParticipants([...this.state.participants, ...this.participantSuggestions]);
    }

    removeParticipant(index) {
        this.saveParticipants(this.state.participants.filter((_p, i) => i !== index));
    }

    openParticipantForm(index = -1) {
        const participant = index >= 0 ? this.state.participants[index] : {};
        this.state.participantForm = {
            index,
            name: participant.name || "",
            email: participant.email || "",
            company: participant.company || "",
            role: participant.role || "",
            internal: Boolean(participant.internal),
        };
    }

    cancelParticipantForm() {
        this.state.participantForm = null;
    }

    async submitParticipantForm() {
        const form = this.state.participantForm;
        if (!form || !(form.name.trim() || form.email.trim())) {
            this.state.participantsError = _t("Enter a name or an email address.");
            return;
        }
        const participant = {
            name: form.name.trim(),
            email: form.email.trim(),
            company: form.company.trim(),
            role: form.role.trim(),
            internal: form.internal,
        };
        const participants = [...this.state.participants];
        if (form.index >= 0) {
            participants[form.index] = participant;
        } else {
            participants.push(participant);
        }
        if (await this.saveParticipants(participants)) {
            this.state.participantForm = null;
        }
    }

    // ------------------------------------------------------------------
    // Notes
    // ------------------------------------------------------------------

    get notesStatusLabel() {
        switch (this.state.notesStatus) {
            case "dirty":
                return _t("Unsaved changes");
            case "saving":
                return _t("Saving…");
            case "error":
                return _t("Not saved");
            default:
                return this.state.notesSaved ? _t("Saved to Evie") : "";
        }
    }

    onNotesInput(ev) {
        this.setNotes(ev.target.value);
    }

    /** Every notes change goes through here: local draft, status and debounced save to Evie. */
    setNotes(value) {
        this.state.notes = value;
        this.state.draftRestored = false;
        if (this.state.notes === this.state.notesSaved) {
            this.state.notesStatus = "saved";
            browser.localStorage.removeItem(this.draftKey);
        } else {
            this.state.notesStatus = "dirty";
            browser.localStorage.setItem(this.draftKey, this.state.notes);
        }
        browser.clearTimeout(this.notesTimer);
        this.notesTimer = browser.setTimeout(() => this.saveNotes(), NOTES_AUTOSAVE_MS);
    }

    onNotesBlur() {
        if (["dirty", "error"].includes(this.state.notesStatus)) {
            this.saveNotes();
        }
    }

    // Live notes: lines typed while recording, appended to the notes with their recording time.

    get liveNotesActive() {
        return (
            this.recordingHere &&
            this.recorderState.phase === "recording" &&
            this.state.activity?.can_write !== false
        );
    }

    /** The recording time, frozen on the moment the current line was started. */
    get liveStamp() {
        return formatElapsed(this.state.liveDraftAt ?? this.recorderState.elapsedSec);
    }

    onLiveInput(ev) {
        const text = ev.target.value;
        this.state.liveDraft = text;
        if (!text.trim()) {
            this.state.liveDraftAt = null;
        } else if (this.state.liveDraftAt === null) {
            this.state.liveDraftAt = this.recorder.elapsedNow();
        }
        this.autosizeLiveInput();
    }

    onLiveKeydown(ev) {
        if (ev.key !== "Enter" || ev.isComposing) {
            return;
        }
        if (ev.metaKey || ev.ctrlKey) {
            ev.preventDefault();
            this.commitLiveNote();
            return;
        }
        if (ev.shiftKey || ev.altKey) {
            return;
        }
        const el = ev.target;
        if (!el.value.trim()) {
            ev.preventDefault();
            return;
        }
        // Enter on an empty line (i.e. Enter twice) saves the line.
        const before = el.value.slice(0, el.selectionStart);
        const after = el.value.slice(el.selectionEnd);
        if (before.endsWith("\n") && !after.trim()) {
            ev.preventDefault();
            this.commitLiveNote(before.slice(0, -1));
        }
    }

    commitLiveNote(text = this.state.liveDraft) {
        if (!text.trim()) {
            return;
        }
        const line = formatLiveNote(this.state.liveDraftAt ?? this.recorder.elapsedNow(), text);
        const notes = this.state.notes;
        const separator = !notes.trim() ? "" : notes.endsWith("\n") ? "" : "\n";
        this.setNotes(`${notes.trim() ? notes : ""}${separator}${line}\n`);
        this.state.liveDraft = "";
        this.state.liveDraftAt = null;
        if (this.liveInput.el) {
            this.liveInput.el.value = "";
            this.autosizeLiveInput();
            this.liveInput.el.focus();
        }
    }

    autosizeLiveInput() {
        const el = this.liveInput.el;
        if (el) {
            el.style.height = "auto";
            el.style.height = `${el.scrollHeight}px`;
        }
    }

    async saveNotes() {
        browser.clearTimeout(this.notesTimer);
        const content = this.state.notes;
        // Evie keeps notes as a non-empty document; clearing them is kept as a local draft.
        if (content === this.state.notesSaved || !content.trim() || this.state.evieError) {
            return;
        }
        if (this.state.notesStatus === "saving") {
            this.notesTimer = browser.setTimeout(() => this.saveNotes(), 1000);
            return;
        }
        this.state.notesStatus = "saving";
        this.state.notesError = "";
        try {
            const result = await this.orm.silent.call(MODEL, "evie_meeting_save_notes", [
                [this.activityId],
                content,
            ]);
            this.applyNotesDocument(result);
            this.state.notesSaved = content;
            if (this.state.notes === content) {
                this.state.notesStatus = "saved";
                browser.localStorage.removeItem(this.draftKey);
            } else {
                this.state.notesStatus = "dirty";
            }
        } catch (error) {
            this.state.notesStatus = "error";
            this.state.notesError = errorMessage(error);
        }
    }
}

registry.category("actions").add(ACTION_TAG, MeetingWindow);
