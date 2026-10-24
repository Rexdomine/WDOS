/**
 * WDOS Multilingua Meeting & Translation Engine (v4)
 * Orchestrates live Microphone Speech-to-Text (Azure AI Speech SDK + Web Speech API),
 * real-time Web Audio microphone level visualizer, multi-language translation
 * (English, French, Portuguese, Arabic, Swahili, Hausa, Yoruba, Igbo),
 * Neural Text-to-Speech audio output (Azure Neural TTS + Web Speech Synthesis fallback),
 * live WebRTC camera preview, and real-time multi-participant room synchronization.
 */

class WDOSMultilinguaMeeting {
    constructor(config) {
        this.meetingId = config.meetingId;
        this.roomCode = config.roomCode || config.meetingId;
        this.tokensUrl = config.tokensUrl;
        this.transcriptUrl = config.transcriptUrl || `/api/rooms/${config.meetingId}/transcript/`;
        this.ttsUrl = config.ttsUrl || `/api/rooms/${config.meetingId}/tts/`;
        this.restoreAudioUrl = config.restoreAudioUrl || `/api/rooms/${config.meetingId}/restore-audio/`;
        this.switchLangUrl = config.switchLangUrl || `/foundation/rooms/${this.roomCode}/live/`;
        this.userDisplayName = config.userDisplayName || "Participant";
        this.isHost = Boolean(config.isHost);
        this.isGuest = Boolean(config.isGuest);

        // Language State
        this.speakingLang = config.speakingLang || "en-US";
        this.listeningLang = config.listeningLang || "fr-FR";

        // Provider Clients & Media Streams
        this.clientInstanceId = Math.random().toString(36).substring(2, 10);
        this.azureData = null;
        this.livekitData = null;
        this.livekitRoom = null;
        this.remoteAudioElements = new Map();
        this.participantLanguagesById = new Map();
        this.participantLanguagesByName = new Map();
        this.myParticipantId = null;
        this.locallyPostedSegmentIds = new Set();
        this.recentlySubmittedTexts = new Map();
        this.spokenSegmentIds = new Set();
        this.isFetchingTranscript = false;
        this.initRoomPromise = null;
        this.tokenRefreshTimer = null;
        this.azureInterimFlushTimer = null;
        this.azureAudioStream = null;
        this.azureRetryCount = 0;
        this.lastRecognizerActivityAt = 0;
        this.lastVoiceDetectedAt = 0;
        this.zoomData = null;
        this.zoomClient = null;
        this.mediaStream = null;
        this.localVideoStream = null;
        this.localAudioStream = null;
        this.audioContext = null;
        this.analyserNode = null;
        this.visualizerFrame = null;
        this.speechRecognizer = null;
        this.webSpeechRecognizer = null;

        // Media & Sync Flags
        this.isAudioMuted = true;
        this.isVideoOff = true;
        this.isAudioDegraded = false;
        this.isSpeakerAudioMuted = false;
        this.isTranslationEnabled = true;
        this.isSyncingMedia = false;
        this.lastSeenSequence = config.initialSequence || 0;
        this.lastSeenAudioSeq = -1;
        this.lastReceivedRawAudioAt = 0;
        this.pollTimer = null;
        this.lastTranslatedText = "";
        this.lastOriginalText = "";
        this.lastOriginalLang = "en-US";
        this.participantCount = 1;
        this.audioPlaybackQueue = [];
        this.isPlayingQueueItem = false;
        this.currentAudioEl = null;
        this.ttsAudioPlayer = null;
        this.isAudioUnlocked = false;
        this.speechWatchdogTimer = null;
        this.interimFlushTimer = null;
        this.pendingInterimText = "";
        this.liveMediaRecorder = null;
        this.liveRecorderInterval = null;
        this.hadVoiceInCurrentChunk = false;

        this.langNames = {
            "en-US": "English",
            "fr-FR": "French",
            "pt-BR": "Portuguese",
            "ar-EG": "Arabic",
            "sw-KE": "Swahili",
            "ha-NG": "Hausa",
            "yo-NG": "Yoruba",
            "ig-NG": "Igbo"
        };

        this.shortToBcp47 = {
            "en": "en-US",
            "fr": "fr-FR",
            "pt": "pt-BR",
            "ar": "ar-EG",
            "sw": "sw-KE",
            "ha": "ha-NG",
            "yo": "yo-NG",
            "ig": "ig-NG"
        };

        this.readyPrompts = {
            "en-US": 'Click "Turn Mic On" or type a statement below to speak — live translation & voice synthesis will play automatically.',
            "fr-FR": 'Cliquez sur « Activer le micro » ou saisissez une phrase ci-dessous pour parler — la traduction en direct et la synthèse vocale seront diffusées automatiquement.',
            "pt-BR": 'Clique em "Ativar Microfone" ou digite uma frase abaixo para falar — a tradução ao vivo e a síntese de voz serão reproduzidas automaticamente.',
            "ar-EG": 'انقر على "تشغيل الميكروفون" أو اكتب عبارة أدناه للتحدث — سيتم تشغيل الترجمة المباشرة والصوت تلقائياً.',
            "sw-KE": 'Bofya "Washa Maikrofoni" au andika kauli hapa chini ili kuzungumza — tafsiri ya moja kwa moja na sauti vitacheza kiotomatiki.',
            "ha-NG": 'Danna "Kunna Makirufo" ko rubuta magana a ƙasa don yin magana — fassarar kai tsaye da murya za su tashi da kansu.',
            "yo-NG": 'Tẹ "Tan Gbohungbohun" tàbí kọ ọ̀rọ̀ sí ìsàlẹ̀ láti sọ̀rọ̀ — ìtumọ̀ ojú-ẹsẹ̀ àti ohùn yóò ṣiṣẹ́ fúnra rẹ̀.',
            "ig-NG": 'Pịa "Gbanye Igwe Okwu" ma ọ bụ pịnye okwu n\'okpuru ka ị kwuo okwu — ntụgharị asụsụ na olu ga-akpọ n\'onwe ya.'
        };

        this.hasLiveSegments = Boolean(config.initialSequence && config.initialSequence > 0);
    }

    normalizeLangCode(code, fallback = "fr-FR") {
        if (!code) return fallback;
        if (this.langNames[code]) return code;
        const short = String(code).split("-")[0].toLowerCase();
        return this.shortToBcp47[short] || fallback;
    }

    getShortLang(bcp47) {
        return (bcp47 || "en-US").split("-")[0].toLowerCase();
    }

    unlockAudioPlayback() {
        try {
            if (this.livekitRoom && typeof this.livekitRoom.startAudio === "function") {
                this.livekitRoom.startAudio().catch(() => {});
            }
            if (this.remoteAudioElements && this.remoteAudioElements.size > 0) {
                this.remoteAudioElements.forEach((audioEl) => {
                    if (audioEl && audioEl.paused) {
                        audioEl.play().catch(() => {});
                    }
                });
            }
        } catch (_) {}
        if (this.isAudioUnlocked) return;
        try {
            if (!this.ttsAudioPlayer) {
                this.ttsAudioPlayer = new Audio();
                this.ttsAudioPlayer.preload = "auto";
                this.ttsAudioPlayer.playsInline = true;
            }
            if ("speechSynthesis" in window) {
                try { window.speechSynthesis.resume(); } catch (_) {}
            }
            this.isAudioUnlocked = true;
        } catch (_) {}
    }

    async boot() {
        if (document.getElementById("waiting-lobby-screen") || document.getElementById("meeting-ended-screen")) {
            return;
        }
        const unlockHandler = () => this.unlockAudioPlayback();
        document.addEventListener("click", unlockHandler, { passive: true });
        document.addEventListener("touchstart", unlockHandler, { passive: true });
        document.addEventListener("pointerdown", unlockHandler, { passive: true });
        document.addEventListener("keydown", unlockHandler, { passive: true });

        this.switchListeningLanguage(this.listeningLang);
        this.bindUIControls();
        if (document.getElementById("prejoin-screen")) {
            return;
        }
        this.initRoomPromise = this.initializeRoom();
        await this.initRoomPromise;
        this.startLivePolling();
    }

