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
        this.serverBotConnected = false;
        this.botLanguageTracks = new Map();
        this.botActiveSpeakerByLang = new Map();
        this.lastServerCaptionAt = 0;
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
                this.publishLangChangeToBot();
                await this.persistLanguageSelection();
                await this.fetchLatestTranscript(false);
                if (this.lastTranslatedText && !this.hasSubscribedBotTrack(this.getShortLang(this.listeningLang))) {
                    this.speakTranslation(this.lastTranslatedText, this.azureData, true);
                }
            });
        }

        const speakLangSelect = document.getElementById("quick-speaking-lang");
        if (speakLangSelect) {
            speakLangSelect.addEventListener("change", async () => {
                const wasUnmuted = !this.isAudioMuted;
                if (wasUnmuted && !this.hasServerTranslationBot()) {
                    await this.toggleMicrophone();
                }
                this.speakingLang = speakLangSelect.value;
                if (this.myParticipantId) {
                    this.participantLanguagesById.set(String(this.myParticipantId), this.speakingLang);
                }
                if (this.userDisplayName) {
                    this.participantLanguagesByName.set(String(this.userDisplayName), this.speakingLang);
                }
                this.publishLangChangeToBot();
                this.setMicStatus(`Speaking: ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing: ${this.langNames[this.listeningLang] || this.listeningLang}`);
                await this.persistLanguageSelection();
                if (!this.hasServerTranslationBot()) {
                    if (this.speechRecognizer) {
                        try { this.speechRecognizer.close(); } catch (_) {}
                        this.speechRecognizer = null;
                    }
                    await this.initAzureTranslation(this.azureData);
                    if (wasUnmuted) {
                        await this.toggleMicrophone();
                    }
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

            const isBotParticipant = (participant) => {
                const ident = participant ? String(participant.identity || "") : "";
                return ident.startsWith("wdos-translator-bot");
            };

            const checkBotPresence = () => {
                let foundBot = false;
                if (room.remoteParticipants && typeof room.remoteParticipants.forEach === "function") {
                    room.remoteParticipants.forEach((p) => {
                        if (isBotParticipant(p)) foundBot = true;
                    });
                }
                this.serverBotConnected = foundBot;
                if (foundBot) {
                    this.stopBrowserSpeechRecognizers();
                }
            };

            const attachAudio = (track, participant, publication = null) => {
                if (!track || track.kind !== "audio") return;
                const botTrack = isBotParticipant(participant);
                const trackName = String((publication && (publication.trackName || publication.name)) || track.name || "");
                const botLang = (botTrack && trackName.startsWith("lang:")) ? trackName.slice(5).toLowerCase() : "";
                const pIdent = participant ? (participant.identity || "p") : "p";
                const pubSid = (publication && (publication.trackSid || publication.sid)) || track.sid || trackName || "audio";
                const key = botTrack ? `bot:${botLang || pubSid}` : `${pIdent}:${pubSid}`;

                const metaLang = botTrack ? "" : syncParticipantMetadata(participant);
                const existing = this.remoteAudioElements.get(key);
                if (existing && existing._lkTrack === track && existing.parentNode === audioContainer) {
                    existing._lkPub = publication || existing._lkPub;
                    if (metaLang) {
                        existing.dataset.speakingLang = metaLang;
                    }
                    this.updateRemoteWebRTCAudioVolumes();
                    return;
                }
                if (existing) {
                    try { if (existing._lkTrack) existing._lkTrack.detach(existing); } catch (_) {}
                    try { track.detach(existing); } catch (_) {}
                    existing.muted = true;
                    existing.volume = 0;
                    try { existing.pause(); } catch (_) {}
                    existing.srcObject = null;
                    if (existing.parentNode) {
                        existing.parentNode.removeChild(existing);
                    }
                }

                try { track.detach(); } catch (_) {}
                const audioEl = track.attach();
                audioEl._lkTrack = track;
                audioEl._lkPub = publication;
                audioEl.playsInline = true;
                audioEl.autoplay = true;
                audioEl.dataset.trackSid = key;
                audioEl.dataset.participantIdentity = participant ? (participant.identity || "") : "";
                audioEl.dataset.participantName = participant ? (participant.name || participant.identity || "Speaker") : "Speaker";
                audioEl.dataset.isBotTrack = botTrack ? "1" : "0";
                audioEl.dataset.botLang = botLang;
                if (metaLang) {
                    audioEl.dataset.speakingLang = metaLang;
                }
                audioContainer.appendChild(audioEl);
                this.remoteAudioElements.set(key, audioEl);
                if (botTrack) {
                    this.serverBotConnected = true;
                    this.stopBrowserSpeechRecognizers();
                    if (botLang) {
                        this.botLanguageTracks.set(botLang, { track, publication, audioEl, key });
                    }
                }
                this.updateRemoteWebRTCAudioVolumes();
                if (typeof room.startAudio === "function") {
                    room.startAudio().then(() => this.updateRemoteWebRTCAudioVolumes()).catch(() => {});
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

            if (LK.RoomEvent.ParticipantConnected) {
                room.on(LK.RoomEvent.ParticipantConnected, (participant) => {
                    if (isBotParticipant(participant)) {
                        this.serverBotConnected = true;
                        this.stopBrowserSpeechRecognizers();
                        this.publishLangChangeToBot();
                    } else {
                        syncParticipantMetadata(participant);
                    }
                    this.updateRemoteWebRTCAudioVolumes();
                });
            }

            if (LK.RoomEvent.ParticipantDisconnected) {
                room.on(LK.RoomEvent.ParticipantDisconnected, (participant) => {
                    if (isBotParticipant(participant)) {
                        this.botLanguageTracks.clear();
                        this.botActiveSpeakerByLang.clear();
                    }
                    checkBotPresence();
                    this.updateRemoteWebRTCAudioVolumes();
                });
            }

            room.on(LK.RoomEvent.TrackSubscribed, (track, publication, participant) => {
                if (track.kind === "audio") {
                    attachAudio(track, participant, publication);
                } else if (track.kind === "video") {
                    attachVideo(track);
                }
            });

            room.on(LK.RoomEvent.TrackUnmuted, (publication, participant) => {
                if (publication && publication.track && publication.track.kind === "audio") {
                    attachAudio(publication.track, participant, publication);
                }
            });

            if (LK.RoomEvent.DataReceived) {
                room.on(LK.RoomEvent.DataReceived, (payload, participant, kind, topic) => {
                    try {
                        const rawStr = new TextDecoder().decode(payload);
                        const msg = JSON.parse(rawStr);
                        if (!msg || typeof msg !== "object") return;
                        this.serverBotConnected = true;
                        this.stopBrowserSpeechRecognizers();

                        if (msg.type === "bot_tts_state" && msg.lang) {
                            this.botActiveSpeakerByLang.set(
                                String(msg.lang).toLowerCase(),
                                msg.speaking
                                    ? { speakerName: msg.speaker_name || "", speakerId: msg.speaker_id || "" }
                                    : null
                            );
                            this.updateRemoteWebRTCAudioVolumes();
                            return;
                        }

                        const shortListen = this.getShortLang(this.listeningLang);
                        if (msg.type === "live_interim" && msg.original_text) {
                            this.lastServerCaptionAt = Date.now();
                            this.triggerSpeakingPulse(msg.speaker_name || "Speaker", 1600);
                            const interimTrans = (msg.translations || {})[shortListen] || msg.original_text;
                            this.renderLiveCaption(msg.speaker_name || "Speaker", msg.original_text, interimTrans, false);
                            return;
                        }

                        if (msg.type === "final_segment" && msg.segment) {
                            const seg = msg.segment;
                            this.lastServerCaptionAt = Date.now();
                            const segKey = String(seg.id || seg.sequence_number);
                            const segTrans = (seg.translations || {})[shortListen] || seg.original_text;
                            this.lastSeenSequence = Math.max(this.lastSeenSequence, seg.sequence_number || 0);
                            this.lastTranslatedText = segTrans;
                            this.lastOriginalText = seg.original_text || "";
                            this.lastOriginalLang = seg.original_language || "en-US";
                            this.triggerSpeakingPulse(seg.speaker_name || "Speaker", 2800);
                            this.renderLiveCaption(seg.speaker_name || "Speaker", seg.original_text, segTrans, true);

                            if (seg.speaker_name && seg.original_language) {
                                this.participantLanguagesByName.set(String(seg.speaker_name), seg.original_language);
                                this.updateRemoteWebRTCAudioVolumes();
                            }

                            if (this.hasSubscribedBotTrack(shortListen)) {
                                // The server-side LiveKit bot is already streaming neural audio on the `lang:<shortListen>` WebRTC track!
                                this.spokenSegmentIds.add(segKey);
                            } else if (!this.spokenSegmentIds.has(segKey)) {
                                this.spokenSegmentIds.add(segKey);
                                const isOtherSpeaker = seg.speaker_name !== this.userDisplayName;
                                const isDifferentLang = shortListen !== this.getShortLang(seg.original_language);
                                if (this.isTranslationEnabled && isDifferentLang && (isOtherSpeaker || this.participantCount <= 1)) {
                                    this.speakTranslation(segTrans, this.azureData, false, this.listeningLang);
                                }
                            }
                        }
                    } catch (_) {}
                });
            }

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
                const botTrack = isBotParticipant(participant);
                const trackName = String((publication && (publication.trackName || publication.name)) || track.name || "");
                const botLang = (botTrack && trackName.startsWith("lang:")) ? trackName.slice(5).toLowerCase() : "";
                const pIdent = participant ? (participant.identity || "p") : "p";
                const pubSid = (publication && (publication.trackSid || publication.sid)) || track.sid || trackName || "audio";
                const key = botTrack ? `bot:${botLang || pubSid}` : `${pIdent}:${pubSid}`;
                const el = this.remoteAudioElements.get(key);
                if (el) {
                    const bLang = el.dataset.botLang || "";
                    if (bLang) {
                        this.botLanguageTracks.delete(bLang);
                    }
                    el.muted = true;
                    el.volume = 0;
                    try { el.pause(); } catch (_) {}
                    el.srcObject = null;
                    if (el.parentNode) {
                        el.parentNode.removeChild(el);
                    }
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
                const humanSpeakers = speakers.filter((s) => s && !isBotParticipant(s));
                if (humanSpeakers.length === 0) return;
                const remoteSpeaker = humanSpeakers.find((s) => s.identity !== localId) || humanSpeakers[0];
                if (remoteSpeaker) {
                    const name = remoteSpeaker.name || remoteSpeaker.identity || this.userDisplayName;
                    this.triggerSpeakingPulse(name, 1600);
                    if (remoteSpeaker.identity !== localId) {
                        this.updateRemoteWebRTCAudioVolumes();
                    }
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
                    if (isBotParticipant(participant)) {
                        this.serverBotConnected = true;
                        this.stopBrowserSpeechRecognizers();
                    } else {
                        syncParticipantMetadata(participant);
                    }
                    if (participant.trackPublications && typeof participant.trackPublications.forEach === "function") {
                        participant.trackPublications.forEach((pub) => {
                            if (pub && pub.isSubscribed && pub.track) {
                                if (pub.track.kind === "audio") attachAudio(pub.track, participant, pub);
                                else if (pub.track.kind === "video") attachVideo(pub.track);
                            }
                        });
                    }
                });
            }
            this.publishLangChangeToBot();
            return true;
        } catch (err) {
            console.warn("[WDOS Multilingua] LiveKit WebRTC connection warning:", err);
            this.livekitRoom = null;
            return false;
        }
    }

    hasServerTranslationBot() {
        return Boolean(
            this.serverBotConnected &&
            this.livekitRoom &&
            this.livekitRoom.state === "connected"
        );
    }

    hasSubscribedBotTrack(shortLang) {
        if (!this.hasServerTranslationBot()) return false;
        const entry = this.botLanguageTracks.get(String(shortLang || "").toLowerCase());
        return Boolean(entry && entry.audioEl);
    }

    isMobileBrowser() {
        return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || "");
    }

    shouldUseBrowserSpeechRecognition() {
        // When the server-side LiveKit translation bot is connected, the server handles all speech recognition & translation!
        if (this.hasServerTranslationBot()) {
            return false;
        }
        // On Android/iOS mobile browsers, opening a second microphone stream or webkitSpeechRecognition
        // alongside LiveKit WebRTC steals hardware microphone focus from WebRTC.
        if (this.isMobileBrowser() && this.livekitRoom && this.livekitRoom.state === "connected") {
            return false;
        }
        return true;
    }

    stopBrowserSpeechRecognizers() {
        this.stopSpeechWatchdog();
        if (this.azureInterimFlushTimer) {
            clearTimeout(this.azureInterimFlushTimer);
            this.azureInterimFlushTimer = null;
        }
        if (this.interimFlushTimer) {
            clearTimeout(this.interimFlushTimer);
            this.interimFlushTimer = null;
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
        if (this.azureAudioStream) {
            try { this.azureAudioStream.getTracks().forEach((t) => t.stop()); } catch (_) {}
            this.azureAudioStream = null;
        }
    }

    publishLangChangeToBot() {
        if (!this.livekitRoom || this.livekitRoom.state !== "connected" || !this.livekitRoom.localParticipant) {
            return;
        }
        try {
            const payload = new TextEncoder().encode(
                JSON.stringify({
                    type: "lang_change",
                    participant_id: this.myParticipantId || "",
                    speaking_lang: this.speakingLang,
                    listening_lang: this.listeningLang
                })
            );
            this.livekitRoom.localParticipant.publishData(payload, { reliable: true, topic: "wdos_lang" }).catch(() => {});
        } catch (_) {}
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

        const applyTrackMuteState = (audioEl, shouldPlay) => {
            const trk = audioEl._lkTrack;
            const pub = audioEl._lkPub;
            const isBot = audioEl.dataset.isBotTrack === "1";
            if (shouldPlay) {
                if (isBot && pub && typeof pub.setEnabled === "function") {
                    try { pub.setEnabled(true); } catch (_) {}
                }
                if (trk && typeof trk.setVolume === "function") {
                    try { trk.setVolume(1.0); } catch (_) {}
                }
                if (trk && Array.isArray(trk.attachedElements)) {
                    trk.attachedElements.forEach((el) => {
                        el.muted = false;
                        el.volume = 1.0;
                    });
                }
                audioEl.muted = false;
                audioEl.volume = 1.0;
                if (audioEl.paused && typeof audioEl.play === "function") {
                    audioEl.play().catch(() => {});
                }
            } else {
                if (isBot && pub && typeof pub.setEnabled === "function") {
                    try { pub.setEnabled(false); } catch (_) {}
                }
                if (trk && typeof trk.setVolume === "function") {
                    try { trk.setVolume(0); } catch (_) {}
                }
                if (trk && Array.isArray(trk.attachedElements)) {
                    trk.attachedElements.forEach((el) => {
                        el.muted = true;
                        el.volume = 0;
                    });
                }
                audioEl.muted = true;
                audioEl.volume = 0;
            }
        };

        this.remoteAudioElements.forEach((audioEl) => {
            if (!audioEl) return;
            if (this.isSpeakerAudioMuted) {
                applyTrackMuteState(audioEl, false);
                return;
            }

            const isBotTrack = audioEl.dataset.isBotTrack === "1";
            if (isBotTrack) {
                // When Live Translation is OFF, strictly disable & mute all bot translation tracks!
                if (!this.isTranslationEnabled) {
                    applyTrackMuteState(audioEl, false);
                    return;
                }
                const botLang = (audioEl.dataset.botLang || "").toLowerCase();
                const activeState = this.botActiveSpeakerByLang.get(botLang) || null;
                const isOwnEchoInMultiRoom = Boolean(
                    activeState &&
                    this.participantCount > 1 &&
                    ((activeState.speakerName && activeState.speakerName === this.userDisplayName) ||
                     (activeState.speakerId && this.myParticipantId && String(activeState.speakerId) === String(this.myParticipantId)))
                );
                const shouldPlayBot = Boolean(botLang === shortListen && !isOwnEchoInMultiRoom);
                applyTrackMuteState(audioEl, shouldPlayBot);
                return;
            }

            // Human Participant WebRTC Audio Track:
            if (!this.isTranslationEnabled) {
                // Live Translation OFF: 100% real human voice over WebRTC for all participants
                applyTrackMuteState(audioEl, true);
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

            if (shortSpeaker && shortSpeaker === shortListen) {
                // Same language (e.g., Speaker is English and Listener wants English) -> 100% real human voice!
                applyTrackMuteState(audioEl, true);
            } else if (!shortSpeaker && !this.hasServerTranslationBot()) {
                applyTrackMuteState(audioEl, true);
            } else {
                // Different language while Live Translation is ON:
                // Completely mute the speaker's raw original voice so the listener ONLY hears the translated voice!
                applyTrackMuteState(audioEl, false);
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

    postLiveInterim(originalText, translations = null) {
        if (!this.transcriptUrl || !originalText || this.isSystemEchoPhrase(originalText)) return;
        const now = Date.now();
        if (this.lastInterimPostAt && now - this.lastInterimPostAt < 480 && originalText === this.lastInterimPostedText) {
            return;
        }
        if (this.lastInterimPostAt && now - this.lastInterimPostAt < 380) {
            return;
        }
        this.lastInterimPostAt = now;
        this.lastInterimPostedText = originalText;
        fetch(this.transcriptUrl, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": this.getCsrfToken()
            },
            body: JSON.stringify({
                action: "live_interim",
                speaker_name: this.userDisplayName,
                original_language: this.speakingLang,
                original_text: originalText,
                translations: translations || {}
            })
        }).catch(() => {});
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
                    speechConfig.setProperty(window.SpeechSDK.PropertyId.Speech_SegmentationSilenceTimeoutMs, "450");
                    if (window.SpeechSDK.PropertyId.Speech_SegmentationMaximumTimeMs !== undefined) {
                        speechConfig.setProperty(window.SpeechSDK.PropertyId.Speech_SegmentationMaximumTimeMs, "8000");
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
            const existingTrack = (!this.forceDefaultMicForAzure && this.localAudioStream)
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
            this.azurePendingInterimText = "";
            this.azurePendingInterimTranslations = {};
            this.azureFlushedUtteranceKey = "";

            this.speechRecognizer.recognizing = (s, e) => {
                if (this.isSuppressedByTTS()) return;
                if (!e.result || !e.result.text) return;
                const interimClean = e.result.text.trim();
                if (!interimClean || this.isSystemEchoPhrase(interimClean)) return;

                this.azureRetryCount = 0;
                this.hadAzureRecognitionSinceUnmute = true;
                this.lastRecognizerActivityAt = Date.now();
                this.lastLocalInterimAt = Date.now();
                this.hadVoiceInCurrentChunk = true;
                this.triggerSpeakingPulse(this.userDisplayName, 1400);

                const interimTranslations = {};
                Object.values(azureData.supported_languages || {}).forEach((lang) => {
                    const tVal = e.result.translations ? e.result.translations.get(lang.short) : null;
                    if (tVal && tVal.trim()) {
                        interimTranslations[lang.short] = tVal.trim();
                    }
                });
                const targetShort = this.getShortLang(this.listeningLang);
                const liveTranslation = interimTranslations[targetShort] || null;
                this.renderLiveCaption(this.userDisplayName, interimClean, liveTranslation, false);
                this.postLiveInterim(interimClean, interimTranslations);

                const uttKey = "azure_" + String(e.result.offset ?? e.result.resultId ?? "0");
                this.azurePendingInterimText = interimClean;
                this.azurePendingInterimTranslations = interimTranslations;
                this.azurePendingUttKey = uttKey;

                if (this.azureInterimFlushTimer) {
                    clearTimeout(this.azureInterimFlushTimer);
                }
                // Safety fallback: only if Azure hasn't finalized the utterance after 1.3s of silence, commit the full utterance
                this.azureInterimFlushTimer = setTimeout(() => {
                    this.azureInterimFlushTimer = null;
                    if (this.isAudioMuted) return;
                    const fullPending = (this.azurePendingInterimText || "").trim();
                    const pendingTranslations = this.azurePendingInterimTranslations || {};
                    const pendingKey = this.azurePendingUttKey || "";
                    if (fullPending && !this.isSystemEchoPhrase(fullPending) && this.azureFlushedUtteranceKey !== pendingKey) {
                        this.azureFlushedUtteranceKey = pendingKey;
                        this.azurePendingInterimText = "";
                        const tShort = this.getShortLang(this.listeningLang);
                        const sdkTrans = pendingTranslations[tShort] || null;
                        this.renderLiveCaption(this.userDisplayName, fullPending, sdkTrans, true);
                        this.postTranscriptSegment(fullPending, sdkTrans, tShort, pendingTranslations);
                    }
                }, 1300);
            };

            this.speechRecognizer.recognized = async (s, e) => {
                if (this.azureInterimFlushTimer) {
                    clearTimeout(this.azureInterimFlushTimer);
                    this.azureInterimFlushTimer = null;
                }
                this.azurePendingInterimText = "";
                if (this.isSuppressedByTTS()) return;
                if (e.result && e.result.text && e.result.text.trim()) {
                    const cleanText = e.result.text.trim();
                    if (this.isSystemEchoPhrase(cleanText)) {
                        return;
                    }
                    this.azureRetryCount = 0;
                    this.hadAzureRecognitionSinceUnmute = true;
                    this.lastRecognizerActivityAt = Date.now();
                    this.lastLocalInterimAt = Date.now();
                    const uttKey = "azure_" + String(e.result.offset ?? e.result.resultId ?? "0");
                    if (this.azureFlushedUtteranceKey && this.azureFlushedUtteranceKey === uttKey) {
                        return;
                    }
                    this.azureFlushedUtteranceKey = uttKey;

                    this.hadVoiceInCurrentChunk = true;
                    this.triggerSpeakingPulse(this.userDisplayName, 1800);
                    const targetShort = this.getShortLang(this.listeningLang);
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
        // On mobile browsers (Android Chrome / iOS Safari) when LiveKit WebRTC is connected,
        // do not attach a second AudioContext or clone the hardware microphone track so WebRTC owns the mic exclusively.
        if (this.isMobileBrowser() && this.livekitRoom && this.livekitRoom.state === "connected") {
            return;
        }
        try {
            if (sharedMicTrack && sharedMicTrack.readyState === "live") {
                this.localAudioStream = new MediaStream([sharedMicTrack.clone()]);
            } else if (!this.livekitRoom || this.livekitRoom.state !== "connected") {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
                this.localAudioStream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true
                    },
                    video: false
                });
            } else {
                return;
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
        if (!pendingFull || this.isSystemEchoPhrase(pendingFull)) return;

        const words = pendingFull.split(/\s+/).filter(Boolean);
        const alreadyFlushed = this.webSpeechFlushedWordsCount || 0;
        const remainingWords = words.slice(alreadyFlushed);
        this.webSpeechFlushedWordsCount = words.length;
        const pending = remainingWords.join(" ").trim();
        if (!pending || this.isSystemEchoPhrase(pending)) return;

        this.lastLocalInterimAt = Date.now();
        this.triggerSpeakingPulse(this.userDisplayName, 2000);
        this.renderLiveCaption(this.userDisplayName, pendingFull, null, false);
        await this.postTranscriptSegment(pending, null, null);
    }

    startSpeechWatchdog() {
        this.stopSpeechWatchdog();
        this.speechWatchdogTimer = setInterval(async () => {
            if (this.isAudioMuted) return;
            if (!this.shouldUseBrowserSpeechRecognition()) {
                this.stopBrowserSpeechRecognizers();
                return;
            }
            if (this.speechRecognizer) {
                const now = Date.now();
                const recentlySpoke = this.lastVoiceDetectedAt && (now - this.lastVoiceDetectedAt < 1800);
                const timeSinceStart = now - (this.lastRecognizerActivityAt || this.lastUnmuteAt || now);
                if (
                    recentlySpoke &&
                    !this.hadAzureRecognitionSinceUnmute &&
                    !this.forceDefaultMicForAzure &&
                    timeSinceStart > 3500 &&
                    this.azureData
                ) {
                    this.forceDefaultMicForAzure = true;
                    await this.initAzureTranslation(this.azureData);
                    if (this.speechRecognizer && !this.isAudioMuted) {
                        this.speechRecognizer.startContinuousRecognitionAsync(
                            () => { this.lastRecognizerActivityAt = Date.now(); },
                            () => {
                                this.speechRecognizer = null;
                                this.startWebSpeechFallback();
                            }
                        );
                    }
                }
                return;
            }
            if (!this.webSpeechRecognizer) {
                this.startWebSpeechFallback();
            }
        }, 2500);
    }

    stopSpeechWatchdog() {
        if (this.speechWatchdogTimer) {
            clearInterval(this.speechWatchdogTimer);
            this.speechWatchdogTimer = null;
        }
    }

    startWebSpeechFallback() {
        if (!this.shouldUseBrowserSpeechRecognition() || this.speechRecognizer) {
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
            this.webSpeechFlushedWordsCount = 0;
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
                        for (let j = (this.webSpeechCommittedIndex + 1); j <= i; j++) {
                            let piece = (event.results[j] && event.results[j][0]) ? event.results[j][0].transcript : "";
                            if (piece && piece.trim()) {
                                if (j === (this.webSpeechCommittedIndex + 1) && (this.webSpeechFlushedWordsCount || 0) > 0) {
                                    const pWords = piece.trim().split(/\s+/).filter(Boolean);
                                    piece = pWords.slice(this.webSpeechFlushedWordsCount).join(" ");
                                }
                                if (piece && piece.trim()) {
                                    finalPieces.push(piece.trim());
                                }
                            }
                        }
                        this.webSpeechCommittedIndex = i;
                        this.webSpeechFlushedWordsCount = 0;
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
                    if (fullFinal && !this.isSystemEchoPhrase(fullFinal)) {
                        this.lastLocalInterimAt = Date.now();
                        this.triggerSpeakingPulse(this.userDisplayName, 2000);
                        this.renderLiveCaption(this.userDisplayName, fullFinal, null, false);
                        this.postTranscriptSegment(fullFinal, null, null);
                    }
                }

                const cleanInterim = interimPieces.join(" ").trim();
                if (cleanInterim && !this.isSystemEchoPhrase(cleanInterim)) {
                    this.pendingInterimText = cleanInterim;
                    this.pendingInterimMaxIndex = event.results.length - 1;
                    this.lastLocalInterimAt = Date.now();
                    this.triggerSpeakingPulse(this.userDisplayName, 1500);
                    this.renderLiveCaption(this.userDisplayName, cleanInterim, null, false);
                    this.postLiveInterim(cleanInterim, null);
                    if (this.interimFlushTimer) clearTimeout(this.interimFlushTimer);
                    // Only commit interim words if the speaker pauses for 1.15s without the browser firing isFinal
                    this.interimFlushTimer = setTimeout(() => {
                        this.flushPendingInterimSpeech();
                    }, 1150);
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
                this.webSpeechCommittedIndex = -1;
                this.pendingInterimMaxIndex = -1;
                this.webSpeechFlushedWordsCount = 0;
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
            this.hadAzureRecognitionSinceUnmute = false;
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
            if (this.shouldUseBrowserSpeechRecognition()) {
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
                this.stopBrowserSpeechRecognizers();
            }
        } else {
            this.isAudioMuted = true;
            this.stopSpeechWatchdog();
            if (this.azureInterimFlushTimer) {
                clearTimeout(this.azureInterimFlushTimer);
                this.azureInterimFlushTimer = null;
            }
            if (this.azurePendingInterimText) {
                const fullPending = (this.azurePendingInterimText || "").trim();
                const pendingTranslations = this.azurePendingInterimTranslations || {};
                const pendingKey = this.azurePendingUttKey || "";
                this.azurePendingInterimText = "";
                if (fullPending && !this.isSystemEchoPhrase(fullPending) && this.azureFlushedUtteranceKey !== pendingKey) {
                    this.azureFlushedUtteranceKey = pendingKey;
                    const tShort = this.getShortLang(this.listeningLang);
                    const sdkTrans = pendingTranslations[tShort] || null;
                    this.renderLiveCaption(this.userDisplayName, fullPending, sdkTrans, true);
                    this.postTranscriptSegment(fullPending, sdkTrans, tShort, pendingTranslations);
                }
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
        if (this.ttsAudioPlayer) {
            try {
                this.ttsAudioPlayer.onended = null;
                this.ttsAudioPlayer.onerror = null;
                this.ttsAudioPlayer.pause();
            } catch (_) {}
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
        this.audioPlaybackQueue.push({
            type: "tts",
            text: cleanText,
            lang: targetLang
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
        if (item.type === "tts" && !this.isTranslationEnabled) {
            this.processAudioQueue();
            return;
        }

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

        if (!this.ttsAudioPlayer) {
            this.ttsAudioPlayer = new Audio();
            this.ttsAudioPlayer.preload = "auto";
            this.ttsAudioPlayer.playsInline = true;
        }

        if (item.type === "raw" && item.audioDataUrl) {
            try {
                const audio = this.ttsAudioPlayer;
                audio.src = item.audioDataUrl;
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
                const audio = this.ttsAudioPlayer;
                const audioUrl = `${this.ttsUrl}?text=${encodeURIComponent(text)}&lang=${encodeURIComponent(targetLang)}`;
                audio.src = audioUrl;
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
            const liveInterim = (data.live_interim && data.live_interim.original_text) ? data.live_interim : null;
            const hasActiveLocalInterim = Boolean(
                (this.lastLocalInterimAt && (Date.now() - this.lastLocalInterimAt < 2500)) ||
                (this.lastServerCaptionAt && (Date.now() - this.lastServerCaptionAt < 2500))
            );

            if (segments.length > 0) {
                this.hasLiveSegments = true;
                this.renderTranscriptFeed(segments);
                const latest = segments[segments.length - 1];
                const translated = (latest.translations || {})[shortListen] || latest.translated_text || latest.original_text;

                const prevSeq = this.lastSeenSequence;
                const newSegments = segments.filter((s) => s.sequence_number > prevSeq);

                if (newSegments.length > 0) {
                    // A new finalized segment arrived: update caption bar immediately with the committed segment
                    this.lastTranslatedText = translated;
                    this.lastOriginalText = latest.original_text || "";
                    this.lastOriginalLang = latest.original_language || "en-US";
                    this.renderLiveCaption(latest.speaker_name, latest.original_text, translated, true);
                } else if (liveInterim) {
                    // Someone is actively speaking mid-sentence right now: render their live growing caption & translation!
                    if (liveInterim.speaker_name !== this.userDisplayName || !hasActiveLocalInterim) {
                        this.triggerSpeakingPulse(liveInterim.speaker_name, 1600);
                        const interimTrans = (liveInterim.translations || {})[shortListen] || liveInterim.translated_text || liveInterim.original_text;
                        this.renderLiveCaption(liveInterim.speaker_name, liveInterim.original_text, interimTrans, false);
                    }
                } else if (!hasActiveLocalInterim) {
                    // No active interim speech: keep latest committed segment displayed
                    this.lastTranslatedText = translated;
                    this.lastOriginalText = latest.original_text || "";
                    this.lastOriginalLang = latest.original_language || "en-US";
                    this.renderLiveCaption(latest.speaker_name, latest.original_text, translated, true);
                }

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
                            // If the server-side LiveKit bot is already streaming translated audio on `lang:<shortListen>`,
                            // do not trigger duplicate browser TTS playback!
                            if (this.hasSubscribedBotTrack(shortListen)) {
                                continue;
                            }
                            const normSegText = String(seg.original_text || "").trim().toLowerCase();
                            const subTs = this.recentlySubmittedTexts.get(normSegText) || 0;
                            const isLocallyPosted =
                                this.locallyPostedSegmentIds.has(String(seg.id)) ||
                                (subTs > 0 && Date.now() - subTs < 7500) ||
                                (seg.speaker_name === this.userDisplayName && this.participantCount > 1);
                            const isOtherSpeaker = !isLocallyPosted;
                            const isDifferentLang = this.getShortLang(this.listeningLang) !== this.getShortLang(seg.original_language);
                            if (isOtherSpeaker || (this.participantCount <= 1 && isDifferentLang)) {
                                if (this.isTranslationEnabled && (isDifferentLang || !this.hasActiveRemoteWebRTCAudio())) {
                                    const segTrans = (seg.translations || {})[shortListen] || seg.translated_text || seg.original_text;
                                    this.speakTranslation(segTrans, this.azureData, false, this.listeningLang);
                                }
                            }
                        }
                    }
                }
            } else if (liveInterim) {
                if (liveInterim.speaker_name !== this.userDisplayName || !hasActiveLocalInterim) {
                    this.triggerSpeakingPulse(liveInterim.speaker_name, 1600);
                    const interimTrans = (liveInterim.translations || {})[shortListen] || liveInterim.translated_text || liveInterim.original_text;
                    this.renderLiveCaption(liveInterim.speaker_name, liveInterim.original_text, interimTrans, false);
                }
            } else if (!hasActiveLocalInterim) {
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
