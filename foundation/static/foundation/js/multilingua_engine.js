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
        this.azureData = null;
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
        this.lastSeenSequence = config.initialSequence || 0;
        this.pollTimer = null;
        this.lastTranslatedText = "";
        this.participantCount = 1;
        this.ttsAudioQueue = [];
        this.currentAudioEl = null;

        // Cross-tab acoustic echo lock so two tabs on the same laptop never transcribe each other's TTS output
        this.ttsChannel = null;
        try {
            if ("BroadcastChannel" in window) {
                this.ttsChannel = new BroadcastChannel("wdos_multilingua_tts");
                this.ttsChannel.onmessage = (ev) => {
                    if (!ev.data) return;
                    if (ev.data.type === "tts_start") {
                        this.ttsSuppressionUntil = Math.max(this.ttsSuppressionUntil || 0, Date.now() + (ev.data.durationMs || 2800));
                    } else if (ev.data.type === "tts_end") {
                        this.ttsSuppressionUntil = Date.now() + 650;
                    }
                };
            }
        } catch (_) {}

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

    async boot() {
        if (document.getElementById("waiting-lobby-screen") || document.getElementById("meeting-ended-screen")) {
            return;
        }
        this.switchListeningLanguage(this.listeningLang);
        this.bindUIControls();
        if (document.getElementById("prejoin-screen")) {
            return;
        }
        await this.initializeRoom();
        this.startLivePolling();
    }

    bindUIControls() {
        const micBtns = document.querySelectorAll("#btn-toggle-mic, #btn-start-speaking");
        micBtns.forEach((btn) => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
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

        const ttsToggleBtn = document.getElementById("btn-toggle-tts-audio");
        if (ttsToggleBtn) {
            ttsToggleBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.isSpeakerAudioMuted = !this.isSpeakerAudioMuted;
                const labelEl = document.getElementById("btn-toggle-tts-label");
                if (this.isSpeakerAudioMuted) {
                    if (this.currentAudioEl) {
                        try { this.currentAudioEl.pause(); } catch (_) {}
                        this.currentAudioEl = null;
                    }
                    if ("speechSynthesis" in window) {
                        try { window.speechSynthesis.cancel(); } catch (_) {}
                    }
                    ttsToggleBtn.style.background = "rgba(239,68,68,0.22)";
                    ttsToggleBtn.style.color = "#FCA5A5";
                    ttsToggleBtn.style.borderColor = "rgba(248,113,113,0.4)";
                    if (labelEl) labelEl.textContent = "Voice Output: MUTED";
                } else {
                    ttsToggleBtn.style.background = "rgba(34,197,94,0.18)";
                    ttsToggleBtn.style.color = "#86EFAC";
                    ttsToggleBtn.style.borderColor = "rgba(134,239,172,0.35)";
                    if (labelEl) labelEl.textContent = "Voice Output: ON";
                    if (this.lastTranslatedText) {
                        this.speakTranslation(this.lastTranslatedText, this.azureData, true);
                    }
                }
            });
        }

        const playBtn = document.getElementById("btn-play-translation");
        if (playBtn) {
            playBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.isSpeakerAudioMuted = false;
                const labelEl = document.getElementById("btn-toggle-tts-label");
                if (labelEl) labelEl.textContent = "Voice Output: ON";
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
            const response = await fetch(this.tokensUrl, {
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
            this.zoomData = data.zoom;
            if (data.participant) {
                this.userDisplayName = data.participant.name || this.userDisplayName;
                this.speakingLang = this.normalizeLangCode(data.participant.speaking_lang || this.speakingLang, "en-US");
                this.listeningLang = this.normalizeLangCode(data.participant.listening_lang || this.listeningLang, "fr-FR");
            }
            this.switchListeningLanguage(this.listeningLang);

            await this.initZoomMedia(data.zoom);
            await this.initAzureTranslation(data.azure);
            this.updateDiagnosticsUI("Connected", 34);
            this.setMicStatus(`Connected as ${this.userDisplayName} · Speaking ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing ${this.langNames[this.listeningLang] || this.listeningLang}`);
            return data;
        } catch (err) {
            console.warn("[WDOS Multilingua] Operating in degraded caption fallback:", err);
            this.triggerDegradedModeUI(err.message);
            return null;
        }
    }

    async initZoomMedia(zoomData) {
        if (!window.ZoomVideo || !zoomData) {
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
        return Boolean(this.isPlayingTTS || (this.ttsSuppressionUntil && Date.now() < this.ttsSuppressionUntil));
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
            const speechConfig = window.SpeechSDK.SpeechTranslationConfig.fromAuthorizationToken(
                azureData.token,
                azureData.region
            );
            speechConfig.speechRecognitionLanguage = this.speakingLang;

            if (window.SpeechSDK.PropertyId) {
                try {
                    speechConfig.setProperty(window.SpeechSDK.PropertyId.SpeechServiceConnection_EndSilenceTimeoutMs, "650");
                    speechConfig.setProperty(window.SpeechSDK.PropertyId.Speech_SegmentationSilenceTimeoutMs, "650");
                } catch (_) {}
            }

            const azureSupportedTargets = new Set(["en", "fr", "pt", "ar", "sw"]);
            Object.values(azureData.supported_languages || {}).forEach((lang) => {
                if (lang && lang.short && azureSupportedTargets.has(lang.short)) {
                    speechConfig.addTargetLanguage(lang.short);
                }
            });

            const audioConfig = window.SpeechSDK.AudioConfig.fromDefaultMicrophoneInput();
            this.speechRecognizer = new window.SpeechSDK.TranslationRecognizer(speechConfig, audioConfig);

            this.speechRecognizer.recognizing = (s, e) => {
                if (this.isSuppressedByTTS()) return;
                if (!e.result || !e.result.text) return;
                const interimClean = e.result.text.trim();
                if (!interimClean || this.isSystemEchoPhrase(interimClean)) return;

                this.triggerSpeakingPulse(this.userDisplayName, 1200);
                const targetShort = this.getShortLang(this.listeningLang);
                const sourceShort = this.getShortLang(this.speakingLang);
                let liveTranslation = e.result.translations ? e.result.translations.get(targetShort) : null;
                if (liveTranslation && targetShort !== sourceShort && liveTranslation.trim().toLowerCase() === interimClean.toLowerCase()) {
                    liveTranslation = null;
                }
                this.renderLiveCaption(this.userDisplayName, interimClean, liveTranslation || null, false);
            };

            this.speechRecognizer.recognized = async (s, e) => {
                if (this.isSuppressedByTTS()) return;
                if (e.result && e.result.text && e.result.text.trim()) {
                    const cleanText = e.result.text.trim();
                    if (this.isSystemEchoPhrase(cleanText)) return;

                    this.triggerSpeakingPulse(this.userDisplayName, 1600);
                    const sourceShort = this.getShortLang(this.speakingLang);
                    const allTranslations = {};
                    Object.values(azureData.supported_languages || {}).forEach((lang) => {
                        const tVal = e.result.translations ? e.result.translations.get(lang.short) : null;
                        if (tVal && tVal.trim()) {
                            if (lang.short === sourceShort || tVal.trim().toLowerCase() !== cleanText.toLowerCase()) {
                                allTranslations[lang.short] = tVal.trim();
                            }
                        }
                    });
                    const targetShort = this.getShortLang(this.listeningLang);
                    const sdkTranslation = allTranslations[targetShort] || null;
                    this.renderLiveCaption(this.userDisplayName, cleanText, sdkTranslation, true);
                    await this.postTranscriptSegment(cleanText, sdkTranslation, targetShort, allTranslations);
                    await this.fetchLatestTranscript(false);
                }
            };

            this.speechRecognizer.canceled = () => {
                if (!this.isAudioMuted) {
                    this.startWebSpeechFallback();
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

    async startMicAudioVisualizer() {
        this.resetSpeakingIndicatorState();
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) return;
            this.localAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
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
                const energy = Math.max(rms * 4.2, voiceBinsAvg * 1.45);
                const isVoiceDetected = energy > 0.065;
                const isPulseActive = Date.now() < (this.speechPulseUntil || 0);

                if (isVoiceDetected) {
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
        if (this.visualizerFrame) {
            cancelAnimationFrame(this.visualizerFrame);
            this.visualizerFrame = null;
        }
        if (this.localAudioStream) {
            this.localAudioStream.getTracks().forEach((t) => t.stop());
            this.localAudioStream = null;
        }
        if (this.audioContext) {
            try { this.audioContext.close(); } catch (_) {}
            this.audioContext = null;
        }
        this.analyserNode = null;
        this.resetSpeakingIndicatorState();
    }

    startWebSpeechFallback() {
        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SpeechRec) {
            return false;
        }
        try {
            if (this.webSpeechRecognizer) {
                try { this.webSpeechRecognizer.stop(); } catch (_) {}
            }
            this.webSpeechRecognizer = new SpeechRec();
            this.webSpeechRecognizer.lang = this.speakingLang || "en-US";
            this.webSpeechRecognizer.continuous = true;
            this.webSpeechRecognizer.interimResults = true;

            this.webSpeechRecognizer.onspeechstart = () => {
                if (this.isSuppressedByTTS()) return;
                this.triggerSpeakingPulse(this.userDisplayName, 1800);
            };

            this.webSpeechRecognizer.onresult = async (event) => {
                if (this.isSuppressedByTTS()) return;
                let interimText = "";
                for (let i = event.resultIndex; i < event.results.length; i++) {
                    const transcript = event.results[i][0].transcript;
                    if (event.results[i].isFinal) {
                        const clean = transcript.trim();
                        if (clean && !this.isSystemEchoPhrase(clean)) {
                            this.triggerSpeakingPulse(this.userDisplayName, 2000);
                            this.renderLiveCaption(this.userDisplayName, clean, null, false);
                            await this.postTranscriptSegment(clean, null, null);
                            await this.fetchLatestTranscript(false);
                        }
                    } else {
                        interimText += transcript;
                    }
                }
                const cleanInterim = interimText.trim();
                if (cleanInterim && !this.isSystemEchoPhrase(cleanInterim)) {
                    this.triggerSpeakingPulse(this.userDisplayName, 1500);
                    this.renderLiveCaption(this.userDisplayName, cleanInterim, null, false);
                }
            };

            this.webSpeechRecognizer.onerror = (ev) => {
                if (ev && ev.error === "language-not-supported" && this.webSpeechRecognizer && this.webSpeechRecognizer.lang !== "en-NG") {
                    try { this.webSpeechRecognizer.stop(); } catch (_) {}
                    this.webSpeechRecognizer.lang = "en-NG";
                }
            };

            this.webSpeechRecognizer.onend = () => {
                if (!this.isAudioMuted && this.webSpeechRecognizer) {
                    try { this.webSpeechRecognizer.start(); } catch (_) {}
                }
            };

            this.webSpeechRecognizer.start();
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
            this.lastUnmuteAt = Date.now();
            micBtns.forEach((btn) => {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> <span>Mic On · Speak Now</span>`;
                btn.style.background = "#16A34A";
                btn.style.borderColor = "#4ADE80";
                btn.style.color = "#FFFFFF";
            });
            this.setMicStatus(`LIVE MICROPHONE ON — Speak in ${this.langNames[this.speakingLang] || this.speakingLang}. Other participants hear your speech in their preferred language.`);

            await this.startMicAudioVisualizer();
            this.syncMediaState(false);

            if (this.mediaStream) {
                try { await this.mediaStream.unmuteAudio(); } catch (_) {}
            }
            if (this.speechRecognizer) {
                this.speechRecognizer.startContinuousRecognitionAsync(
                    () => {},
                    () => { this.startWebSpeechFallback(); }
                );
            } else {
                this.startWebSpeechFallback();
            }
        } else {
            this.isAudioMuted = true;
            this.stopMicAudioVisualizer();
            this.syncMediaState(true);
            if (this.mediaStream) {
                try { await this.mediaStream.muteAudio(); } catch (_) {}
            }
            if (this.speechRecognizer) {
                try { this.speechRecognizer.stopContinuousRecognitionAsync(); } catch (_) {}
            }
            if (this.webSpeechRecognizer) {
                const rec = this.webSpeechRecognizer;
                this.webSpeechRecognizer = null;
                try { rec.stop(); } catch (_) {}
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
        if (!this.switchLangUrl) return;
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
        } catch (_) {}
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
            try { this.webSpeechRecognizer.stop(); } catch (_) {}
            this.webSpeechRecognizer = null;
        }
        if (this.currentAudioEl) {
            try { this.currentAudioEl.pause(); } catch (_) {}
            this.currentAudioEl = null;
        }
        if ("speechSynthesis" in window) {
            try { window.speechSynthesis.cancel(); } catch (_) {}
        }
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

    notifyTTSState(isStarting, durationMs = 2600) {
        if (isStarting) {
            this.isPlayingTTS = true;
            this.ttsSuppressionUntil = Date.now() + durationMs;
            if (this.ttsChannel) {
                try { this.ttsChannel.postMessage({ type: "tts_start", durationMs }); } catch (_) {}
            }
        } else {
            this.isPlayingTTS = false;
            this.ttsSuppressionUntil = Date.now() + 650;
            if (this.ttsChannel) {
                try { this.ttsChannel.postMessage({ type: "tts_end" }); } catch (_) {}
            }
        }
    }

    speakTranslation(text, azureData = null, forcePlay = false) {
        if (!text || this.isSystemEchoPhrase(text)) return;
        if (this.isSpeakerAudioMuted && !forcePlay) return;

        const targetLang = this.listeningLang || "fr-FR";
        const estDuration = Math.max(2200, String(text).length * 75);
        this.notifyTTSState(true, estDuration);

        if (this.ttsUrl) {
            try {
                if (this.currentAudioEl) {
                    try { this.currentAudioEl.pause(); } catch (_) {}
                    this.currentAudioEl = null;
                }
                const audioUrl = `${this.ttsUrl}?text=${encodeURIComponent(text)}&lang=${encodeURIComponent(targetLang)}`;
                const audio = new Audio(audioUrl);
                this.currentAudioEl = audio;
                audio.onended = () => {
                    this.currentAudioEl = null;
                    this.notifyTTSState(false);
                };
                audio.onerror = () => {
                    this.currentAudioEl = null;
                    this.speakWithBrowserSynthesis(text, targetLang);
                };
                const playPromise = audio.play();
                if (playPromise && typeof playPromise.catch === "function") {
                    playPromise.catch(() => {
                        this.currentAudioEl = null;
                        this.speakWithBrowserSynthesis(text, targetLang);
                    });
                }
                return;
            } catch (_) {
                // Fall back to browser speech synthesis below
            }
        }
        this.speakWithBrowserSynthesis(text, targetLang);
    }

    speakWithBrowserSynthesis(text, targetLang) {
        if (!("speechSynthesis" in window) || !text || this.isSystemEchoPhrase(text)) {
            this.notifyTTSState(false);
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
            utterance.onend = () => {
                this.notifyTTSState(false);
            };
            utterance.onerror = () => {
                this.notifyTTSState(false);
            };
            window.speechSynthesis.speak(utterance);
        } catch (err) {
            this.notifyTTSState(false);
        }
    }

    async postTranscriptSegment(originalText, translatedText, targetShort, allTranslations = null) {
        if (!this.transcriptUrl || !originalText || this.isSystemEchoPhrase(originalText)) return null;
        const normText = originalText.trim().toLowerCase();
        if (this.lastSubmittedText === normText && this.lastSubmittedAt && Date.now() - this.lastSubmittedAt < 3500) {
            return null;
        }
        this.lastSubmittedText = normText;
        this.lastSubmittedAt = Date.now();
        try {
            const sourceShort = this.getShortLang(this.speakingLang);
            const translations = allTranslations ? { ...allTranslations } : {};
            if (
                targetShort &&
                translatedText &&
                !this.isSystemEchoPhrase(translatedText) &&
                (targetShort === sourceShort || translatedText.trim().toLowerCase() !== originalText.trim().toLowerCase())
            ) {
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
                    this.hasLiveSegments = true;
                    const shortListen = this.getShortLang(this.listeningLang);
                    const tText = (data.segment.translations || {})[shortListen] || data.segment.original_text;
                    const isNewSeq = (data.segment.sequence_number || 0) > this.lastSeenSequence;
                    this.lastSeenSequence = Math.max(this.lastSeenSequence, data.segment.sequence_number || 0);
                    this.triggerSpeakingPulse(data.segment.speaker_name, 2600);
                    this.renderLiveCaption(data.segment.speaker_name, data.segment.original_text, tText, true);
                    // Only auto-speak your own statement if you are solo-testing in a 1-person room with different Speak/Hear languages
                    if (isNewSeq && this.participantCount <= 1 && shortListen !== sourceShort) {
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
        }, 700);
    }

    async fetchLatestTranscript(speakNewSegments = true) {
        if (!this.transcriptUrl) return;
        try {
            const shortListen = this.getShortLang(this.listeningLang);
            const resp = await fetch(`${this.transcriptUrl}?lang=${encodeURIComponent(shortListen)}`, {
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
                if (
                    data.my_participant.is_muted &&
                    !this.isAudioMuted &&
                    Date.now() - (this.lastUnmuteAt || 0) > 2200
                ) {
                    await this.toggleMicrophone(true);
                    this.setMicStatus("Your microphone was muted by the meeting host.");
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
                this.renderParticipantsList(data.participants);
            }

            const segments = data.segments || [];
            if (segments.length > 0) {
                this.hasLiveSegments = true;
                this.renderTranscriptFeed(segments);
                const latest = segments[segments.length - 1];
                const isNew = latest.sequence_number > this.lastSeenSequence;
                const translated = (latest.translations || {})[shortListen] || latest.translated_text || latest.original_text;
                this.lastTranslatedText = translated;
                this.renderLiveCaption(latest.speaker_name, latest.original_text, translated, true);

                if (isNew) {
                    const prevSeq = this.lastSeenSequence;
                    this.lastSeenSequence = latest.sequence_number;
                    if (speakNewSegments && prevSeq >= 0) {
                        this.triggerSpeakingPulse(latest.speaker_name, 3200);
                        const isOtherSpeaker = latest.speaker_name !== this.userDisplayName;
                        const isDifferentLang = this.getShortLang(this.listeningLang) !== this.getShortLang(latest.original_language);
                        // Always play translated speech when another participant speaks, or when solo-testing with different Speak/Hear languages
                        if (isOtherSpeaker || (this.participantCount <= 1 && isDifferentLang)) {
                            this.speakTranslation(translated, this.azureData);
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