    bindUIControls() {
        const micBtns = document.querySelectorAll("#btn-toggle-mic, #btn-start-speaking");
        micBtns.forEach((btn) => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                this.unlockAudioPlayback();
                await this.toggleMicrophone();
            });
        });

        const camBtns = document.querySelectorAll("#btn-toggle-cam");
        camBtns.forEach((btn) => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                await this.toggleCamera();
            });
        });

        const handBtn = document.getElementById("btn-raise-hand");
        if (handBtn) {
            handBtn.addEventListener("click", async (e) => {
                e.preventDefault();
                await this.toggleRaiseHand();
            });
        }

        const transModeBtn = document.getElementById("btn-toggle-translation-mode");
        if (transModeBtn) {
            transModeBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.unlockAudioPlayback();
                this.isTranslationEnabled = !this.isTranslationEnabled;
                this.clearAudioQueue();
                this.updateRemoteWebRTCAudioVolumes();
                const modeLabelEl = document.getElementById("btn-toggle-translation-mode-label");
                const headerLabelEl = document.getElementById("caption-header-label");
                const replayLabelEl = document.getElementById("btn-play-translation-label");
                const langName = this.langNames[this.listeningLang] || this.listeningLang;
                if (this.isTranslationEnabled) {
                    transModeBtn.style.background = "rgba(212,0,106,0.25)";
                    transModeBtn.style.color = "#F4C2DA";
                    transModeBtn.style.borderColor = "rgba(244,194,218,0.45)";
                    if (modeLabelEl) modeLabelEl.textContent = "Live Translation: ON";
                    if (headerLabelEl) headerLabelEl.textContent = `LIVE TRANSLATION (${langName.toUpperCase()})`;
                    if (replayLabelEl) replayLabelEl.textContent = `Replay Voice (${langName})`;
                    this.setMicStatus(`Live Voice Translation ON — Hearing translated voice in ${langName}.`);
                } else {
                    transModeBtn.style.background = "rgba(56,189,248,0.22)";
                    transModeBtn.style.color = "#7DD3FC";
                    transModeBtn.style.borderColor = "rgba(125,211,252,0.45)";
                    if (modeLabelEl) modeLabelEl.textContent = "Live Translation: OFF (Original Voice)";
                    if (headerLabelEl) headerLabelEl.textContent = "ORIGINAL VOICE MODE (AI TRANSLATION OFF)";
                    if (replayLabelEl) replayLabelEl.textContent = "Replay Original Voice";
                    this.setMicStatus("Live Voice Translation OFF — Hearing the speaker's real human voice only (no AI voice).");
                }
            });
        }

        const ttsToggleBtn = document.getElementById("btn-toggle-tts-audio");
        if (ttsToggleBtn) {
            ttsToggleBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.unlockAudioPlayback();
                this.isSpeakerAudioMuted = !this.isSpeakerAudioMuted;
                this.updateRemoteWebRTCAudioVolumes();
                const labelEl = document.getElementById("btn-toggle-tts-label");
                if (this.isSpeakerAudioMuted) {
                    this.clearAudioQueue();
                    ttsToggleBtn.style.background = "rgba(239,68,68,0.22)";
                    ttsToggleBtn.style.color = "#FCA5A5";
                    ttsToggleBtn.style.borderColor = "rgba(248,113,113,0.4)";
                    if (labelEl) labelEl.textContent = "Voice Output: MUTED";
                } else {
                    ttsToggleBtn.style.background = "rgba(34,197,94,0.18)";
                    ttsToggleBtn.style.color = "#86EFAC";
                    ttsToggleBtn.style.borderColor = "rgba(134,239,172,0.35)";
                    if (labelEl) labelEl.textContent = "Voice Output: ON";
                    if (this.isTranslationEnabled && this.lastTranslatedText) {
                        this.speakTranslation(this.lastTranslatedText, this.azureData, true);
                    } else if (!this.isTranslationEnabled && this.lastRawAudioDataUrl) {
                        this.enqueueRawAudioChunk(this.lastRawAudioDataUrl, "Speaker");
                    }
                }
            });
        }

        const playBtn = document.getElementById("btn-play-translation");
        if (playBtn) {
            playBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.unlockAudioPlayback();
                this.isSpeakerAudioMuted = false;
                this.updateRemoteWebRTCAudioVolumes();
                const labelEl = document.getElementById("btn-toggle-tts-label");
                if (labelEl) labelEl.textContent = "Voice Output: ON";
                const ttsBtn = document.getElementById("btn-toggle-tts-audio");
                if (ttsBtn) {
                    ttsBtn.style.background = "rgba(34,197,94,0.18)";
                    ttsBtn.style.color = "#86EFAC";
                    ttsBtn.style.borderColor = "rgba(134,239,172,0.35)";
                }
                if (!this.isTranslationEnabled) {
                    if (this.lastRawAudioDataUrl) {
                        this.clearAudioQueue();
                        this.enqueueRawAudioChunk(this.lastRawAudioDataUrl, "Speaker");
                    }
                    return;
                }
                const textToSpeak = this.lastTranslatedText || document.getElementById("caption-translated-text")?.textContent || document.getElementById("caption-text")?.textContent;
                if (textToSpeak) {
                    this.speakTranslation(textToSpeak.trim(), this.azureData, true);
                }
            });
        }

        const speakForms = document.querySelectorAll("#live-speech-form, #room-04-speak-form");
        speakForms.forEach((form) => {
            form.addEventListener("submit", async (e) => {
                const input = form.querySelector("input[name='original_text']");
                if (!input || !input.value.trim()) return;
                e.preventDefault();
                const text = input.value.trim();
                const submitBtn = form.querySelector("button[type='submit']");
                const origBtnHtml = submitBtn ? submitBtn.innerHTML : "";
                if (submitBtn) {
                    submitBtn.disabled = true;
                    submitBtn.textContent = "Translating...";
                }
                input.value = "";
                await this.postTranscriptSegment(text, null, null);
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = origBtnHtml || "Speak";
                }
                await this.fetchLatestTranscript(true);
            });
        });

        const quickLangSelect = document.getElementById("quick-switch-lang");
        if (quickLangSelect) {
            quickLangSelect.addEventListener("change", async () => {
                this.switchListeningLanguage(quickLangSelect.value);
                await this.persistLanguageSelection();
                await this.fetchLatestTranscript(false);
                if (this.lastTranslatedText) {
                    this.speakTranslation(this.lastTranslatedText, this.azureData, true);
                }
            });
        }

        const speakLangSelect = document.getElementById("quick-speaking-lang");
        if (speakLangSelect) {
            speakLangSelect.addEventListener("change", async () => {
                const wasUnmuted = !this.isAudioMuted;
                if (wasUnmuted) {
                    await this.toggleMicrophone();
                }
                this.speakingLang = speakLangSelect.value;
                this.setMicStatus(`Speaking: ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing: ${this.langNames[this.listeningLang] || this.listeningLang}`);
                await this.persistLanguageSelection();
                if (this.speechRecognizer) {
                    try { this.speechRecognizer.close(); } catch (_) {}
                    this.speechRecognizer = null;
                }
                await this.initAzureTranslation(this.azureData);
                if (wasUnmuted) {
                    await this.toggleMicrophone();
                }
            });
        }

        // Delegate AJAX submission for Host/Co-Host actions so active mic/camera streams are never interrupted
        document.addEventListener("submit", async (e) => {
            const form = e.target;
            if (!form || !form.classList || !form.classList.contains("js-host-ajax-form")) return;
            e.preventDefault();
            await this.submitHostActionForm(form);
        });

        document.addEventListener("click", async (e) => {
            const btn = e.target && e.target.closest ? e.target.closest(".js-host-ajax-form button[type='submit']") : null;
            if (btn && btn.form) {
                e.preventDefault();
                await this.submitHostActionForm(btn.form, btn);
                return;
            }
            document.querySelectorAll("details.zm-top-menu[open]").forEach((menu) => {
                if (!menu.contains(e.target)) {
                    menu.removeAttribute("open");
                }
            });
        });
    }

    async submitHostActionForm(form, triggerBtn = null) {
        if (!form || form.dataset.submitting === "1") return;
        form.dataset.submitting = "1";
        const btn = triggerBtn || form.querySelector("button[type='submit']");
        const origText = btn ? btn.textContent : "";
        if (btn) {
            btn.disabled = true;
            btn.style.opacity = "0.7";
            const actionVal = (form.querySelector("input[name='action']")?.value || "").toLowerCase();
            if (actionVal === "admit" || actionVal === "admit_all") {
                btn.textContent = "Admitting...";
            } else if (actionVal === "deny") {
                btn.textContent = "Denying...";
            }
        }
        try {
            const formData = new URLSearchParams(new FormData(form));
            const rawActionAttr = typeof form.getAttribute === "function" ? form.getAttribute("action") : "";
            const targetUrl = (rawActionAttr && typeof rawActionAttr === "string" ? rawActionAttr : "") || this.switchLangUrl || window.location.pathname;
            const resp = await fetch(targetUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": this.getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData.toString()
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data && data.message) {
                    this.setMicStatus(data.message);
                }
                if (data && Array.isArray(data.waiting_participants)) {
                    this.renderWaitingRoomQueue(data.waiting_participants, true);
                }
                if (data && Array.isArray(data.participants)) {
                    this.participantCount = data.participants.length;
                    this.renderParticipantsList(data.participants, true);
                }
                await this.fetchLatestTranscript(false);
            }
        } catch (_) {
        } finally {
            form.dataset.submitting = "0";
            if (btn && document.body.contains(btn)) {
                btn.disabled = false;
                btn.style.opacity = "1";
                if (origText) btn.textContent = origText;
            }
        }
    }

    async initializeRoom() {
        try {
            const sep = this.tokensUrl.includes("?") ? "&" : "?";
            const urlWithCid = `${this.tokensUrl}${sep}cid=${encodeURIComponent(this.clientInstanceId)}`;
            const response = await fetch(urlWithCid, {
                headers: { "Accept": "application/json" }
            });
            const data = await response.json();

            if (response.status === 403 && data.status === "waiting") {
                this.triggerWaitingRoomUI();
                return data;
            }

            if (!response.ok) {
                throw new Error(data.error || "Failed to initialize room tokens.");
            }

            this.azureData = data.azure;
            this.livekitData = data.livekit || null;
            this.zoomData = data.zoom;
            if (data.participant) {
                this.myParticipantId = data.participant.id || null;
                this.userDisplayName = data.participant.name || this.userDisplayName;
                this.speakingLang = this.normalizeLangCode(data.participant.speaking_lang || this.speakingLang, "en-US");
                this.listeningLang = this.normalizeLangCode(data.participant.listening_lang || this.listeningLang, "fr-FR");
                if (this.myParticipantId && this.speakingLang) {
                    this.participantLanguagesById.set(String(this.myParticipantId), this.speakingLang);
                }
                if (this.userDisplayName && this.speakingLang) {
                    this.participantLanguagesByName.set(String(this.userDisplayName), this.speakingLang);
                }
            }
            this.switchListeningLanguage(this.listeningLang);

            await this.initLiveKitMedia(data.livekit);
            await this.initZoomMedia(data.zoom);
            this.startTokenRefreshTimer();
            this.updateDiagnosticsUI("Connected", 28);
            this.setMicStatus(`Connected as ${this.userDisplayName} · Speaking ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing ${this.langNames[this.listeningLang] || this.listeningLang}`);
            return data;
        } catch (err) {
            console.warn("[WDOS Multilingua] Operating in degraded caption fallback:", err);
            this.triggerDegradedModeUI(err.message);
            return null;
        }
    }

    async initLiveKitMedia(livekitData) {
        if (!window.LivekitClient || !livekitData || !livekitData.enabled || !livekitData.url || !livekitData.token) {
            return false;
        }
        try {
            if (this.livekitRoom) {
                try { await this.livekitRoom.disconnect(); } catch (_) {}
                this.livekitRoom = null;
            }
            let audioContainer = document.getElementById("livekit-remote-audio-container");
            if (!audioContainer) {
                audioContainer = document.createElement("div");
                audioContainer.id = "livekit-remote-audio-container";
                audioContainer.style.cssText = "position:fixed;left:-9999px;top:0;width:1px;height:1px;opacity:0.01;pointer-events:none;overflow:hidden;";
                document.body.appendChild(audioContainer);
            }

            const LK = window.LivekitClient;
            const room = new LK.Room({
                adaptiveStream: true,
                dynacast: true,
                audioCaptureDefaults: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            this.livekitRoom = room;

            const syncParticipantMetadata = (participant) => {
                if (!participant) return "";
                let metaLang = "";
                if (participant.metadata) {
                    try {
                        const parsed = JSON.parse(participant.metadata);
                        if (parsed && parsed.speaking_lang) {
                            metaLang = parsed.speaking_lang;
                            if (parsed.participant_id) {
                                this.participantLanguagesById.set(String(parsed.participant_id), metaLang);
                            }
                        }
                    } catch (_) {}
                }
                const rawIdentity = participant.identity || "";
                const baseId = rawIdentity.split("__")[0];
                if (baseId && metaLang) {
                    this.participantLanguagesById.set(baseId, metaLang);
                }
                if (participant.name && metaLang) {
                    this.participantLanguagesByName.set(String(participant.name), metaLang);
                }
                return metaLang;
            };

            const attachAudio = (track, participant) => {
                if (!track || track.kind !== "audio") return;
                const key = track.sid || (participant && participant.identity) || String(Math.random());
                const existing = this.remoteAudioElements.get(key);
                if (existing && existing.parentNode) {
                    existing.parentNode.removeChild(existing);
                }
                const metaLang = syncParticipantMetadata(participant);
                const audioEl = track.attach();
                audioEl.playsInline = true;
                audioEl.autoplay = true;
                audioEl.muted = false;
                audioEl.dataset.trackSid = key;
                audioEl.dataset.participantIdentity = participant ? (participant.identity || "") : "";
                audioEl.dataset.participantName = participant ? (participant.name || participant.identity || "Speaker") : "Speaker";
                if (metaLang) {
                    audioEl.dataset.speakingLang = metaLang;
                }
                audioContainer.appendChild(audioEl);
                this.remoteAudioElements.set(key, audioEl);
                this.updateRemoteWebRTCAudioVolumes();
                if (typeof room.startAudio === "function") {
                    room.startAudio().catch(() => {});
                }
                if (typeof audioEl.play === "function") {
                    audioEl.play().catch(() => {});
                }
            };

            const attachVideo = (track) => {
                if (!track || track.kind !== "video") return;
                if (!this.isVideoOff) return;
                const stageVideo = document.getElementById("live-stage-video");
                const speakerAvatarBox = document.getElementById("stage-avatar-container");
                if (stageVideo) {
                    track.attach(stageVideo);
                    stageVideo.style.display = "block";
                    if (speakerAvatarBox) speakerAvatarBox.style.display = "none";
                }
            };

            room.on(LK.RoomEvent.TrackSubscribed, (track, publication, participant) => {
                if (track.kind === "audio") {
                    attachAudio(track, participant);
                } else if (track.kind === "video") {
                    attachVideo(track);
                }
            });

            room.on(LK.RoomEvent.TrackUnmuted, (publication, participant) => {
                if (publication && publication.track && publication.track.kind === "audio") {
                    attachAudio(publication.track, participant);
                }
            });

            if (LK.RoomEvent.ParticipantMetadataChanged) {
                room.on(LK.RoomEvent.ParticipantMetadataChanged, (prevMetadata, participant) => {
                    syncParticipantMetadata(participant);
                    this.updateRemoteWebRTCAudioVolumes();
                });
            }

            if (LK.RoomEvent.AudioPlaybackStatusChanged) {
                room.on(LK.RoomEvent.AudioPlaybackStatusChanged, () => {
                    if (room.canPlaybackAudio) {
                        this.updateRemoteWebRTCAudioVolumes();
                    }
                });
            }

            if (LK.RoomEvent.Reconnected) {
                room.on(LK.RoomEvent.Reconnected, async () => {
                    if (!this.isAudioMuted && room.localParticipant) {
                        try {
                            await room.localParticipant.setMicrophoneEnabled(true);
                        } catch (_) {}
                    }
                    this.updateRemoteWebRTCAudioVolumes();
                });
            }

            room.on(LK.RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
                if (!track) return;
                try { track.detach(); } catch (_) {}
                const key = track.sid || (participant && participant.identity) || "";
                const el = this.remoteAudioElements.get(key);
                if (el && el.parentNode) {
                    el.parentNode.removeChild(el);
                }
                this.remoteAudioElements.delete(key);
                if (track.kind === "video" && this.isVideoOff) {
                    const stageVideo = document.getElementById("live-stage-video");
                    const speakerAvatarBox = document.getElementById("stage-avatar-container");
                    if (stageVideo) stageVideo.style.display = "none";
                    if (speakerAvatarBox) speakerAvatarBox.style.display = "flex";
                }
            });

            room.on(LK.RoomEvent.ActiveSpeakersChanged, (speakers) => {
                if (!Array.isArray(speakers) || speakers.length === 0) return;
                const localId = room.localParticipant ? room.localParticipant.identity : "";
                const remoteSpeaker = speakers.find((s) => s && s.identity !== localId) || speakers[0];
                if (remoteSpeaker) {
                    const name = remoteSpeaker.name || remoteSpeaker.identity || this.userDisplayName;
                    this.triggerSpeakingPulse(name, 1600);
                }
            });

            await room.connect(livekitData.url, livekitData.token);
            if (typeof room.startAudio === "function") {
                room.startAudio().catch(() => {});
            }

            if (!this.isAudioMuted && room.localParticipant) {
                try {
                    await room.localParticipant.setMicrophoneEnabled(true);
                } catch (_) {}
            }

            if (room.remoteParticipants && typeof room.remoteParticipants.forEach === "function") {
                room.remoteParticipants.forEach((participant) => {
                    syncParticipantMetadata(participant);
                    if (participant.trackPublications && typeof participant.trackPublications.forEach === "function") {
                        participant.trackPublications.forEach((pub) => {
                            if (pub && pub.isSubscribed && pub.track) {
                                if (pub.track.kind === "audio") attachAudio(pub.track, participant);
                                else if (pub.track.kind === "video") attachVideo(pub.track);
                            }
                        });
                    }
                });
            }
            return true;
        } catch (err) {
            console.warn("[WDOS Multilingua] LiveKit WebRTC connection warning:", err);
            this.livekitRoom = null;
            return false;
        }
    }

    startTokenRefreshTimer() {
        if (this.tokenRefreshTimer) clearInterval(this.tokenRefreshTimer);
        // Refresh 10-minute Azure Speech ephemeral token every 7 minutes so long meetings never drop recognition
        this.tokenRefreshTimer = setInterval(async () => {
            if (!this.tokensUrl) return;
            try {
                const sep = this.tokensUrl.includes("?") ? "&" : "?";
                const resp = await fetch(`${this.tokensUrl}${sep}cid=${encodeURIComponent(this.clientInstanceId)}`, {
                    headers: { "Accept": "application/json" }
                });
                if (!resp.ok) return;
                const data = await resp.json();
                if (data && data.azure && data.azure.token) {
                    this.azureData = data.azure;
                    if (this.speechRecognizer) {
                        try {
                            this.speechRecognizer.authorizationToken = data.azure.token;
                        } catch (_) {}
                    }
                }
            } catch (_) {}
        }, 7 * 60 * 1000);
    }

    hasActiveRemoteWebRTCAudio() {
        return Boolean(
            this.livekitRoom &&
            this.livekitRoom.state === "connected" &&
            this.remoteAudioElements &&
            this.remoteAudioElements.size > 0
        );
    }

    updateRemoteWebRTCAudioVolumes() {
        if (!this.remoteAudioElements || this.remoteAudioElements.size === 0) return;
        const shortListen = this.getShortLang(this.listeningLang);
        this.remoteAudioElements.forEach((audioEl) => {
            if (!audioEl) return;
            if (this.isSpeakerAudioMuted) {
                audioEl.muted = true;
                audioEl.volume = 0;
                return;
            }
            audioEl.muted = false;
            if (!this.isTranslationEnabled) {
                // Live Translation OFF: 100% real human voice over WebRTC
                audioEl.volume = 1.0;
                if (audioEl.paused && typeof audioEl.play === "function") {
                    audioEl.play().catch(() => {});
                }
                return;
            }
            // Live Translation ON:
            const rawId = audioEl.dataset.participantIdentity || "";
            const baseId = rawId.split("__")[0];
            const pName = audioEl.dataset.participantName || "";
            const metaLang = audioEl.dataset.speakingLang || "";
            const speakerLang =
                this.participantLanguagesById.get(baseId) ||
                this.participantLanguagesById.get(rawId) ||
                this.participantLanguagesByName.get(pName) ||
                metaLang ||
                "";
            const shortSpeaker = speakerLang ? this.getShortLang(speakerLang) : "";
            if (!shortSpeaker || shortSpeaker === shortListen) {
                // Speaker is speaking the SAME language the listener is set to hear (or not yet known) -> 100% real human voice!
                audioEl.volume = this.isPlayingQueueItem ? 0.2 : 1.0;
            } else {
                // Speaker is speaking a DIFFERENT language -> mute original voice so listener hears only their chosen language
                audioEl.volume = 0.0;
            }
            if (audioEl.volume > 0 && audioEl.paused && typeof audioEl.play === "function") {
                audioEl.play().catch(() => {});
            }
        });
    }

    async initZoomMedia(zoomData) {
        if (this.livekitRoom && this.livekitRoom.state === "connected") {
            return;
        }
        if (!window.ZoomVideo || !zoomData || !zoomData.token) {
            return;
        }
        try {
            this.zoomClient = window.ZoomVideo.createClient();
            await this.zoomClient.init("en-US", "Global", { patchJsMedia: true });
            await this.zoomClient.join(
                zoomData.session_name,
                zoomData.token,
                this.userDisplayName
            );
            this.mediaStream = this.zoomClient.getMediaStream();
            await this.mediaStream.startAudio({ mute: true });
        } catch (err) {
            console.info("[WDOS Multilingua] Local WebRTC media mode active.");
        }
    }

    isSystemEchoPhrase(text) {
        const norm = String(text || "").trim().toLowerCase().replace(/[.!?,…]+$/g, "").trim();
        return (
            !norm ||
            norm === "translating live" ||
            norm === "consulting live" ||
            norm === "listening" ||
            norm === "listening for speech" ||
            norm === "translation ashes turned off for what is"
        );
    }

    isSuppressedByTTS() {
        // Never suppress speech recognition on the active speaker's unmuted microphone
        if (!this.isAudioMuted) return false;
        return Boolean(this.ttsSuppressionUntil && Date.now() < this.ttsSuppressionUntil);
    }

    /**
     * Streaming segmentation for continuous speech.
     * Given the growing hypothesis of the current phrase, returns the next block of
     * stable words to send (every ~5 words, holding back the last 2 words which the
     * recognizer may still revise, or flushing immediately when forcePartial is true).
     */
    takeStreamingChunk(fullText, isFinal, utteranceKey = "default", forcePartial = false) {
        const words = String(fullText || "").trim().split(/\s+/).filter(Boolean);
        if (
            this.streamUtteranceKey !== utteranceKey ||
            words.length < (this.streamCommittedWords || 0)
        ) {
            this.streamUtteranceKey = utteranceKey;
            this.streamCommittedWords = 0;
        }
        const committed = Math.min(this.streamCommittedWords || 0, words.length);
        const pending = words.slice(committed);
        if (isFinal) {
            this.streamCommittedWords = 0;
            return pending.join(" ").trim();
        }
        if (forcePartial) {
            const hold = pending.length > 4 ? 1 : 0;
            const takeCount = pending.length - hold;
            if (takeCount >= 1) {
                const chunk = pending.slice(0, takeCount);
                this.streamCommittedWords = committed + chunk.length;
                return chunk.join(" ").trim();
            }
            return "";
        }
        const STREAM_WORDS = 5;
        const HOLD_BACK = 2;
        if (pending.length >= STREAM_WORDS + HOLD_BACK) {
            const chunk = pending.slice(0, pending.length - HOLD_BACK);
            this.streamCommittedWords = committed + chunk.length;
            return chunk.join(" ").trim();
        }
        return "";
    }

    async initAzureTranslation(azureData) {
        if (!window.SpeechSDK || !azureData || !azureData.token || azureData.mode === "mock") {
            return;
        }
        const azureSupportedSources = new Set(["en-US", "fr-FR", "pt-BR", "ar-EG", "sw-KE"]);
        if (!azureSupportedSources.has(this.speakingLang)) {
            this.speechRecognizer = null;
            return;
        }
        try {
            if (this.azureInterimFlushTimer) {
                clearTimeout(this.azureInterimFlushTimer);
                this.azureInterimFlushTimer = null;
            }
            if (this.speechRecognizer) {
                try { this.speechRecognizer.close(); } catch (_) {}
                this.speechRecognizer = null;
            }
            if (this.azureAudioStream) {
                try { this.azureAudioStream.getTracks().forEach((t) => t.stop()); } catch (_) {}
                this.azureAudioStream = null;
            }
            const speechConfig = window.SpeechSDK.SpeechTranslationConfig.fromAuthorizationToken(
                azureData.token,
                azureData.region
            );
            speechConfig.speechRecognitionLanguage = this.speakingLang;

            if (window.SpeechSDK.PropertyId) {
                try {
                    speechConfig.setProperty(window.SpeechSDK.PropertyId.Speech_SegmentationSilenceTimeoutMs, "350");
                    if (window.SpeechSDK.PropertyId.Speech_SegmentationMaximumTimeMs !== undefined) {
                        speechConfig.setProperty(window.SpeechSDK.PropertyId.Speech_SegmentationMaximumTimeMs, "12000");
                    }
                } catch (_) {}
            }

            const azureSupportedTargets = new Set(["en", "fr", "pt", "ar", "sw"]);
            Object.values(azureData.supported_languages || {}).forEach((lang) => {
                if (lang && lang.short && azureSupportedTargets.has(lang.short)) {
                    speechConfig.addTargetLanguage(lang.short);
                }
            });

            let audioConfig = null;
            const existingTrack = this.localAudioStream
                ? this.localAudioStream.getAudioTracks().find((t) => t && t.readyState === "live")
                : null;
            if (existingTrack && typeof window.SpeechSDK.AudioConfig.fromStreamInput === "function") {
                try {
                    this.azureAudioStream = new MediaStream([existingTrack.clone()]);
                    audioConfig = window.SpeechSDK.AudioConfig.fromStreamInput(this.azureAudioStream);
                } catch (_) {
                    audioConfig = null;
                }
            }
            if (!audioConfig) {
                audioConfig = window.SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
            }

            this.speechRecognizer = new window.SpeechSDK.TranslationRecognizer(speechConfig, audioConfig);

            this.speechRecognizer.recognizing = (s, e) => {
                if (this.isSuppressedByTTS()) return;
                if (!e.result || !e.result.text) return;
                const interimClean = e.result.text.trim();
                if (!interimClean || this.isSystemEchoPhrase(interimClean)) return;

                this.azureRetryCount = 0;
                this.lastRecognizerActivityAt = Date.now();
                this.hadVoiceInCurrentChunk = true;
                this.triggerSpeakingPulse(this.userDisplayName, 1200);
                const targetShort = this.getShortLang(this.listeningLang);
                const liveTranslation = e.result.translations ? e.result.translations.get(targetShort) : null;
                this.renderLiveCaption(this.userDisplayName, interimClean, liveTranslation || null, false);

                const uttKey = "azure_" + String(e.result.offset ?? e.result.resultId ?? "0");
                // Continuous speech without pauses: push stable words out every ~5 words while speaking
                const streamChunk = this.takeStreamingChunk(interimClean, false, uttKey, false);
                if (streamChunk) {
                    this.postTranscriptSegment(streamChunk, null, null);
                }
                if (this.azureInterimFlushTimer) {
                    clearTimeout(this.azureInterimFlushTimer);
                }
                this.azureInterimFlushTimer = setTimeout(() => {
                    this.azureInterimFlushTimer = null;
                    if (this.isAudioMuted) return;
                    const flushChunk = this.takeStreamingChunk(interimClean, false, uttKey, true);
                    if (flushChunk && !this.isSystemEchoPhrase(flushChunk)) {
                        this.postTranscriptSegment(flushChunk, null, null);
                    }
                }, 650);
            };

            this.speechRecognizer.recognized = async (s, e) => {
                if (this.azureInterimFlushTimer) {
                    clearTimeout(this.azureInterimFlushTimer);
                    this.azureInterimFlushTimer = null;
                }
                if (this.isSuppressedByTTS()) return;
                if (e.result && e.result.text && e.result.text.trim()) {
                    const cleanText = e.result.text.trim();
                    if (this.isSystemEchoPhrase(cleanText)) {
                        this.streamCommittedWords = 0;
                        return;
                    }
                    this.azureRetryCount = 0;
                    this.lastRecognizerActivityAt = Date.now();
                    const uttKey = "azure_" + String(e.result.offset ?? e.result.resultId ?? "0");
                    const alreadyStreamed = (this.streamCommittedWords || 0) > 0 && this.streamUtteranceKey === uttKey;
                    const remainder = this.takeStreamingChunk(cleanText, true, uttKey, false);

                    this.hadVoiceInCurrentChunk = true;
                    this.triggerSpeakingPulse(this.userDisplayName, 1600);
                    const targetShort = this.getShortLang(this.listeningLang);
                    if (alreadyStreamed) {
                        // Earlier words of this phrase were already sent; send only the unsent tail
                        if (remainder && !this.isSystemEchoPhrase(remainder)) {
                            this.renderLiveCaption(this.userDisplayName, cleanText, null, true);
                            await this.postTranscriptSegment(remainder, null, null);
                        }
                        return;
                    }
                    const allTranslations = {};
                    Object.values(azureData.supported_languages || {}).forEach((lang) => {
                        const tVal = e.result.translations ? e.result.translations.get(lang.short) : null;
                        if (tVal && tVal.trim()) {
                            allTranslations[lang.short] = tVal.trim();
                        }
                    });
                    const sdkTranslation = allTranslations[targetShort] || null;
                    this.renderLiveCaption(this.userDisplayName, cleanText, sdkTranslation, true);
                    await this.postTranscriptSegment(cleanText, sdkTranslation, targetShort, allTranslations);
                }
            };

            this.speechRecognizer.canceled = () => {
                if (!this.isAudioMuted) {
                    this.speechRecognizer = null;
                    if ((this.azureRetryCount || 0) < 3 && this.azureData) {
                        this.azureRetryCount = (this.azureRetryCount || 0) + 1;
                        setTimeout(async () => {
                            if (this.isAudioMuted) return;
                            await this.initAzureTranslation(this.azureData);
                            if (this.speechRecognizer) {
                                this.speechRecognizer.startContinuousRecognitionAsync(() => {}, () => {
                                    this.speechRecognizer = null;
                                    this.startWebSpeechFallback();
                                });
                            } else {
                                this.startWebSpeechFallback();
                            }
                        }, 450);
                    } else {
                        this.startWebSpeechFallback();
                    }
                }
            };
        } catch (err) {
            this.speechRecognizer = null;
        }
    }

    triggerSpeakingPulse(speakerName, durationMs = 2400) {
        this.speechPulseUntil = Math.max(this.speechPulseUntil || 0, Date.now() + durationMs);
        this.activeSpeakingPerson = speakerName || this.userDisplayName;

        const waveEl = document.getElementById("stage-waveform");
        const avatarEl = document.getElementById("stage-speaker-initials");
        const nameEl = document.getElementById("stage-speaker-name");
        const indicatorEl = document.getElementById("stage-speaking-indicator");

        if (nameEl && this.activeSpeakingPerson) {
            nameEl.textContent = this.activeSpeakingPerson;
        }
        if (avatarEl && this.activeSpeakingPerson) {
            const parts = String(this.activeSpeakingPerson).trim().split(/\s+/);
            avatarEl.textContent = parts.slice(0, 2).map((p) => p[0] || "").join("").toUpperCase() || "SP";
            avatarEl.classList.add("is-speaking");
        }
        if (waveEl) {
            waveEl.classList.remove("is-listening");
            waveEl.classList.add("is-speaking", "css-anim");
        }
        if (indicatorEl) {
            indicatorEl.innerHTML = `<span style="color:#4ADE80; font-weight:800;">● ${this.escapeHtml(this.activeSpeakingPerson)} is speaking live...</span>`;
        }

        if (this.speechPulseTimer) clearTimeout(this.speechPulseTimer);
        this.speechPulseTimer = setTimeout(() => {
            if (Date.now() >= (this.speechPulseUntil || 0)) {
                this.resetSpeakingIndicatorState();
            }
        }, durationMs + 60);
    }

    resetSpeakingIndicatorState() {
        const waveEl = document.getElementById("stage-waveform");
        const avatarEl = document.getElementById("stage-speaker-initials");
        const indicatorEl = document.getElementById("stage-speaking-indicator");
        const bars = document.querySelectorAll("#stage-waveform span");

        if (avatarEl) {
            avatarEl.classList.remove("is-speaking");
        }
        if (waveEl) {
            waveEl.classList.remove("is-speaking", "css-anim");
            if (!this.isAudioMuted) {
                waveEl.classList.add("is-listening");
            } else {
                waveEl.classList.remove("is-listening");
            }
        }
        bars.forEach((bar) => {
            bar.style.height = this.isAudioMuted ? "6px" : "8px";
        });
        if (indicatorEl) {
            if (!this.isAudioMuted) {
                indicatorEl.innerHTML = `<span style="color:#86EFAC;">Mic active · Listening for speech...</span>`;
            } else {
                indicatorEl.textContent = "Microphone muted · Waiting for speaker";
            }
        }
    }

    startLiveVoiceRecorder(stream) {
        this.stopLiveVoiceRecorder();
        if (!stream || typeof window.MediaRecorder === "undefined") return;
        try {
            let mimeType = "";
            const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];
            for (const c of candidates) {
                if (window.MediaRecorder.isTypeSupported && window.MediaRecorder.isTypeSupported(c)) {
                    mimeType = c;
                    break;
                }
            }
            const startCycle = () => {
                if (this.isAudioMuted || !this.localAudioStream) return;
                try {
                    const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
                    this.liveMediaRecorder = recorder;
                    const chunks = [];
                    this.hadVoiceInCurrentChunk = false;

                    recorder.ondataavailable = (ev) => {
                        if (ev.data && ev.data.size > 0) {
                            chunks.push(ev.data);
                        }
                    };
                    recorder.onstop = () => {
                        const hadVoice = this.hadVoiceInCurrentChunk;
                        if (hadVoice && chunks.length > 0 && this.transcriptUrl) {
                            const blob = new Blob(chunks, { type: recorder.mimeType || mimeType || "audio/webm" });
                            if (blob.size > 200 && blob.size < 220000) {
                                const reader = new FileReader();
                                reader.onloadend = () => {
                                    const dataUrl = reader.result;
                                    if (typeof dataUrl === "string" && dataUrl.startsWith("data:audio/")) {
                                        fetch(this.transcriptUrl, {
                                            method: "POST",
                                            headers: {
                                                "Content-Type": "application/json",
                                                "X-CSRFToken": this.getCsrfToken()
                                            },
                                            body: JSON.stringify({
                                                action: "audio_chunk",
                                                speaker_name: this.userDisplayName,
                                                audio_data_url: dataUrl
                                            })
                                        }).catch(() => {});
                                    }
                                };
                                reader.readAsDataURL(blob);
                            }
                        }
                    };
                    recorder.start();
                } catch (_) {}
            };

            startCycle();
            this.liveRecorderInterval = setInterval(() => {
                if (this.isAudioMuted || !this.localAudioStream) {
                    this.stopLiveVoiceRecorder();
                    return;
                }
                if (this.liveMediaRecorder && this.liveMediaRecorder.state === "recording") {
                    try { this.liveMediaRecorder.stop(); } catch (_) {}
                }
                startCycle();
            }, 1350);
        } catch (_) {}
    }

    stopLiveVoiceRecorder() {
        if (this.liveRecorderInterval) {
            clearInterval(this.liveRecorderInterval);
            this.liveRecorderInterval = null;
        }
        if (this.liveMediaRecorder) {
            try {
                if (this.liveMediaRecorder.state === "recording") {
                    this.liveMediaRecorder.stop();
                }
            } catch (_) {}
            this.liveMediaRecorder = null;
        }
    }

    async startMicAudioVisualizer(sharedMicTrack = null) {
        this.resetSpeakingIndicatorState();
        try {
            if (sharedMicTrack && sharedMicTrack.readyState === "live") {
                this.localAudioStream = new MediaStream([sharedMicTrack.clone()]);
            } else {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
                this.localAudioStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    },
                    video: false
                });
            }
            if (!this.livekitRoom || this.livekitRoom.state !== "connected") {
                this.startLiveVoiceRecorder(this.localAudioStream);
            }
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            this.audioContext = new AudioCtx();
            if (this.audioContext.state === "suspended") {
                try { await this.audioContext.resume(); } catch (_) {}
            }
            const source = this.audioContext.createMediaStreamSource(this.localAudioStream);
            this.analyserNode = this.audioContext.createAnalyser();
            this.analyserNode.fftSize = 256;
            this.analyserNode.smoothingTimeConstant = 0.45;
            this.analyserNode.minDecibels = -88;
            this.analyserNode.maxDecibels = -22;
            source.connect(this.analyserNode);

            const waveEl = document.getElementById("stage-waveform");
            const avatarEl = document.getElementById("stage-speaker-initials");
            const indicatorEl = document.getElementById("stage-speaking-indicator");
            const bars = document.querySelectorAll("#stage-waveform span");
            const freqData = new Uint8Array(this.analyserNode.frequencyBinCount);
            const timeData = new Uint8Array(this.analyserNode.fftSize);
            const bandWeights = [0.55, 0.85, 1.05, 1.3, 1.05, 0.85, 0.55];

            // Background-safe interval so voice energy is detected even on mobile or inactive tabs
            if (this.audioEnergyInterval) clearInterval(this.audioEnergyInterval);
            this.audioEnergyInterval = setInterval(() => {
                if (this.isAudioMuted || !this.analyserNode) return;
                this.analyserNode.getByteFrequencyData(freqData);
                this.analyserNode.getByteTimeDomainData(timeData);
                let sumSquares = 0;
                for (let i = 0; i < timeData.length; i++) {
                    const normalized = (timeData[i] - 128) / 128;
                    sumSquares += normalized * normalized;
                }
                const rms = Math.sqrt(sumSquares / timeData.length);
                const voiceBinsAvg = (freqData[1] + freqData[2] + freqData[3] + freqData[4] + freqData[5]) / (5 * 255);
                if (rms > 0.025 || voiceBinsAvg > 0.045) {
                    this.hadVoiceInCurrentChunk = true;
                    this.lastVoiceDetectedAt = Date.now();
                }
            }, 80);

            const animateBars = () => {
                if (this.isAudioMuted || !this.analyserNode) return;
                this.analyserNode.getByteFrequencyData(freqData);
                this.analyserNode.getByteTimeDomainData(timeData);

                let sumSquares = 0;
                for (let i = 0; i < timeData.length; i++) {
                    const normalized = (timeData[i] - 128) / 128;
                    sumSquares += normalized * normalized;
                }
                const rms = Math.sqrt(sumSquares / timeData.length);
                const voiceBinsAvg = (freqData[1] + freqData[2] + freqData[3] + freqData[4] + freqData[5]) / (5 * 255);
                const energy = Math.max(rms * 4.8, voiceBinsAvg * 1.6);
                const isVoiceDetected = energy > 0.032;
                const isPulseActive = Date.now() < (this.speechPulseUntil || 0);

                if (isVoiceDetected) {
                    this.hadVoiceInCurrentChunk = true;
                    this.lastVoiceDetectedAt = Date.now();
                    this.speechPulseUntil = Math.max(this.speechPulseUntil || 0, Date.now() + 380);
                    this.activeSpeakingPerson = this.userDisplayName;
                }

                if (isVoiceDetected || isPulseActive) {
                    if (waveEl) {
                        waveEl.classList.remove("is-listening");
                        waveEl.classList.add("is-speaking");
                        if (isVoiceDetected) {
                            waveEl.classList.remove("css-anim");
                        } else {
                            waveEl.classList.add("css-anim");
                        }
                    }
                    if (avatarEl) avatarEl.classList.add("is-speaking");
                    if (indicatorEl) {
                        const who = this.activeSpeakingPerson || this.userDisplayName;
                        indicatorEl.innerHTML = `<span style="color:#4ADE80; font-weight:800;">● ${this.escapeHtml(who)} is speaking live...</span>`;
                    }

                    if (isVoiceDetected) {
                        bars.forEach((bar, idx) => {
                            const binVal = (freqData[idx + 1] || 0) / 255;
                            const weight = bandWeights[idx % bandWeights.length];
                            const combined = Math.min(1, (energy * 0.75 + binVal * 0.65) * weight);
                            const heightPx = Math.max(10, Math.min(44, Math.round(8 + combined * 36)));
                            bar.style.height = `${heightPx}px`;
                        });
                    }
                } else {
                    if (waveEl) {
                        waveEl.classList.remove("is-speaking", "css-anim");
                        waveEl.classList.add("is-listening");
                    }
                    if (avatarEl) avatarEl.classList.remove("is-speaking");
                    bars.forEach((bar) => {
                        bar.style.height = "8px";
                    });
                    if (indicatorEl) {
                        indicatorEl.innerHTML = `<span style="color:#86EFAC;">Mic active · Listening for speech...</span>`;
                    }
                }

                this.visualizerFrame = requestAnimationFrame(animateBars);
            };
            animateBars();
        } catch (err) {
            console.warn("[WDOS Multilingua] Microphone stream visualizer warning:", err);
        }
    }

    stopMicAudioVisualizer() {
        this.stopLiveVoiceRecorder();
        if (this.audioEnergyInterval) {
            clearInterval(this.audioEnergyInterval);
            this.audioEnergyInterval = null;
        }
        if (this.visualizerFrame) {
            cancelAnimationFrame(this.visualizerFrame);
            this.visualizerFrame = null;
        }
        if (this.localAudioStream) {
            this.localAudioStream.getTracks().forEach((t) => t.stop());
            this.localAudioStream = null;
        }
        if (this.azureAudioStream) {
            try { this.azureAudioStream.getTracks().forEach((t) => t.stop()); } catch (_) {}
            this.azureAudioStream = null;
        }
        if (this.audioContext) {
            try { this.audioContext.close(); } catch (_) {}
            this.audioContext = null;
        }
        this.analyserNode = null;
        this.resetSpeakingIndicatorState();
    }

    async flushPendingInterimSpeech() {
        if (this.interimFlushTimer) {
            clearTimeout(this.interimFlushTimer);
            this.interimFlushTimer = null;
        }
        const pendingFull = (this.pendingInterimText || "").trim();
        this.pendingInterimText = "";
        if (typeof this.pendingInterimMaxIndex === "number" && this.pendingInterimMaxIndex > (this.webSpeechCommittedIndex ?? -1)) {
            this.webSpeechCommittedIndex = this.pendingInterimMaxIndex;
        }
        // Only send the words that were not already streamed out mid-sentence
        const pending = this.takeStreamingChunk(pendingFull, true, "webspeech");
        if (!pending || this.isSystemEchoPhrase(pending)) return;
        this.triggerSpeakingPulse(this.userDisplayName, 2000);
        this.renderLiveCaption(this.userDisplayName, pendingFull, null, false);
        await this.postTranscriptSegment(pending, null, null);
    }

    startSpeechWatchdog() {
        this.stopSpeechWatchdog();
        this.speechWatchdogTimer = setInterval(() => {
            if (this.isAudioMuted) return;
            // Never kill an active Azure Speech SDK recognizer; only recover if both recognizers stopped
            if (this.speechRecognizer) {
                return;
            }
            if (!this.webSpeechRecognizer) {
                this.startWebSpeechFallback();
            }
        }, 3000);
    }

    stopSpeechWatchdog() {
        if (this.speechWatchdogTimer) {
            clearInterval(this.speechWatchdogTimer);
            this.speechWatchdogTimer = null;
        }
    }

    startWebSpeechFallback() {
        // On mobile browsers (iOS/Android), native SpeechRecognition steals hardware microphone focus from WebRTC (LiveKit).
        // If LiveKit WebRTC is connected on mobile and Azure Speech SDK is available, prefer re-initializing Azure Speech SDK.
        const isMobileDevice = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || "");
        if (isMobileDevice && this.livekitRoom && this.livekitRoom.state === "connected" && this.azureData && this.azureData.mode === "live") {
            return false;
        }
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRec) {
            return false;
        }
        try {
            if (this.webSpeechRecognizer) {
                try { this.webSpeechRecognizer.onend = null; this.webSpeechRecognizer.stop(); } catch (_) {}
            }
            const recognizer = new SpeechRec();
            this.webSpeechRecognizer = recognizer;
            this.webSpeechCommittedIndex = -1;
            this.pendingInterimMaxIndex = -1;
            recognizer.lang = this.speakingLang || "en-US";
            recognizer.continuous = true;
            recognizer.interimResults = true;

            recognizer.onspeechstart = () => {
                if (this.isSuppressedByTTS()) return;
                this.hadVoiceInCurrentChunk = true;
                this.triggerSpeakingPulse(this.userDisplayName, 1800);
            };

            recognizer.onresult = async (event) => {
                if (this.isSuppressedByTTS()) return;
                this.hadVoiceInCurrentChunk = true;
                let finalPieces = [];
                let interimPieces = [];
                const startIdx = (typeof this.webSpeechCommittedIndex === "number" ? this.webSpeechCommittedIndex : -1) + 1;

                for (let i = startIdx; i < event.results.length; i++) {
                    const res = event.results[i];
                    if (res && res.isFinal) {
                        // Collect all uncommitted results from startIdx up through i so earlier words are never dropped!
                        for (let j = (this.webSpeechCommittedIndex + 1); j <= i; j++) {
                            const piece = (event.results[j] && event.results[j][0]) ? event.results[j][0].transcript : "";
                            if (piece && piece.trim()) {
                                finalPieces.push(piece.trim());
                            }
                        }
                        this.webSpeechCommittedIndex = i;
                        interimPieces = [];
                    } else if (res && res[0] && res[0].transcript) {
                        const piece = res[0].transcript.trim();
                        if (piece) {
                            interimPieces.push(piece);
                        }
                    }
                }

                if (finalPieces.length > 0) {
                    if (this.interimFlushTimer) {
                        clearTimeout(this.interimFlushTimer);
                        this.interimFlushTimer = null;
                    }
                    this.pendingInterimText = "";
                    const fullFinal = finalPieces.join(" ").trim();
                    const fullClean = this.takeStreamingChunk(fullFinal, true, "webspeech");
                    if (fullClean && !this.isSystemEchoPhrase(fullClean)) {
                        this.triggerSpeakingPulse(this.userDisplayName, 2000);
                        this.renderLiveCaption(this.userDisplayName, fullFinal, null, false);
                        this.postTranscriptSegment(fullClean, null, null);
                    }
                }

                const cleanInterim = interimPieces.join(" ").trim();
                if (cleanInterim && !this.isSystemEchoPhrase(cleanInterim)) {
                    this.pendingInterimText = cleanInterim;
                    this.pendingInterimMaxIndex = event.results.length - 1;
                    this.triggerSpeakingPulse(this.userDisplayName, 1500);
                    this.renderLiveCaption(this.userDisplayName, cleanInterim, null, false);
                    // Continuous speech: push stable words out every ~5 words instead of waiting for a pause
                    const streamChunk = this.takeStreamingChunk(cleanInterim, false, "webspeech");
                    if (streamChunk) {
                        this.postTranscriptSegment(streamChunk, null, null);
                    }
                    if (this.interimFlushTimer) clearTimeout(this.interimFlushTimer);
                    // If the speaker pauses for ~0.65s without Chrome firing isFinal, commit the rest immediately
                    this.interimFlushTimer = setTimeout(() => {
                        this.flushPendingInterimSpeech();
                    }, 650);
                }
            };

            recognizer.onerror = (ev) => {
                if (ev && ev.error === "language-not-supported" && this.webSpeechRecognizer && this.webSpeechRecognizer.lang !== "en-NG") {
                    try { this.webSpeechRecognizer.stop(); } catch (_) {}
                    this.webSpeechRecognizer.lang = "en-NG";
                }
            };

            recognizer.onend = () => {
                if (this.pendingInterimText) {
                    this.flushPendingInterimSpeech();
                }
                this.streamCommittedWords = 0;
                this.webSpeechCommittedIndex = -1;
                this.pendingInterimMaxIndex = -1;
                if (!this.isAudioMuted && this.webSpeechRecognizer === recognizer) {
                    setTimeout(() => {
                        if (!this.isAudioMuted && this.webSpeechRecognizer === recognizer) {
                            try {
                                recognizer.start();
                            } catch (_) {
                                this.startWebSpeechFallback();
                            }
                        }
                    }, 140);
                }
            };

            recognizer.start();
            this.startSpeechWatchdog();
            return true;
        } catch (err) {
            return false;
        }
    }

    async toggleMicrophone(forcedMute = null) {
        const micBtns = document.querySelectorAll("#btn-toggle-mic, #btn-start-speaking");
        const shouldUnmute = forcedMute === null ? this.isAudioMuted : !forcedMute;

        if (shouldUnmute) {
            this.isAudioMuted = false;
            this.azureRetryCount = 0;
            this.lastUnmuteAt = Date.now();
            this.lastRecognizerActivityAt = Date.now();
            this.isSyncingMedia = true;
            micBtns.forEach((btn) => {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> <span>Mic On · Speak Now</span>`;
                btn.style.background = "#16A34A";
                btn.style.borderColor = "#4ADE80";
                btn.style.color = "#FFFFFF";
            });
            this.setMicStatus(`LIVE MICROPHONE ON — Speak in ${this.langNames[this.speakingLang] || this.speakingLang}. Other participants hear your speech in their preferred language.`);

            // Immediately notify backend that participant unmuted
            const syncPromise = this.syncMediaState(false);

            // If room initialization is still in flight, wait for it so LiveKit & Azure tokens are ready
            if (this.initRoomPromise) {
                try { await this.initRoomPromise; } catch (_) {}
            }

            let sharedMicTrack = null;
            if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
                try {
                    const pub = await this.livekitRoom.localParticipant.setMicrophoneEnabled(true);
                    if (pub && pub.track && pub.track.mediaStreamTrack && pub.track.mediaStreamTrack.readyState === "live") {
                        sharedMicTrack = pub.track.mediaStreamTrack;
                    } else if (this.livekitRoom.localParticipant.audioTrackPublications) {
                        this.livekitRoom.localParticipant.audioTrackPublications.forEach((p) => {
                            if (!sharedMicTrack && p && p.track && p.track.mediaStreamTrack && p.track.mediaStreamTrack.readyState === "live") {
                                sharedMicTrack = p.track.mediaStreamTrack;
                            }
                        });
                    }
                } catch (_) {}
            }

            // Share the single hardware microphone stream across LiveKit, Visualizer, and Azure Speech SDK
            await this.startMicAudioVisualizer(sharedMicTrack);
            this.lastUnmuteAt = Date.now();
            await syncPromise;
            this.lastUnmuteAt = Date.now();

            if (this.mediaStream) {
                try { await this.mediaStream.unmuteAudio(); } catch (_) {}
            }
            if (this.azureData) {
                await this.initAzureTranslation(this.azureData);
            }
            if (this.speechRecognizer) {
                this.speechRecognizer.startContinuousRecognitionAsync(
                    () => {
                        this.lastRecognizerActivityAt = Date.now();
                        this.startSpeechWatchdog();
                    },
                    () => {
                        this.speechRecognizer = null;
                        this.startWebSpeechFallback();
                    }
                );
            } else {
                this.startWebSpeechFallback();
            }
        } else {
            this.isAudioMuted = true;
            this.stopSpeechWatchdog();
            if (this.azureInterimFlushTimer) {
                clearTimeout(this.azureInterimFlushTimer);
                this.azureInterimFlushTimer = null;
            }
            if (this.pendingInterimText) {
                this.flushPendingInterimSpeech();
            }
            if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
                try {
                    await this.livekitRoom.localParticipant.setMicrophoneEnabled(false);
                } catch (_) {}
            }
            if (this.speechRecognizer) {
                const sr = this.speechRecognizer;
                this.speechRecognizer = null;
                try { sr.stopContinuousRecognitionAsync(); } catch (_) {}
                try { sr.close(); } catch (_) {}
            }
            if (this.webSpeechRecognizer) {
                const rec = this.webSpeechRecognizer;
                this.webSpeechRecognizer = null;
                try { rec.onend = null; rec.stop(); } catch (_) {}
            }
            this.stopMicAudioVisualizer();
            this.syncMediaState(true);
            if (this.mediaStream) {
                try { await this.mediaStream.muteAudio(); } catch (_) {}
            }
            micBtns.forEach((btn) => {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><line x1="1" y1="1" x2="23" y2="23"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12M15 9.34V4a3 3 0 0 0-5.94-.6"/><path d="M17 16.95A7 7 0 0 1 5 12v-2m14 0v2a7 7 0 0 1-.11 1.23"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> <span>Turn Mic On</span>`;
                btn.style.background = "";
                btn.style.borderColor = "";
                btn.style.color = "";
            });
            this.setMicStatus(`Microphone muted · Click "Turn Mic On" to speak live or type below.`);
        }
        return !this.isAudioMuted;
    }

    async syncMediaState(isMuted) {
        if (!this.switchLangUrl) {
            this.isSyncingMedia = false;
            return;
        }
        this.isSyncingMedia = true;
        try {
            const formData = new URLSearchParams();
            formData.append("action", "update_media_state");
            formData.append("is_muted", isMuted ? "true" : "false");
            await fetch(this.switchLangUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": this.getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData.toString()
            });
        } catch (_) {
        } finally {
            this.isSyncingMedia = false;
        }
    }

    async toggleRaiseHand() {
        if (!this.switchLangUrl) return;
        try {
            const formData = new URLSearchParams();
            formData.append("action", "toggle_hand");
            const resp = await fetch(this.switchLangUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": this.getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData.toString()
            });
            if (resp.ok) {
                const data = await resp.json();
                const handBtn = document.getElementById("btn-raise-hand");
                const handLabel = document.getElementById("btn-raise-hand-label");
                if (handBtn) {
                    if (data.hand_raised) {
                        handBtn.style.background = "#D97706";
                        handBtn.style.borderColor = "#FCD34D";
                        handBtn.style.color = "#FFFFFF";
                        if (handLabel) handLabel.textContent = "Lower Hand";
                    } else {
                        handBtn.style.background = "";
                        handBtn.style.borderColor = "";
                        handBtn.style.color = "";
                        if (handLabel) handLabel.textContent = "Raise Hand";
                    }
                }
                await this.fetchLatestTranscript(false);
            }
        } catch (_) {}
    }

    shutdownAllMedia() {
        if (this.pollTimer) {
            clearInterval(this.pollTimer);
            this.pollTimer = null;
        }
        if (this.tokenRefreshTimer) {
            clearInterval(this.tokenRefreshTimer);
            this.tokenRefreshTimer = null;
        }
        this.stopSpeechWatchdog();
        if (this.interimFlushTimer) {
            clearTimeout(this.interimFlushTimer);
            this.interimFlushTimer = null;
        }
        this.isAudioMuted = true;
        this.stopMicAudioVisualizer();
        if (this.localVideoStream) {
            this.localVideoStream.getTracks().forEach((t) => t.stop());
            this.localVideoStream = null;
        }
        if (this.speechRecognizer) {
            try { this.speechRecognizer.stopContinuousRecognitionAsync(); } catch (_) {}
            try { this.speechRecognizer.close(); } catch (_) {}
            this.speechRecognizer = null;
        }
        if (this.webSpeechRecognizer) {
            try { this.webSpeechRecognizer.onend = null; this.webSpeechRecognizer.stop(); } catch (_) {}
            this.webSpeechRecognizer = null;
        }
        if (this.livekitRoom) {
            try { this.livekitRoom.disconnect(); } catch (_) {}
            this.livekitRoom = null;
        }
        if (this.remoteAudioElements) {
            this.remoteAudioElements.clear();
        }
        this.clearAudioQueue();
    }

    async toggleCamera() {
        const camBtns = document.querySelectorAll("#btn-toggle-cam");
        const stageVideo = document.getElementById("live-stage-video") || document.getElementById("prejoin-preview");
        const speakerAvatarBox = document.getElementById("stage-avatar-container");
        const camNotice = document.getElementById("stage-camera-notice");

        if (this.isVideoOff) {
            camBtns.forEach((btn) => {
                btn.textContent = "Starting Camera...";
            });
            try {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    throw new Error("Camera API unavailable in this browser.");
                }
                if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
                    try { await this.livekitRoom.localParticipant.setCameraEnabled(true); } catch (_) {}
                }
                this.localVideoStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
                if (stageVideo) {
                    stageVideo.srcObject = this.localVideoStream;
                    stageVideo.style.display = "block";
                    try { await stageVideo.play(); } catch (_) {}
                }
                if (speakerAvatarBox) {
                    speakerAvatarBox.style.display = "none";
                }
                if (camNotice) {
                    camNotice.style.display = "none";
                }
                this.isVideoOff = false;
                camBtns.forEach((btn) => {
                    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> <span>Camera On</span>`;
                    btn.style.background = "#16A34A";
                    btn.style.borderColor = "#4ADE80";
                    btn.style.color = "#FFFFFF";
                });
                this.setMicStatus("Live camera video active on stage.");
            } catch (err) {
                this.isVideoOff = true;
                camBtns.forEach((btn) => {
                    btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"/><line x1="1" y1="1" x2="23" y2="23"/></svg> <span>Camera Unavailable</span>`;
                });
                if (camNotice) {
                    camNotice.textContent = "Webcam is unavailable or in use by another application — Audio & Live Translation Stage is active.";
                    camNotice.style.display = "block";
                }
                this.setMicStatus("Webcam unavailable or blocked by browser — continuing with Voice & Interpretation stage.");
            }
        } else {
            if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
                try { await this.livekitRoom.localParticipant.setCameraEnabled(false); } catch (_) {}
            }
            if (this.localVideoStream) {
                this.localVideoStream.getTracks().forEach((t) => t.stop());
                this.localVideoStream = null;
            }
            if (stageVideo) {
                stageVideo.srcObject = null;
                if (stageVideo.id === "live-stage-video") stageVideo.style.display = "none";
            }
            if (speakerAvatarBox) {
                speakerAvatarBox.style.display = "flex";
            }
            if (camNotice) {
                camNotice.style.display = "none";
            }
            this.isVideoOff = true;
            camBtns.forEach((btn) => {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> <span>Turn Camera On</span>`;
                btn.style.background = "";
                btn.style.borderColor = "";
                btn.style.color = "";
            });
            this.setMicStatus("Camera turned off.");
        }
    }

    notifyTTSState(isStarting, durationMs = 2400) {
        if (isStarting) {
            this.ttsSuppressionUntil = Date.now() + Math.min(durationMs, 4500);
        } else {
            this.ttsSuppressionUntil = Date.now() + 350;
        }
    }

    clearAudioQueue() {
        this.audioPlaybackQueue = [];
        this.isPlayingQueueItem = false;
        if (this.currentAudioEl) {
            try {
                this.currentAudioEl.onended = null;
                this.currentAudioEl.onerror = null;
                this.currentAudioEl.pause();
            } catch (_) {}
            this.currentAudioEl = null;
        }
        if ("speechSynthesis" in window) {
            try { window.speechSynthesis.cancel(); } catch (_) {}
        }
        this.updateRemoteWebRTCAudioVolumes();
    }

    enqueueRawAudioChunk(audioDataUrl, speakerName) {
        if (!audioDataUrl) return;
        this.lastRawAudioDataUrl = audioDataUrl;
        if (this.isSpeakerAudioMuted) return;
        if (this.audioPlaybackQueue.length >= 8) {
            this.audioPlaybackQueue.shift();
        }
        this.audioPlaybackQueue.push({
            type: "raw",
            audioDataUrl,
            speakerName: speakerName || "Speaker"
        });
        this.processAudioQueue();
    }

    speakTranslation(text, azureData = null, forcePlay = false, langOverride = null) {
        if (!this.isTranslationEnabled) return;
        if (!text || this.isSystemEchoPhrase(text)) return;
        if (this.isSpeakerAudioMuted && !forcePlay) return;

        const targetLang = langOverride || this.listeningLang || "fr-FR";
        const cleanText = String(text).replace(/^\[[^\]]+\]\s*/, "").trim();
        if (!cleanText) return;

        if (forcePlay) {
            this.clearAudioQueue();
        }
        if (this.audioPlaybackQueue.length >= 10) {
            this.audioPlaybackQueue.shift();
        }
        let preloadedAudio = null;
        if (this.ttsUrl) {
            try {
                const audioUrl = `${this.ttsUrl}?text=${encodeURIComponent(cleanText)}&lang=${encodeURIComponent(targetLang)}`;
                preloadedAudio = new Audio();
                preloadedAudio.preload = "auto";
                preloadedAudio.playsInline = true;
                preloadedAudio.src = audioUrl;
                preloadedAudio.load();
            } catch (_) {
                preloadedAudio = null;
            }
        }
        this.audioPlaybackQueue.push({
            type: "tts",
            text: cleanText,
            lang: targetLang,
            preloadedAudio: preloadedAudio
        });
        this.processAudioQueue();
    }

    processAudioQueue() {
        if (this.isPlayingQueueItem) return;
        if (this.isSpeakerAudioMuted || this.audioPlaybackQueue.length === 0) {
            this.isPlayingQueueItem = false;
            this.updateRemoteWebRTCAudioVolumes();
            return;
        }
        const item = this.audioPlaybackQueue.shift();
        if (!item) return;

        this.isPlayingQueueItem = true;
        this.updateRemoteWebRTCAudioVolumes();
        let finished = false;
        const estTimeout = item.type === "raw"
            ? 3600
            : Math.min(18000, Math.max(4500, String(item.text || "").length * 110));

        const safetyTimer = setTimeout(() => {
            finishItem();
        }, estTimeout);

        const finishItem = () => {
            if (finished) return;
            finished = true;
            clearTimeout(safetyTimer);
            this.currentAudioEl = null;
            this.isPlayingQueueItem = false;
            this.updateRemoteWebRTCAudioVolumes();
            this.notifyTTSState(false);
            setTimeout(() => this.processAudioQueue(), 15);
        };

        if (item.type === "raw" && item.audioDataUrl) {
            try {
                const audio = new Audio(item.audioDataUrl);
                audio.playsInline = true;
                this.currentAudioEl = audio;
                audio.onended = () => finishItem();
                audio.onerror = () => finishItem();
                const playPromise = audio.play();
                if (playPromise && typeof playPromise.catch === "function") {
                    playPromise.catch(() => finishItem());
                }
                return;
            } catch (_) {
                finishItem();
                return;
            }
        }

        const text = item.text;
        const targetLang = item.lang || this.listeningLang || "fr-FR";
        this.notifyTTSState(true, estTimeout);

        if (this.ttsUrl) {
            try {
                const audio = item.preloadedAudio || this.ttsAudioPlayer || new Audio();
                if (!item.preloadedAudio) {
                    const audioUrl = `${this.ttsUrl}?text=${encodeURIComponent(text)}&lang=${encodeURIComponent(targetLang)}`;
                    audio.src = audioUrl;
                }
                this.currentAudioEl = audio;
                audio.onended = () => finishItem();
                audio.onerror = () => {
                    this.currentAudioEl = null;
                    this.speakWithBrowserSynthesis(text, targetLang, finishItem);
                };
                const playPromise = audio.play();
                if (playPromise && typeof playPromise.catch === "function") {
                    playPromise.catch(() => {
                        this.currentAudioEl = null;
                        this.speakWithBrowserSynthesis(text, targetLang, finishItem);
                    });
                }
                return;
            } catch (_) {}
        }
        this.speakWithBrowserSynthesis(text, targetLang, finishItem);
    }

    speakWithBrowserSynthesis(text, targetLang, onComplete = null) {
        const done = () => {
            this.notifyTTSState(false);
            if (typeof onComplete === "function") onComplete();
        };
        if (!this.isTranslationEnabled || !("speechSynthesis" in window) || !text || this.isSystemEchoPhrase(text)) {
            done();
            return;
        }
        try {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = targetLang || "fr-FR";
            const voices = window.speechSynthesis.getVoices() || [];
            const shortCode = this.getShortLang(targetLang);
            const matchingVoice = voices.find((v) => v.lang.toLowerCase().startsWith(shortCode));
            if (matchingVoice) utterance.voice = matchingVoice;
            utterance.onend = () => done();
            utterance.onerror = () => done();
            window.speechSynthesis.speak(utterance);
        } catch (err) {
            done();
        }
    }

    postTranscriptSegment(originalText, translatedText, targetShort, allTranslations = null) {
        // Serialize posts so streamed chunks of one sentence reach the server (and listeners) in spoken order
        const run = () => this._postTranscriptSegmentNow(originalText, translatedText, targetShort, allTranslations);
        this.transcriptPostChain = (this.transcriptPostChain || Promise.resolve()).then(run, run);
        return this.transcriptPostChain;
    }

    async _postTranscriptSegmentNow(originalText, translatedText, targetShort, allTranslations = null) {
        if (!this.transcriptUrl || !originalText || this.isSystemEchoPhrase(originalText)) return null;
        const normText = originalText.trim().toLowerCase();
        if (this.lastSubmittedText === normText && this.lastSubmittedAt && Date.now() - this.lastSubmittedAt < 2200) {
            return null;
        }
        this.lastSubmittedText = normText;
        this.lastSubmittedAt = Date.now();
        this.recentlySubmittedTexts.set(normText, Date.now());
        try {
            const sourceShort = this.getShortLang(this.speakingLang);
            const translations = allTranslations ? { ...allTranslations } : {};
            if (targetShort && translatedText && !this.isSystemEchoPhrase(translatedText)) {
                translations[targetShort] = translatedText.trim();
            }
            const resp = await fetch(this.transcriptUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": this.getCsrfToken()
                },
                body: JSON.stringify({
                    speaker_name: this.userDisplayName,
                    original_language: this.speakingLang,
                    original_text: originalText,
                    translations: translations
                })
            });
            if (resp.ok) {
                const data = await resp.json();
                if (data.segment) {
                    if (data.segment.id) {
                        this.locallyPostedSegmentIds.add(String(data.segment.id));
                    }
                    this.hasLiveSegments = true;
                    const shortListen = this.getShortLang(this.listeningLang);
                    const tText = (data.segment.translations || {})[shortListen] || data.segment.original_text;
                    const isNewSeq = (data.segment.sequence_number || 0) > this.lastSeenSequence;
                    this.lastSeenSequence = Math.max(this.lastSeenSequence, data.segment.sequence_number || 0);
                    this.lastOriginalText = data.segment.original_text || "";
                    this.lastOriginalLang = data.segment.original_language || this.speakingLang || "en-US";
                    this.triggerSpeakingPulse(data.segment.speaker_name, 2600);
                    this.renderLiveCaption(data.segment.speaker_name, data.segment.original_text, tText, true);
                    // Only auto-speak your own statement if you are solo-testing in a 1-person room with different Speak/Hear languages
                    if (isNewSeq && this.participantCount <= 1 && shortListen !== sourceShort && this.isTranslationEnabled) {
                        this.speakTranslation(tText, this.azureData);
                    }
                }
                return data;
            }
        } catch (err) {
            console.warn("[WDOS Multilingua] Transcript sync warning:", err);
        }
        return null;
    }

    startLivePolling() {
        if (this.pollTimer) clearInterval(this.pollTimer);
        this.fetchLatestTranscript(false);
        this.pollTimer = setInterval(() => {
            this.fetchLatestTranscript(true);
        }, 450);
    }

    async fetchLatestTranscript(speakNewSegments = true) {
        if (!this.transcriptUrl || this.isFetchingTranscript) return;
        this.isFetchingTranscript = true;
        try {
            const shortListen = this.getShortLang(this.listeningLang);
            const audioSeqParam = this.lastSeenAudioSeq >= 0 ? `&after_audio_seq=${this.lastSeenAudioSeq}` : "";
            const resp = await fetch(`${this.transcriptUrl}?lang=${encodeURIComponent(shortListen)}${audioSeqParam}`, {
                headers: { "Accept": "application/json" }
            });
            if (!resp.ok) return;
            const data = await resp.json();

            // 1. Check if the meeting was ended by the Host/Co-Host
            if (data.room_status === "COMPLETED") {
                this.shutdownAllMedia();
                if (!document.getElementById("meeting-ended-screen")) {
                    window.location.reload();
                }
                return;
            }

            // 2. Check if the current participant was muted, removed, or promoted by the Host
            if (typeof data.is_host === "boolean") {
                this.isHost = data.is_host;
            }
            if (data.my_participant) {
                if (data.my_participant.admission_status === "REMOVED" || data.my_participant.admission_status === "DENIED") {
                    this.shutdownAllMedia();
                    window.location.href = this.isGuest ? "/auth/login/" : "/foundation/meetings/";
                    return;
                }
                // Only force-mute when the Host explicitly clicked Mute / Mute All (connection_status === "Muted by Host")
                if (
                    data.my_participant.is_muted &&
                    data.my_participant.connection_status === "Muted by Host" &&
                    !this.isAudioMuted &&
                    !this.isSyncingMedia &&
                    Date.now() - (this.lastUnmuteAt || 0) > 4500
                ) {
                    await this.toggleMicrophone(true);
                    this.setMicStatus("Your microphone was muted by the meeting host.");
                }
            }

            // 3. Process fallback original voice audio chunks only if LiveKit WebRTC is not connected
            if (typeof data.latest_audio_seq === "number") {
                if (this.lastSeenAudioSeq < 0) {
                    this.lastSeenAudioSeq = data.latest_audio_seq;
                } else if (!this.hasActiveRemoteWebRTCAudio() && Array.isArray(data.audio_chunks) && data.audio_chunks.length > 0) {
                    for (const chunk of data.audio_chunks) {
                        if (chunk.seq > this.lastSeenAudioSeq) {
                            this.lastSeenAudioSeq = chunk.seq;
                            if (chunk.speaker_name !== this.userDisplayName) {
                                this.triggerSpeakingPulse(chunk.speaker_name, 2200);
                                this.lastReceivedRawAudioAt = Date.now();
                                this.lastRawAudioDataUrl = chunk.audio_data_url;
                                if (!this.isTranslationEnabled && speakNewSegments) {
                                    this.enqueueRawAudioChunk(chunk.audio_data_url, chunk.speaker_name);
                                }
                            }
                        }
                    }
                } else {
                    this.lastSeenAudioSeq = Math.max(this.lastSeenAudioSeq, data.latest_audio_seq);
                }
            }

            if (data.active_speaker_name) {
                const nameEl = document.getElementById("stage-speaker-name");
                const roleEl = document.getElementById("stage-speaker-role");
                const avatarEl = document.getElementById("stage-speaker-initials");
                if (nameEl) nameEl.textContent = data.active_speaker_name;
                if (roleEl && data.active_speaker_role) roleEl.textContent = data.active_speaker_role;
                if (avatarEl) {
                    const parts = data.active_speaker_name.trim().split(/\s+/);
                    avatarEl.textContent = parts.slice(0, 2).map((p) => p[0] || "").join("").toUpperCase() || "SP";
                }
            }

            if (typeof data.allow_guest_access === "boolean") {
                const guestBadge = document.getElementById("badge-guest-access");
                const guestInput = document.getElementById("input-toggle-room-access");
                const guestBtn = document.getElementById("btn-toggle-room-access");
                if (guestBadge) {
                    guestBadge.textContent = data.allow_guest_access ? "Anyone with link" : "WDOS accounts only";
                    guestBadge.style.background = data.allow_guest_access ? "rgba(34,197,94,0.18)" : "rgba(255,255,255,0.1)";
                    guestBadge.style.color = data.allow_guest_access ? "#86EFAC" : "#E5D9E6";
                }
                if (guestInput) guestInput.value = data.allow_guest_access ? "wdos_only" : "anyone_with_link";
                if (guestBtn) guestBtn.innerHTML = `<span>${data.allow_guest_access ? "Restrict to WDOS Only" : "Allow Anyone with Link"}</span>`;
            }

            if (typeof data.bypass_lobby === "boolean") {
                const lobbyBadge = document.getElementById("badge-lobby-policy");
                const lobbyInput = document.getElementById("input-toggle-lobby-policy");
                const lobbyBtn = document.getElementById("btn-toggle-lobby-policy");
                if (lobbyBadge) {
                    lobbyBadge.textContent = data.bypass_lobby ? "Lobby: Bypass On" : "Lobby: Host Admits";
                    lobbyBadge.style.background = data.bypass_lobby ? "rgba(56,189,248,0.18)" : "rgba(245,158,11,0.18)";
                    lobbyBadge.style.color = data.bypass_lobby ? "#7DD3FC" : "#FCD34D";
                }
                if (lobbyInput) lobbyInput.value = data.bypass_lobby ? "wait_in_lobby" : "bypass_lobby";
                if (lobbyBtn) lobbyBtn.innerHTML = `<span>${data.bypass_lobby ? "Require Lobby" : "Bypass Lobby"}</span>`;
            }

            if (Array.isArray(data.waiting_participants)) {
                this.renderWaitingRoomQueue(data.waiting_participants);
            }

            if (Array.isArray(data.participants)) {
                this.participantCount = data.participants.length;
                data.participants.forEach((p) => {
                    if (p && p.id && p.speaking_language) {
                        this.participantLanguagesById.set(String(p.id), p.speaking_language);
                    }
                    if (p && p.participant_name && p.speaking_language) {
                        this.participantLanguagesByName.set(String(p.participant_name), p.speaking_language);
                    }
                });
                this.updateRemoteWebRTCAudioVolumes();
                this.renderParticipantsList(data.participants);
            }

            const segments = data.segments || [];
            if (segments.length > 0) {
                this.hasLiveSegments = true;
                this.renderTranscriptFeed(segments);
                const latest = segments[segments.length - 1];
                const translated = (latest.translations || {})[shortListen] || latest.translated_text || latest.original_text;
                this.lastTranslatedText = translated;
                this.lastOriginalText = latest.original_text || "";
                this.lastOriginalLang = latest.original_language || "en-US";
                this.renderLiveCaption(latest.speaker_name, latest.original_text, translated, true);

                const prevSeq = this.lastSeenSequence;
                const newSegments = segments.filter((s) => s.sequence_number > prevSeq);
                if (newSegments.length > 0) {
                    this.lastSeenSequence = newSegments[newSegments.length - 1].sequence_number;
                    if (speakNewSegments && prevSeq >= 0) {
                        for (const seg of newSegments) {
                            const segKey = String(seg.id || seg.sequence_number);
                            if (this.spokenSegmentIds.has(segKey)) continue;
                            this.spokenSegmentIds.add(segKey);

                            this.triggerSpeakingPulse(seg.speaker_name, 3200);
                            if (seg.speaker_name && seg.original_language) {
                                this.participantLanguagesByName.set(String(seg.speaker_name), seg.original_language);
                                this.updateRemoteWebRTCAudioVolumes();
                            }
                            const normSegText = String(seg.original_text || "").trim().toLowerCase();
                            const subTs = this.recentlySubmittedTexts.get(normSegText) || 0;
                            const isLocallyPosted =
                                this.locallyPostedSegmentIds.has(String(seg.id)) ||
                                (subTs > 0 && Date.now() - subTs < 7500);
                            const isOtherSpeaker = !isLocallyPosted;
                            const isDifferentLang = this.getShortLang(this.listeningLang) !== this.getShortLang(seg.original_language);
                            if (isOtherSpeaker || (this.participantCount <= 1 && isDifferentLang)) {
                                // Only synthesize AI translated voice when Real-Time Translation is ON.
                                // When Real-Time Translation is OFF, listeners hear ONLY the speaker's real human voice over WebRTC.
                                // When Real-Time Translation is ON and the speaker speaks the SAME language as the listener while WebRTC audio is active,
                                // the listener already hears their real human voice live via WebRTC.
                                if (this.isTranslationEnabled && (isDifferentLang || !this.hasActiveRemoteWebRTCAudio())) {
                                    const segTrans = (seg.translations || {})[shortListen] || seg.translated_text || seg.original_text;
                                    this.speakTranslation(segTrans, this.azureData, false, this.listeningLang);
                                }
                            }
                        }
                    }
                }
            } else {
                this.hasLiveSegments = false;
                const langName = this.langNames[this.listeningLang] || this.listeningLang;
                const transLabelEl = document.getElementById("caption-translated-label");
                const transTextEl = document.getElementById("caption-translated-text");
                const readyPrompt = this.readyPrompts[this.listeningLang] || this.readyPrompts["en-US"];
                if (transLabelEl) transLabelEl.textContent = `[${langName}]:`;
                if (transTextEl) transTextEl.textContent = readyPrompt;
                this.lastTranslatedText = readyPrompt;
            }
        } catch (err) {
            // Ignore transient polling errors
        } finally {
            this.isFetchingTranscript = false;
        }
    }

    renderTranscriptFeed(segments) {
        const container = document.getElementById("live-transcript-feed");
        const countEl = document.getElementById("live-transcript-count");
        if (countEl) countEl.textContent = `${segments.length}`;
        if (!container) return;

        const shortListen = this.getShortLang(this.listeningLang);
        const langName = this.langNames[this.listeningLang] || "Translated";
        container.innerHTML = segments.slice().reverse().map((seg) => {
            const tr = seg.translations || {};
            const myLangText = tr[shortListen] || seg.translated_text || seg.original_text;
            return `
              <div class="zm-msg-card">
                <div class="zm-msg-header">
                  <strong>${this.escapeHtml(seg.speaker_name)}</strong>
                  <span class="zm-msg-badge">${this.escapeHtml(langName)}</span>
                </div>
                <div class="zm-msg-translated">${this.escapeHtml(myLangText)}</div>
                <div class="zm-msg-original">Original: ${this.escapeHtml(seg.original_text)}</div>
              </div>
            `;
        }).join("");
    }

    renderWaitingRoomQueue(waitingList, force = false) {
        const container = document.getElementById("waiting-room-container");
        if (!container) return;
        const cleanList = Array.isArray(waitingList)
            ? waitingList.filter((wp) => wp && String(wp.participant_name || "").trim().length > 0)
            : [];
        const sig = JSON.stringify(cleanList);
        if (!force && this.lastWaitingSig === sig) {
            return;
        }
        this.lastWaitingSig = sig;
        if (!this.isHost || cleanList.length === 0) {
            container.innerHTML = "";
            return;
        }
        const csrf = this.escapeHtml(this.getCsrfToken());
        const actionUrl = this.escapeHtml(this.switchLangUrl || `/foundation/rooms/${this.roomCode}/live/`);
        const rowsHtml = cleanList.map((wp) => `
          <div style="display:flex; justify-content:space-between; align-items:center; gap:8px; margin-bottom:6px; padding-top:6px; border-top:1px dashed #FDE68A;">
            <div>
              <div style="font-size:12.5px; font-weight:700; color:#19131A;">${this.escapeHtml(wp.participant_name)}</div>
              <div style="font-size:11px; color:#78350F;">Speaks ${this.escapeHtml(wp.speaking_language_display || "English")} · Hears ${this.escapeHtml(wp.listening_language_display || "French")}</div>
            </div>
            <div style="display:flex; gap:6px;">
              <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                <input type="hidden" name="action" value="admit">
                <input type="hidden" name="participant_id" value="${this.escapeHtml(wp.id)}">
                <button type="submit" style="background:#16A34A; color:#FFF; border:none; border-radius:6px; padding:4px 10px; font-size:11px; font-weight:700; cursor:pointer;">Admit</button>
              </form>
              <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                <input type="hidden" name="action" value="deny">
                <input type="hidden" name="participant_id" value="${this.escapeHtml(wp.id)}">
                <button type="submit" style="background:#FEE2E2; color:#991B1B; border:none; border-radius:6px; padding:4px 10px; font-size:11px; font-weight:700; cursor:pointer;">Deny</button>
              </form>
            </div>
          </div>
        `).join("");

        container.innerHTML = `
          <div id="waiting-room-queue" style="margin-bottom:12px; padding:10px 12px; border-radius:12px; background:#FFFBEB; border:1px solid #FDE68A;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <span style="font-size:12px; font-weight:800; color:#92400E;">Waiting Lobby (${cleanList.length})</span>
              <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                <input type="hidden" name="action" value="admit_all">
                <button type="submit" style="background:#D97706; color:#FFF; border:none; border-radius:6px; padding:3px 9px; font-size:11px; font-weight:700; cursor:pointer;">Admit All</button>
              </form>
            </div>
            ${rowsHtml}
          </div>
        `;
    }

    renderParticipantsList(participants, force = false) {
        const container = document.getElementById("live-participants-list");
        const countEl = document.getElementById("live-participants-count");
        if (countEl) countEl.textContent = `${participants.length}`;
        if (!container) return;
        const sig = JSON.stringify(participants);
        if (!force && this.lastParticipantsSig === sig) {
            return;
        }
        this.lastParticipantsSig = sig;

        const csrf = this.escapeHtml(this.getCsrfToken());
        const actionUrl = this.escapeHtml(this.switchLangUrl || `/foundation/rooms/${this.roomCode}/live/`);

        container.innerHTML = participants.map((p) => {
            const parts = String(p.participant_name || "P").trim().split(/\s+/);
            const initials = parts.slice(0, 2).map((w) => w[0] || "").join("").toUpperCase() || "P";
            const handBadge = p.hand_raised ? `<span style="font-size:11px; color:#D97706; margin-left:4px;">&#9995; Hand Raised</span>` : "";
            const hostControls = (this.isHost && p.meeting_role !== "Host") ? `
              <div style="width:100%; display:flex; justify-content:flex-end; gap:6px; margin-top:6px; padding-top:6px; border-top:1px dashed #EFE6EE;">
                <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                  <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                  <input type="hidden" name="action" value="mute_participant">
                  <input type="hidden" name="participant_id" value="${this.escapeHtml(p.id)}">
                  <button type="submit" style="background:#F3F4F6; color:#374151; border:1px solid #D1D5DB; border-radius:6px; padding:2px 8px; font-size:11px; font-weight:700; cursor:pointer;">Mute</button>
                </form>
                <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                  <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                  <input type="hidden" name="action" value="toggle_cohost">
                  <input type="hidden" name="participant_id" value="${this.escapeHtml(p.id)}">
                  <button type="submit" style="background:#FCEEF5; color:#D4006A; border:1px solid #F4C2DA; border-radius:6px; padding:2px 8px; font-size:11px; font-weight:700; cursor:pointer;">${p.meeting_role === "Co-Host" ? "Remove Co-Host" : "Make Co-Host"}</button>
                </form>
                <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                  <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                  <input type="hidden" name="action" value="remove_participant">
                  <input type="hidden" name="participant_id" value="${this.escapeHtml(p.id)}">
                  <button type="submit" style="background:#FEE2E2; color:#991B1B; border:1px solid #FCA5A5; border-radius:6px; padding:2px 8px; font-size:11px; font-weight:700; cursor:pointer;">Remove</button>
                </form>
              </div>
            ` : "";
            return `
              <div class="zm-person-row" style="flex-wrap:wrap;">
                <div class="zm-person-avatar">${this.escapeHtml(initials)}</div>
                <div class="zm-person-info">
                  <div class="zm-person-name">${this.escapeHtml(p.participant_name)}${handBadge}</div>
                  <div class="zm-person-meta">${this.escapeHtml(p.meeting_role)} · Speaks ${this.escapeHtml(p.speaking_language_display)} · Hears <strong>${this.escapeHtml(p.listening_language_display)}</strong></div>
                </div>
                <span class="zm-person-status">${this.escapeHtml(p.connection_status || "Online")}</span>
                ${hostControls}
              </div>
            `;
        }).join("");
    }

    async persistLanguageSelection() {
        if (!this.switchLangUrl) return;
        try {
            const formData = new URLSearchParams();
            formData.append("action", "switch_language");
            formData.append("speaking_language", this.speakingLang);
            formData.append("listening_language", this.listeningLang);
            await fetch(this.switchLangUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": this.getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData.toString()
            });
        } catch (err) {
            // Ignore transient network errors
        }
    }

    switchListeningLanguage(newLangCode) {
        const normalized = this.normalizeLangCode(newLangCode, "fr-FR");
        this.listeningLang = normalized;
        this.updateRemoteWebRTCAudioVolumes();
        const langName = this.langNames[normalized] || normalized;
        const headerLabel = document.getElementById("caption-header-label");
        if (headerLabel) headerLabel.textContent = `LIVE TRANSLATION (${langName.toUpperCase()})`;
        const playBtn = document.getElementById("btn-play-translation-label");
        if (playBtn) playBtn.textContent = `Replay Voice (${langName})`;
        const colLang = document.getElementById("transcript-col-lang");
        if (colLang) colLang.textContent = langName.toUpperCase();
        const transLabelEl = document.getElementById("caption-translated-label");
        if (transLabelEl) transLabelEl.textContent = `[${langName}]:`;
        if (!this.hasLiveSegments) {
            const readyPrompt = this.readyPrompts[normalized] || this.readyPrompts["en-US"];
            const transTextEl = document.getElementById("caption-translated-text");
            if (transTextEl) transTextEl.textContent = readyPrompt;
            this.lastTranslatedText = readyPrompt;
        }
        this.setMicStatus(`Connected as ${this.userDisplayName} · Speaking ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing ${langName}`);
    }

    async restoreAudio() {
        try {
            if (this.livekitRoom && typeof this.livekitRoom.startAudio === "function") {
                try { await this.livekitRoom.startAudio(); } catch (_) {}
            } else if (this.livekitData && this.livekitData.enabled) {
                await this.initLiveKitMedia(this.livekitData);
            }
            if (this.mediaStream) {
                await this.mediaStream.stopAudio();
                await this.mediaStream.startAudio({ mute: this.isAudioMuted });
            }
            const resp = await fetch(this.restoreAudioUrl, {
                method: "POST",
                headers: { "X-CSRFToken": this.getCsrfToken() }
            });
            this.isAudioDegraded = false;
            const alertEl = document.getElementById("room-degraded-banner");
            if (alertEl) alertEl.style.display = "none";
            return await resp.json();
        } catch (err) {
            return null;
        }
    }

    renderLiveCaption(speaker, originalText, translatedText, isFinal) {
        const container = document.getElementById("caption-container");
        const speakerEl = document.getElementById("caption-speaker");
        const textEl = document.getElementById("caption-text");
        const transWrapEl = document.getElementById("caption-translated-wrap");
        const transLabelEl = document.getElementById("caption-translated-label");
        const transTextEl = document.getElementById("caption-translated-text");
        if (!container || !speakerEl || !textEl) return;

        speakerEl.textContent = `${speaker}:`;
        textEl.textContent = originalText;

        const langName = this.langNames[this.listeningLang] || this.listeningLang;
        if (transWrapEl && transTextEl) {
            if (translatedText && !this.isSystemEchoPhrase(translatedText)) {
                transWrapEl.style.display = "block";
                if (transLabelEl) transLabelEl.textContent = `[${langName}]:`;
                transTextEl.textContent = translatedText;
                this.lastTranslatedText = translatedText;
            }
        }
        container.style.opacity = isFinal ? "1.0" : "0.88";
    }

    setMicStatus(msg) {
        const el = document.getElementById("live-mic-status");
        if (el) el.textContent = msg;
    }

    triggerWaitingRoomUI() {
        if (document.getElementById("waiting-lobby-screen") || document.getElementById("prejoin-screen")) {
            return;
        }
        if (window.location.pathname.indexOf("/waiting/") === -1 && this.roomCode) {
            window.location.href = `/foundation/rooms/${this.roomCode}/waiting/`;
        }
    }

    triggerDegradedModeUI(reason) {
        this.isAudioDegraded = true;
        const alertEl = document.getElementById("room-degraded-banner");
        if (alertEl) {
            alertEl.style.display = "flex";
            const msgEl = alertEl.querySelector(".degraded-reason");
            if (msgEl && reason) msgEl.textContent = reason;
        }
    }

    updateDiagnosticsUI(stateLabel, latencyMs) {
        const latEl = document.getElementById("diag-latency-ms");
        if (latEl) latEl.textContent = `${latencyMs} ms`;
    }

    getCsrfToken() {
        const input = document.querySelector("input[name='csrfmiddlewaretoken']");
        if (input) return input.value;
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : "";
    }

    escapeHtml(str) {
        return String(str || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }
}

window.WDOSMultilinguaMeeting = WDOSMultilinguaMeeting;
