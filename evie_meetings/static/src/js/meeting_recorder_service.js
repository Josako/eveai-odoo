/** @odoo-module */

/**
 * evie_meeting_recorder service (odoo-meeting-window).
 *
 * Records meeting audio in the browser and uploads it to Evie. It is a
 * service rather than part of the meeting window so a recording keeps
 * running while the user navigates Odoo (the recording indicator in the top
 * bar leads back to the window). One recording at a time.
 *
 * Uploads go straight from the browser to Evie via a one-time link the
 * server obtains with the API key (evie_meeting_upload_url): recordings are
 * too large to relay through Odoo. A failed upload keeps the audio in memory
 * so the user can retry or download it instead of losing the meeting.
 */

import { reactive } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";

const MODEL = "mail.activity";
const MIME_CANDIDATES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
const EXTENSIONS = { "audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a" };
// Speech needs far less than the browser default (~128 kbps): an hour stays around 20 MB.
const AUDIO_BITS_PER_SECOND = 48000;
const MAX_NAME_LENGTH = 100;

export function errorMessage(error) {
    return error?.data?.message || error?.message || String(error);
}

function pickMimeType() {
    return MIME_CANDIDATES.find((type) => window.MediaRecorder?.isTypeSupported?.(type)) || "";
}

function extensionFor(mimeType) {
    return EXTENSIONS[(mimeType || "").split(";")[0]] || "webm";
}

function safeName(title) {
    return (title || _t("Meeting recording")).slice(0, MAX_NAME_LENGTH);
}

export const meetingRecorderService = {
    dependencies: ["orm", "notification"],

    start(env, { orm, notification }) {
        const state = reactive({
            phase: "idle", // idle | starting | recording | uploading
            activityId: false,
            title: "",
            elapsedSec: 0,
            failedUpload: null,
            // Bumped after every successful upload so an open window reloads.
            uploadCount: 0,
            lastUploadActivityId: false,
        });

        let recorder = null;
        let stream = null;
        let chunks = [];
        let timer = null;
        let startedAt = null;

        browser.addEventListener("beforeunload", (ev) => {
            if (state.phase === "recording" || state.phase === "uploading") {
                ev.preventDefault();
                ev.returnValue = "";
            }
        });

        function stopStream() {
            stream?.getTracks().forEach((track) => track.stop());
            stream = null;
        }

        function reset() {
            browser.clearInterval(timer);
            timer = null;
            stopStream();
            recorder = null;
            chunks = [];
            startedAt = null;
            state.elapsedSec = 0;
            state.phase = "idle";
            state.activityId = false;
            state.title = "";
        }

        async function upload(item) {
            state.phase = "uploading";
            state.activityId = item.activityId;
            state.title = item.title;
            try {
                const { upload_url } = await orm.silent.call(MODEL, "evie_meeting_upload_url", [
                    [item.activityId],
                ]);
                const form = new FormData();
                form.append("file", item.blob, item.filename);
                form.append(
                    "data",
                    JSON.stringify({
                        name: safeName(item.title),
                        recorded_at: item.recordedAt.toISOString(),
                        duration_sec: item.durationSec ?? null,
                    })
                );
                const response = await browser.fetch(upload_url, { method: "POST", body: form });
                if (!response.ok) {
                    let message = "";
                    try {
                        message = (await response.json()).message;
                    } catch {
                        // Not a JSON error body.
                    }
                    throw new Error(message || _t("Upload failed (HTTP %s).", response.status));
                }
                state.failedUpload = null;
                state.lastUploadActivityId = item.activityId;
                state.uploadCount++;
                notification.add(_t("Recording saved. Evie is transcribing it."), {
                    type: "success",
                });
            } catch (error) {
                state.failedUpload = { ...item, error: errorMessage(error) };
                notification.add(
                    _t("The recording could not be saved: %s. Open the meeting window to retry.",
                        errorMessage(error)),
                    { type: "danger", sticky: true }
                );
            } finally {
                state.phase = "idle";
                state.activityId = false;
                state.title = "";
            }
        }

        return {
            state,

            get busy() {
                return state.phase !== "idle";
            },

            async start({ activityId, title }) {
                if (state.phase !== "idle") {
                    return;
                }
                if (!browser.navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
                    notification.add(_t("This browser cannot record audio."), { type: "danger" });
                    return;
                }
                state.phase = "starting";
                state.activityId = activityId;
                state.title = title;
                try {
                    stream = await browser.navigator.mediaDevices.getUserMedia({ audio: true });
                    const mimeType = pickMimeType();
                    const options = { audioBitsPerSecond: AUDIO_BITS_PER_SECOND };
                    if (mimeType) {
                        options.mimeType = mimeType;
                    }
                    recorder = new window.MediaRecorder(stream, options);
                    chunks = [];
                    startedAt = new Date();
                    recorder.ondataavailable = (ev) => {
                        if (ev.data?.size) {
                            chunks.push(ev.data);
                        }
                    };
                    recorder.onerror = () => {
                        notification.add(_t("Recording failed. Please try again."), {
                            type: "danger",
                        });
                        reset();
                    };
                    recorder.onstop = () => {
                        const type = recorder?.mimeType || mimeType || "audio/webm";
                        const item = {
                            activityId: state.activityId,
                            title: state.title,
                            blob: new Blob(chunks, { type }),
                            filename: `meeting.${extensionFor(type)}`,
                            recordedAt: startedAt || new Date(),
                            durationSec: state.elapsedSec,
                        };
                        reset();
                        if (!item.blob.size) {
                            notification.add(
                                _t("No audio was captured. Check your microphone and try again."),
                                { type: "warning" }
                            );
                            return;
                        }
                        upload(item);
                    };
                    recorder.start(1000);
                    timer = browser.setInterval(() => state.elapsedSec++, 1000);
                    state.phase = "recording";
                } catch (error) {
                    reset();
                    notification.add(
                        error?.name === "NotAllowedError"
                            ? _t("Microphone access was blocked. Allow it in the browser to record.")
                            : _t("Could not start recording: %s", errorMessage(error)),
                        { type: "danger" }
                    );
                }
            },

            stop() {
                if (recorder && recorder.state !== "inactive") {
                    browser.clearInterval(timer);
                    recorder.stop();
                }
            },

            /** Add an existing audio/video file as a recording of the activity. */
            async uploadFile({ activityId, title, file }) {
                if (state.phase !== "idle") {
                    return;
                }
                await upload({
                    activityId,
                    title: title || file.name.replace(/\.[^.]+$/, ""),
                    blob: file,
                    filename: file.name,
                    recordedAt: new Date(file.lastModified || Date.now()),
                    durationSec: null,
                });
            },

            async retryUpload() {
                const item = state.failedUpload;
                if (item && state.phase === "idle") {
                    await upload(item);
                }
            },

            downloadFailedUpload() {
                const item = state.failedUpload;
                if (!item) {
                    return;
                }
                const url = URL.createObjectURL(item.blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = item.filename;
                link.click();
                browser.setTimeout(() => URL.revokeObjectURL(url), 1000);
            },

            discardFailedUpload() {
                state.failedUpload = null;
            },
        };
    },
};

registry.category("services").add("evie_meeting_recorder", meetingRecorderService);
