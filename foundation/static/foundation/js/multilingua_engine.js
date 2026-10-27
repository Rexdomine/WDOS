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
        this.canShareScreen = Boolean(config.canShareScreen ?? config.isHost);
        this.allowParticipantScreenShare = Boolean(config.allowParticipantScreenShare);
        this.activeScreensharePresenter = config.activeScreensharePresenter || "";
        this.isScreenSharing = false;
        this.localScreenStream = null;
        this.activeScreenTrack = null;
        this.chatUrl = config.chatUrl || `/api/rooms/${this.roomCode}/chat/`;
        this.seenChatIds = new Set();
        this.unreadChatCount = 0;

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
        this.remoteCameraTracks = new Map();
        this.localCameraTrack = null;
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

        // Multi-Participant Video Grid & Delta Reconciliation State
        this.stageLayout = "grid"; // "grid" | "speaker"
        this.pinnedParticipantId = null;
        this.gridPage = 0;
        this.gridPageSize = 12;
        this.cachedParticipants = [];
        this.cachedSegments = [];
        this.speakingParticipantIds = new Set();
        this.lastStateVersion = "";
        this.unchangedPollStreak = 0;

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

    initPrejoinStudio() {
        const camBtn = document.getElementById("btn-toggle-cam");
        const micBtn = document.getElementById("btn-toggle-mic");
        const previewVideo = document.getElementById("prejoin-preview");
        const avatarBox = document.getElementById("stage-avatar-container");
        const micMeter = document.getElementById("prejoin-mic-meter");
        const micLabel = document.getElementById("prejoin-mic-label");
        const camBadge = document.getElementById("prejoin-cam-badge");
        const prejoinForm = document.getElementById("room-01-form");

        let prejoinVideoStream = null;
        let prejoinAudioStream = null;
        let prejoinAudioCtx = null;
        let prejoinAnalyser = null;
        let prejoinAnimFrame = null;

        const stopAudioTest = () => {
            if (prejoinAnimFrame) cancelAnimationFrame(prejoinAnimFrame);
            prejoinAnimFrame = null;
            if (prejoinAudioStream) {
                prejoinAudioStream.getTracks().forEach((t) => t.stop());
                prejoinAudioStream = null;
            }
            if (prejoinAudioCtx) {
                try { prejoinAudioCtx.close(); } catch (_) {}
                prejoinAudioCtx = null;
            }
            if (micMeter) micMeter.style.display = "none";
            if (micBtn) {
                micBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> <span>Test Mic</span>`;
                micBtn.style.background = "";
                micBtn.style.borderColor = "";
                micBtn.style.color = "";
            }
        };

        const stopVideoTest = () => {
            if (prejoinVideoStream) {
                prejoinVideoStream.getTracks().forEach((t) => t.stop());
                prejoinVideoStream = null;
            }
            if (previewVideo) {
                previewVideo.srcObject = null;
                previewVideo.style.display = "none";
            }
            if (avatarBox) avatarBox.style.display = "flex";
            if (camBadge) {
                camBadge.textContent = "📷 Camera Off";
                camBadge.style.background = "rgba(0,0,0,0.5)";
                camBadge.style.color = "#D8CBD9";
            }
            if (camBtn) {
                camBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> <span>Turn Camera On</span>`;
                camBtn.style.background = "";
                camBtn.style.borderColor = "";
                camBtn.style.color = "";
            }
        };

        // Camera Toggle
        if (camBtn) {
            camBtn.addEventListener("click", async (e) => {
                e.preventDefault();
                if (prejoinVideoStream) {
                    stopVideoTest();
                } else {
                    try {
                        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                            alert("Camera access is not supported by your browser.");
                            return;
                        }
                        camBtn.textContent = "Starting Camera...";
                        prejoinVideoStream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
                        if (previewVideo) {
                            previewVideo.srcObject = prejoinVideoStream;
                            previewVideo.style.display = "block";
                            previewVideo.play().catch(() => {});
                        }
                        if (avatarBox) avatarBox.style.display = "none";
                        if (camBadge) {
                            camBadge.textContent = "🟢 Camera Active";
                            camBadge.style.background = "rgba(22,163,74,0.3)";
                            camBadge.style.color = "#86EFAC";
                        }
                        camBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> <span>Turn Camera Off</span>`;
                        camBtn.style.background = "#1F2937";
                        camBtn.style.borderColor = "#4B5563";
                        camBtn.style.color = "#FFFFFF";
                    } catch (err) {
                        console.warn("Prejoin camera access error:", err);
                        stopVideoTest();
                        alert("Camera unavailable or permission denied. You can still join the room with audio.");
                    }
                }
            });
        }

        // Mic Test Toggle
        if (micBtn) {
            micBtn.addEventListener("click", async (e) => {
                e.preventDefault();
                this.unlockAudioPlayback();
                if (prejoinAudioStream) {
                    stopAudioTest();
                } else {
                    try {
                        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                            alert("Microphone access is not supported by your browser.");
                            return;
                        }
                        micBtn.textContent = "Connecting Mic...";
                        prejoinAudioStream = await navigator.mediaDevices.getUserMedia({
                            audio: { echoCancellation: true, noiseSuppression: true },
                            video: false
                        });
                        const AudioCtx = window.AudioContext || window.webkitAudioContext;
                        if (AudioCtx) {
                            prejoinAudioCtx = new AudioCtx();
                            if (prejoinAudioCtx.state === "suspended") {
                                await prejoinAudioCtx.resume();
                            }
                            const source = prejoinAudioCtx.createMediaStreamSource(prejoinAudioStream);
                            prejoinAnalyser = prejoinAudioCtx.createAnalyser();
                            prejoinAnalyser.fftSize = 128;
                            source.connect(prejoinAnalyser);

                            const bars = document.querySelectorAll(".prejoin-eq-bar");
                            const dataArray = new Uint8Array(prejoinAnalyser.frequencyBinCount);

                            if (micMeter) micMeter.style.display = "inline-flex";
                            if (micLabel) micLabel.textContent = "Testing mic... Speak now";

                            const drawMeter = () => {
                                if (!prejoinAudioStream || !prejoinAnalyser) return;
                                prejoinAnalyser.getByteFrequencyData(dataArray);
                                let sum = 0;
                                for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
                                const avg = sum / dataArray.length;

                                bars.forEach((b, idx) => {
                                    const val = dataArray[idx * 3] || avg;
                                    const height = Math.max(4, Math.min(22, Math.round((val / 255) * 22)));
                                    b.style.height = `${height}px`;
                                    if (avg > 14) {
                                        b.style.background = "#22C55E";
                                    } else {
                                        b.style.background = "#4ADE80";
                                    }
                                });

                                if (avg > 16 && micLabel) {
                                    micLabel.textContent = "✅ Mic is working! Audio detected.";
                                    micLabel.style.color = "#86EFAC";
                                }
                                prejoinAnimFrame = requestAnimationFrame(drawMeter);
                            };
                            drawMeter();
                        }
                        micBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg> <span>Stop Mic Test</span>`;
                        micBtn.style.background = "#15803D";
                        micBtn.style.borderColor = "#22C55E";
                        micBtn.style.color = "#FFFFFF";
                    } catch (err) {
                        console.warn("Prejoin mic access error:", err);
                        stopAudioTest();
                        alert("Microphone unavailable or permission denied. Check your browser permissions.");
                    }
                }
            });
        }

        // Clean up test media when submitting the form to enter the meeting
        if (prejoinForm) {
            prejoinForm.addEventListener("submit", () => {
                stopVideoTest();
                stopAudioTest();
            });
        }
        window.addEventListener("beforeunload", () => {
            stopVideoTest();
            stopAudioTest();
        });
    }

    bindUIControls() {
        if (document.getElementById("prejoin-screen")) {
            this.initPrejoinStudio();
            return;
        }
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

        const screenShareBtns = document.querySelectorAll("#btn-toggle-screenshare");
        screenShareBtns.forEach((btn) => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                await this.toggleScreenShare();
            });
        });
        this.updateScreenShareButtonVisibility();

        const stopOverlayBtn = document.getElementById("btn-stop-screenshare-overlay");
        if (stopOverlayBtn) {
            stopOverlayBtn.addEventListener("click", async (e) => {
                e.preventDefault();
                await this.stopScreenShare();
            });
        }

        // Layout switcher & Fullscreen & Grid Pagination controls
        const gridLayoutBtn = document.getElementById("btn-layout-grid");
        const speakerLayoutBtn = document.getElementById("btn-layout-speaker");
        if (gridLayoutBtn) {
            gridLayoutBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.setStageLayout("grid");
            });
        }
        if (speakerLayoutBtn) {
            speakerLayoutBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.setStageLayout("speaker");
            });
        }
        const fullscreenBtn = document.getElementById("btn-stage-fullscreen");
        if (fullscreenBtn) {
            fullscreenBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.toggleStageFullscreen();
            });
        }
        const gridPrevBtn = document.getElementById("btn-grid-prev");
        const gridNextBtn = document.getElementById("btn-grid-next");
        if (gridPrevBtn) {
            gridPrevBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.changeGridPage(-1);
            });
        }
        if (gridNextBtn) {
            gridNextBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.changeGridPage(1);
            });
        }

        // Live Emoji Reactions via LiveKit WebRTC DataChannel
        document.querySelectorAll(".zm-reaction-btn").forEach((btn) => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                const emoji = btn.getAttribute("data-reaction");
                if (emoji) {
                    this.sendReaction(emoji);
                }
            });
        });

        // Hardware Audio/Video Device Selectors
        this.initHardwareDeviceSelectors();

        window.addEventListener("pagehide", () => {
            if (this.myParticipantId && this.switchLangUrl) {
                const data = new URLSearchParams();
                data.append("action", "leave_room");
                data.append("participant_id", this.myParticipantId);
                data.append("is_beacon", "1");
                data.append("csrfmiddlewaretoken", this.getCsrfToken());
                if (navigator.sendBeacon) {
                    navigator.sendBeacon(this.switchLangUrl, data);
                }
            }
        });

        document.addEventListener("visibilitychange", () => {
            if (!document.hidden && this.transcriptUrl) {
                this.fetchLatestTranscript(false);
            }
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
                    return;
                }
                const textToSpeak = this.lastTranslatedText || document.getElementById("caption-translated-text")?.textContent || document.getElementById("caption-text")?.textContent;
                if (textToSpeak) {
                    this.speakTranslation(textToSpeak.trim(), this.azureData, true);
                }
            });
        }

        const recBtn = document.getElementById("btn-toggle-cloud-recording");
        if (recBtn) {
            recBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.toggleCloudRecording();
            });
        }

        const webModeBtn = document.getElementById("btn-toggle-webinar-mode");
        if (webModeBtn) {
            webModeBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.toggleWebinarMode();
            });
        }

        const bgBlurBtn = document.getElementById("btn-toggle-bg-blur");
        if (bgBlurBtn) {
            bgBlurBtn.addEventListener("click", (e) => {
                e.preventDefault();
                this.toggleBackgroundBlur();
            });
        }

        document.addEventListener("click", async (e) => {
            const voteBtn = e.target.closest(".js-vote-poll-btn");
            if (voteBtn && this.switchLangUrl) {
                const pollId = voteBtn.getAttribute("data-poll-id");
                const optIdx = voteBtn.getAttribute("data-opt-idx");
                if (pollId && optIdx !== null) {
                    const formData = new URLSearchParams();
                    formData.append("action", "vote_poll");
                    formData.append("poll_id", pollId);
                    formData.append("option_index", optIdx);
                    try {
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
                            if (data.poll) {
                                this.cachedPolls = this.cachedPolls || [];
                                const idx = this.cachedPolls.findIndex((p) => p.id === data.poll.id);
                                if (idx >= 0) this.cachedPolls[idx] = data.poll;
                                else this.cachedPolls.push(data.poll);
                                this.renderPolls(this.cachedPolls);
                            }
                        }
                    } catch (_) {}
                }
            }
        });

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

        const chatForm = document.getElementById("room-chat-form");
        const chatInput = document.getElementById("room-chat-input");
        if (chatForm) {
            chatForm.addEventListener("submit", async (e) => {
                e.preventDefault();
                await this.submitChatMessage(chatForm);
            });
        }
        if (chatInput) {
            chatInput.addEventListener("keydown", async (e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (chatForm) await this.submitChatMessage(chatForm);
                }
            });
        }

        const existingMsgEls = document.querySelectorAll("#room-chat-feed .zm-chat-msg");
        existingMsgEls.forEach((el) => {
            const id = el.getAttribute("data-chat-id");
            if (id) {
                this.seenChatIds.add(String(id));
            }
        });

        let alreadyRead = false;
        try {
            if (this.roomCode && sessionStorage.getItem(`wdos_chat_read_${this.roomCode}`) === "1") {
                alreadyRead = true;
            }
        } catch (_) {}

        if (this.isChatTabActive() || alreadyRead) {
            this.clearUnreadChatCount();
        } else {
            const dockBadge = document.getElementById("dock-chat-badge");
            if (dockBadge && dockBadge.style.display !== "none") {
                this.unreadChatCount = parseInt(dockBadge.textContent, 10) || 0;
            } else {
                this.unreadChatCount = 0;
            }
        }

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
            const pinBtn = e.target && e.target.closest ? e.target.closest(".js-pin-tile-btn") : null;
            if (pinBtn) {
                e.preventDefault();
                const pid = pinBtn.getAttribute("data-participant-id");
                if (pid) this.togglePinParticipant(pid);
                return;
            }
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
                if (data && typeof data.allow_participant_screen_share === "boolean") {
                    this.allowParticipantScreenShare = data.allow_participant_screen_share;
                    const policyBtn = document.getElementById("btn-toggle-screenshare-policy");
                    const policyInput = document.getElementById("input-screenshare-policy-action");
                    const policyLabel = document.getElementById("screenshare-policy-btn-label");
                    if (policyLabel) {
                        policyLabel.textContent = data.allow_participant_screen_share ? "Screen Share: All Allowed" : "Screen Share: Host Only";
                    }
                    if (policyBtn) {
                        policyBtn.style.background = data.allow_participant_screen_share ? "#DCFCE7" : "#F3F4F6";
                        policyBtn.style.color = data.allow_participant_screen_share ? "#166534" : "#4B5563";
                        policyBtn.style.borderColor = data.allow_participant_screen_share ? "#86EFAC" : "#E5E7EB";
                    }
                    if (policyInput) {
                        policyInput.value = data.allow_participant_screen_share ? "host_only" : "all_participants";
                    }
                }
                if (data && Array.isArray(data.waiting_participants)) {
                    this.renderWaitingRoomQueue(data.waiting_participants, true);
                }
                if (data && Array.isArray(data.participants)) {
                    this.participantCount = data.participants.length;
                    this.cachedParticipants = data.participants;
                    this.renderParticipantsList(data.participants, true);
                    this.renderVideoGrid(data.participants);
                }
                this.lastStateVersion = "";
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

            const lkConnected = await this.initLiveKitMedia(data.livekit);
            await this.initZoomMedia(data.zoom);
            this.startTokenRefreshTimer();
            if (lkConnected) {
                this.lkReconnectAttempt = 0;
                if (this.lkReconnectTimer) {
                    clearTimeout(this.lkReconnectTimer);
                    this.lkReconnectTimer = null;
                }
                this.updateDiagnosticsUI("Connected", 28);
                this.setMicStatus(`Connected as ${this.userDisplayName} · Speaking ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing ${this.langNames[this.listeningLang] || this.listeningLang}`);
            } else if (data.livekit && data.livekit.enabled) {
                this.updateConnectionQualityPill("poor");
                const qText = document.getElementById("webrtc-quality-text");
                if (qText) qText.textContent = "LiveKit SFU Reconnecting";
                this.setMicStatus("LiveKit WebRTC SFU connection unavailable (check LiveKit Cloud plan quota or network) — retrying automatically...");
                this.scheduleLiveKitReconnect();
            } else {
                this.updateDiagnosticsUI("Connected", 28);
                this.setMicStatus(`Connected as ${this.userDisplayName} · Speaking ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing ${this.langNames[this.listeningLang] || this.listeningLang}`);
            }
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
                videoCaptureDefaults: {
                    resolution: { width: 1280, height: 720, frameRate: 30 }
                },
                publishDefaults: {
                    simulcast: true
                },
                audioCaptureDefaults: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });
            this.livekitRoom = room;

            const getParticipantBaseId = (participant) => {
                if (!participant) return "";
                if (participant.metadata) {
                    try {
                        const parsed = JSON.parse(participant.metadata);
                        if (parsed && parsed.participant_id) {
                            return String(parsed.participant_id);
                        }
                    } catch (_) {}
                }
                const rawIdentity = String(participant.identity || "");
                return rawIdentity.split("__")[0];
            };

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

            const isScreenShareTrack = (track, publication) => {
                const screenSrc = (LK.Track && LK.Track.Source) ? LK.Track.Source.ScreenShare : "screen_share";
                return Boolean(
                    (publication && (publication.source === "screen_share" || publication.source === screenSrc || (publication.trackName && publication.trackName.includes("screen")))) ||
                    (track && (track.source === "screen_share" || track.source === screenSrc))
                );
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

            const attachVideo = (track, participant, publication = null) => {
                if (!track || track.kind !== "video") return;
                if (isScreenShareTrack(track, publication)) {
                    this.attachRemoteScreenTrack(track, participant);
                    return;
                }
                const baseId = getParticipantBaseId(participant) || (participant && participant.identity) || "remote";
                this.remoteCameraTracks.set(String(baseId), { track, publication, participant });
                this.attachCameraTrackToTile(String(baseId), track, false, participant);
                this.updateStageViewMode();
            };

            const detachVideo = (track, participant, publication = null) => {
                if (isScreenShareTrack(track, publication)) {
                    this.detachScreenTrack();
                    return;
                }
                const baseId = getParticipantBaseId(participant) || (participant && participant.identity) || "remote";
                this.remoteCameraTracks.delete(String(baseId));
                this.detachCameraTrackFromTile(String(baseId));
                this.updateStageViewMode();
            };

            if (LK.RoomEvent.ParticipantConnected) {
                room.on(LK.RoomEvent.ParticipantConnected, (participant) => {
                    if (isBotParticipant(participant)) {
                        this.serverBotConnected = true;
                        this.stopBrowserSpeechRecognizers();
                        this.publishLangChangeToBot();
                    } else {
                        syncParticipantMetadata(participant);
                        this.lastStateVersion = "";
                        this.fetchLatestTranscript(false);
                    }
                    this.updateRemoteWebRTCAudioVolumes();
                });
            }

            if (LK.RoomEvent.ParticipantDisconnected) {
                room.on(LK.RoomEvent.ParticipantDisconnected, (participant) => {
                    if (isBotParticipant(participant)) {
                        this.botLanguageTracks.clear();
                        this.botActiveSpeakerByLang.clear();
                    } else {
                        const baseId = getParticipantBaseId(participant);
                        if (baseId) {
                            this.remoteCameraTracks.delete(String(baseId));
                            this.detachCameraTrackFromTile(String(baseId));
                        }
                        this.lastStateVersion = "";
                        this.fetchLatestTranscript(false);
                    }
                    checkBotPresence();
                    this.updateRemoteWebRTCAudioVolumes();
                });
            }

            room.on(LK.RoomEvent.TrackSubscribed, (track, publication, participant) => {
                if (track.kind === "audio") {
                    attachAudio(track, participant, publication);
                } else if (track.kind === "video") {
                    attachVideo(track, participant, publication);
                }
            });

            if (LK.RoomEvent.TrackMuted) {
                room.on(LK.RoomEvent.TrackMuted, (publication, participant) => {
                    if (isScreenShareTrack(null, publication)) {
                        this.detachScreenTrack();
                    } else if (publication && publication.kind === "video") {
                        const baseId = getParticipantBaseId(participant);
                        if (baseId) this.detachCameraTrackFromTile(String(baseId));
                    }
                });
            }

            room.on(LK.RoomEvent.TrackUnmuted, (publication, participant) => {
                if (publication && publication.track) {
                    if (publication.track.kind === "audio") {
                        attachAudio(publication.track, participant, publication);
                    } else if (publication.track.kind === "video") {
                        attachVideo(publication.track, participant, publication);
                    }
                }
            });

            if (LK.RoomEvent.ConnectionQualityChanged) {
                room.on(LK.RoomEvent.ConnectionQualityChanged, (quality, participant) => {
                    if (participant && room.localParticipant && participant.identity === room.localParticipant.identity) {
                        this.updateConnectionQualityPill(quality);
                    }
                });
            }

            if (LK.RoomEvent.DataReceived) {
                room.on(LK.RoomEvent.DataReceived, (payload, participant, kind, topic) => {
                    try {
                        const rawStr = new TextDecoder().decode(payload);
                        const msg = JSON.parse(rawStr);
                        if (!msg || typeof msg !== "object") return;

                        // 1. Live Chat Message (`wdos_chat`)
                        if (topic === "wdos_chat" || (msg.type === "chat_message" && msg.message)) {
                            if (msg.message) {
                                this.appendChatMessage(msg.message, false);
                            }
                            return;
                        }

                        // 2. Live Floating Emoji Reaction (`wdos_reaction`)
                        if (topic === "wdos_reaction" || msg.type === "reaction") {
                            if (msg.emoji) {
                                this.renderFloatingReaction(msg.emoji, msg.sender_name || (participant && participant.name) || "Participant");
                            }
                            return;
                        }

                        // 3. Real-Time Control & Governance Events (`wdos_control`)
                        if (
                            topic === "wdos_control" ||
                            msg.type === "participant_joined" ||
                            msg.type === "participant_updated" ||
                            msg.type === "host_admitted" ||
                            msg.type === "host_action" ||
                            msg.type === "policy_updated" ||
                            msg.type === "screenshare_state" ||
                            msg.type === "meeting_ended"
                        ) {
                            this.handleRealtimeControlPacket(msg);
                            return;
                        }

                        // 4. Server Translation Bot & Live Captions (`wdos_caption`)
                        if (isBotParticipant(participant) || msg.type === "bot_tts_state") {
                            this.serverBotConnected = true;
                            this.stopBrowserSpeechRecognizers();
                        }

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
                            this.appendRealtimeSegmentToFeed(seg);

                            if (seg.speaker_name && seg.original_language) {
                                this.participantLanguagesByName.set(String(seg.speaker_name), seg.original_language);
                                this.updateRemoteWebRTCAudioVolumes();
                            }

                            if (this.hasSubscribedBotTrack(shortListen)) {
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

            if (LK.RoomEvent.Reconnecting) {
                room.on(LK.RoomEvent.Reconnecting, () => {
                    this.updateConnectionQualityPill("poor");
                    this.setMicStatus("Reconnecting to LiveKit WebRTC SFU...");
                });
            }

            if (LK.RoomEvent.Reconnected) {
                room.on(LK.RoomEvent.Reconnected, async () => {
                    if (!this.isAudioMuted && room.localParticipant) {
                        try {
                            await room.localParticipant.setMicrophoneEnabled(true);
                        } catch (_) {}
                    }
                    this.updateConnectionQualityPill("excellent");
                    this.updateRemoteWebRTCAudioVolumes();
                    this.lastStateVersion = "";
                    this.fetchLatestTranscript(false);
                });
            }

            if (LK.RoomEvent.ParticipantPermissionsChanged) {
                room.on(LK.RoomEvent.ParticipantPermissionsChanged, (prevPermissions, participant) => {
                    if (participant && room.localParticipant && participant.identity === room.localParticipant.identity) {
                        const canPub = Boolean(participant.permissions && participant.permissions.canPublish);
                        if (canPub) {
                            this.setMicStatus("Floor granted — you can now unmute and share video.");
                        }
                    }
                });
            }

            room.on(LK.RoomEvent.TrackUnsubscribed, (track, publication, participant) => {
                if (!track) return;
                if (track.kind === "video") {
                    detachVideo(track, participant, publication);
                    try { track.detach(); } catch (_) {}
                    return;
                }
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
            });

            room.on(LK.RoomEvent.ActiveSpeakersChanged, (speakers) => {
                this.speakingParticipantIds.clear();
                if (Array.isArray(speakers)) {
                    speakers.forEach((s) => {
                        if (s && !isBotParticipant(s)) {
                            const bid = getParticipantBaseId(s);
                            if (bid) this.speakingParticipantIds.add(String(bid));
                        }
                    });
                }
                this.highlightSpeakingTiles();
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
            this.updateConnectionQualityPill("excellent");
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
                                else if (pub.track.kind === "video") attachVideo(pub.track, participant, pub);
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

    scheduleLiveKitReconnect() {
        if (this.lkReconnectTimer) clearTimeout(this.lkReconnectTimer);
        if (!this.livekitData || !this.livekitData.enabled) return;
        this.lkReconnectAttempt = (this.lkReconnectAttempt || 0) + 1;
        const delayMs = Math.min(60000, 10000 * Math.pow(2, this.lkReconnectAttempt - 1));
        this.lkReconnectTimer = setTimeout(async () => {
            if (this.livekitRoom && this.livekitRoom.state === "connected") return;
            const ok = await this.initLiveKitMedia(this.livekitData);
            if (ok) {
                this.lkReconnectAttempt = 0;
                this.updateConnectionQualityPill("excellent");
                this.setMicStatus(`Connected as ${this.userDisplayName} · Speaking ${this.langNames[this.speakingLang] || this.speakingLang} · Hearing ${this.langNames[this.listeningLang] || this.listeningLang}`);
            } else {
                this.scheduleLiveKitReconnect();
            }
        }, delayMs);
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

    stopLiveVoiceRecorder() {
        // Legacy HTTP audio chunk recorder removed: all voice media streams over LiveKit WebRTC SFU tracks.
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
            clearTimeout(this.pollTimer);
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
        this.stopScreenShare();
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
        if (this.remoteCameraTracks) {
            this.remoteCameraTracks.clear();
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
                let lkCamTrack = null;
                if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
                    try {
                        const pub = await this.livekitRoom.localParticipant.setCameraEnabled(true);
                        if (pub && pub.track) {
                            lkCamTrack = pub.track;
                        } else if (this.livekitRoom.localParticipant.videoTrackPublications) {
                            this.livekitRoom.localParticipant.videoTrackPublications.forEach((p) => {
                                if (!lkCamTrack && p && p.track && p.source !== "screen_share") {
                                    lkCamTrack = p.track;
                                }
                            });
                        }
                    } catch (_) {}
                }

                if (lkCamTrack) {
                    this.localCameraTrack = lkCamTrack;
                    if (this.isBackgroundBlurEnabled) {
                        await this.applyCameraBlurProcessor(true);
                    }
                    if (stageVideo && typeof lkCamTrack.attach === "function") {
                        lkCamTrack.attach(stageVideo);
                        stageVideo.muted = true;
                        if (this.stageLayout === "speaker") {
                            stageVideo.style.display = "block";
                        }
                    }
                    if (this.myParticipantId) {
                        this.attachCameraTrackToTile(String(this.myParticipantId), lkCamTrack, true, this.livekitRoom.localParticipant);
                    }
                } else {
                    this.localVideoStream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
                    if (stageVideo) {
                        stageVideo.srcObject = this.localVideoStream;
                        stageVideo.muted = true;
                        if (this.stageLayout === "speaker" || !document.getElementById("live-video-grid")) {
                            stageVideo.style.display = "block";
                        }
                        try { await stageVideo.play(); } catch (_) {}
                    }
                    if (this.myParticipantId) {
                        this.attachCameraTrackToTile(String(this.myParticipantId), this.localVideoStream, true, null);
                    }
                }
                if (speakerAvatarBox && this.stageLayout === "speaker") {
                    speakerAvatarBox.style.display = "none";
                }
                if (camNotice) {
                    camNotice.style.display = "none";
                }
                this.isVideoOff = false;
                this.updateStageViewMode();
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
            if (this.localCameraTrack && typeof this.localCameraTrack.detach === "function") {
                try { this.localCameraTrack.detach(); } catch (_) {}
            }
            this.localCameraTrack = null;
            if (this.localVideoStream) {
                this.localVideoStream.getTracks().forEach((t) => t.stop());
                this.localVideoStream = null;
            }
            if (this.myParticipantId) {
                this.detachCameraTrackFromTile(String(this.myParticipantId));
            }
            if (stageVideo) {
                stageVideo.srcObject = null;
                stageVideo.style.display = "none";
            }
            if (camNotice) {
                camNotice.style.display = "none";
            }
            this.isVideoOff = true;
            this.updateStageViewMode();
            camBtns.forEach((btn) => {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg> <span>Turn Camera On</span>`;
                btn.style.background = "";
                btn.style.borderColor = "";
                btn.style.color = "";
            });
            this.setMicStatus("Camera turned off.");
        }
    }

    isUserPermittedToShareScreen() {
        return Boolean(this.isHost || this.canShareScreen || this.allowParticipantScreenShare);
    }

    updateScreenShareButtonVisibility() {
        const canShare = this.isUserPermittedToShareScreen();
        const screenBtns = document.querySelectorAll("#btn-toggle-screenshare");
        screenBtns.forEach((btn) => {
            btn.style.display = canShare ? "inline-flex" : "none";
        });
        if (!canShare && this.isScreenSharing) {
            this.stopScreenShare();
            this.setMicStatus("Screen sharing permission was revoked by the host.");
        }
    }

    async toggleScreenShare() {
        if (this.isScreenSharing) {
            await this.stopScreenShare();
            return;
        }
        if (!this.isUserPermittedToShareScreen()) {
            this.setMicStatus("Screen sharing is restricted by the host. Only authorized presenters can share.");
            return;
        }
        await this.startScreenShare();
    }

    async startScreenShare() {
        const btns = document.querySelectorAll("#btn-toggle-screenshare");
        btns.forEach((btn) => {
            btn.innerHTML = `<span>Starting Share...</span>`;
        });

        try {
            let screenTrack = null;

            if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
                try {
                    const pub = await this.livekitRoom.localParticipant.setScreenShareEnabled(true, {
                        audio: true,
                        resolution: { width: 1920, height: 1080, frameRate: 15 },
                        contentHint: "detail"
                    });
                    if (pub && pub.track) {
                        screenTrack = pub.track;
                    }
                } catch (lkErr) {
                    console.warn("LiveKit screen share publication error:", lkErr);
                    if (lkErr && (lkErr.name === "NotAllowedError" || String(lkErr.message || "").includes("Permission denied"))) {
                        throw lkErr;
                    }
                }
            }

            if (!screenTrack) {
                if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
                    throw new Error("Screen sharing is not supported in this browser.");
                }
                const stream = await navigator.mediaDevices.getDisplayMedia({
                    video: { width: { ideal: 1920 }, height: { ideal: 1080 }, frameRate: { ideal: 15 }, cursor: "always" },
                    audio: true
                });
                this.localScreenStream = stream;
                const videoTrack = stream.getVideoTracks()[0];
                if (!videoTrack) throw new Error("No video track found in screen capture.");
                try { videoTrack.contentHint = "detail"; } catch (_) {}

                videoTrack.onended = () => {
                    this.stopScreenShare();
                };
                this.attachLocalScreenTrack(stream);
            } else {
                if (screenTrack.mediaStreamTrack) {
                    screenTrack.mediaStreamTrack.onended = () => {
                        this.stopScreenShare();
                    };
                }
                this.activeScreenTrack = screenTrack;
                this.attachLocalScreenTrack(screenTrack);
            }

            this.isScreenSharing = true;
            this.updateScreenShareButtons(true);
            await this.notifyScreenshareState(true, this.userDisplayName);
            this.setMicStatus("Presenting your screen to the meeting via WebRTC.");
        } catch (err) {
            this.isScreenSharing = false;
            this.updateScreenShareButtons(false);
            if (err.name === "NotAllowedError" || (err.message && err.message.includes("Permission denied"))) {
                this.setMicStatus("Screen sharing cancelled.");
            } else {
                this.setMicStatus(`Screen sharing error: ${err.message || "Could not share screen"}`);
            }
        }
    }

    attachLocalScreenTrack(trackOrStream) {
        const container = document.getElementById("stage-screenshare-container");
        const video = document.getElementById("live-screenshare-video");
        const img = document.getElementById("live-screenshare-img");
        const badge = document.getElementById("screenshare-presenter-name") || document.getElementById("stage-screenshare-badge");
        const stopOverlay = document.getElementById("btn-stop-screenshare-overlay");
        const avatarBox = document.getElementById("stage-avatar-container");
        const stageVideo = document.getElementById("live-stage-video");
        const videoGrid = document.getElementById("live-video-grid");

        if (container && video) {
            if (trackOrStream && typeof trackOrStream.attach === "function") {
                trackOrStream.attach(video);
            } else if (trackOrStream instanceof MediaStream) {
                video.srcObject = trackOrStream;
            }
            video.muted = true;
            video.style.display = "block";
            if (img) img.style.display = "none";
            try { video.play().catch(() => {}); } catch (_) {}
            container.style.display = "block";
            if (badge) badge.textContent = `Presenting: ${this.userDisplayName} (You)`;
            if (stopOverlay) stopOverlay.style.display = "inline-flex";
            if (avatarBox) avatarBox.style.display = "none";
            if (stageVideo) stageVideo.style.display = "none";
            if (videoGrid) videoGrid.style.display = "none";
        }
    }

    attachRemoteScreenTrack(track, participant) {
        const container = document.getElementById("stage-screenshare-container");
        const video = document.getElementById("live-screenshare-video");
        const img = document.getElementById("live-screenshare-img");
        const badge = document.getElementById("screenshare-presenter-name") || document.getElementById("stage-screenshare-badge");
        const stopOverlay = document.getElementById("btn-stop-screenshare-overlay");
        const avatarBox = document.getElementById("stage-avatar-container");
        const stageVideo = document.getElementById("live-stage-video");
        const videoGrid = document.getElementById("live-video-grid");

        const presenterName = (participant && (participant.name || participant.identity)) || this.activeScreensharePresenter || "Presenter";
        this.activeScreensharePresenter = presenterName;
        this.activeScreenTrack = track;

        if (container && video) {
            if (track && typeof track.attach === "function") {
                track.attach(video);
            }
            video.muted = false;
            video.style.display = "block";
            if (img) img.style.display = "none";
            try { video.play().catch(() => {}); } catch (_) {}
            container.style.display = "block";
            if (badge) badge.textContent = `Presenting: ${presenterName}`;
            if (stopOverlay) stopOverlay.style.display = "none";
            if (avatarBox) avatarBox.style.display = "none";
            if (stageVideo) stageVideo.style.display = "none";
            if (videoGrid) videoGrid.style.display = "none";
        }
    }

    detachScreenTrack() {
        const container = document.getElementById("stage-screenshare-container");
        const video = document.getElementById("live-screenshare-video");
        const img = document.getElementById("live-screenshare-img");
        const stopOverlay = document.getElementById("btn-stop-screenshare-overlay");

        if (video) {
            try {
                if (this.activeScreenTrack && typeof this.activeScreenTrack.detach === "function") {
                    this.activeScreenTrack.detach(video);
                }
            } catch (_) {}
            video.srcObject = null;
            video.style.display = "none";
        }
        if (img) {
            img.src = "";
            img.style.display = "none";
        }
        if (container) {
            container.style.display = "none";
        }
        if (stopOverlay) {
            stopOverlay.style.display = "none";
        }
        this.activeScreenTrack = null;
        this.activeScreensharePresenter = "";
        this.updateStageViewMode();
    }

    async stopScreenShare() {
        if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
            try {
                await this.livekitRoom.localParticipant.setScreenShareEnabled(false);
            } catch (_) {}
        }
        if (this.localScreenStream) {
            try {
                this.localScreenStream.getTracks().forEach((t) => t.stop());
            } catch (_) {}
            this.localScreenStream = null;
        }
        this.isScreenSharing = false;
        this.detachScreenTrack();
        this.updateScreenShareButtons(false);
        await this.notifyScreenshareState(false, "");
        this.setMicStatus("Screen sharing ended.");
    }

    updateScreenShareButtons(isActive) {
        const btns = document.querySelectorAll("#btn-toggle-screenshare");
        btns.forEach((btn) => {
            if (isActive) {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/><line x1="2" y1="2" x2="22" y2="22"/></svg> <span>Stop Sharing</span>`;
                btn.style.background = "#DC2626";
                btn.style.borderColor = "#F87171";
                btn.style.color = "#FFFFFF";
            } else {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg> <span>Share Screen</span>`;
                btn.style.background = "";
                btn.style.borderColor = "";
                btn.style.color = "";
            }
        });
    }

    async notifyScreenshareState(isSharing, presenterName) {
        if (!this.switchLangUrl) return;
        try {
            const formData = new URLSearchParams();
            formData.append("action", "set_screenshare_state");
            formData.append("is_sharing", isSharing ? "true" : "false");
            formData.append("presenter_name", presenterName || "");
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

    setStageLayout(mode) {
        this.stageLayout = mode === "speaker" ? "speaker" : "grid";
        const gridBtn = document.getElementById("btn-layout-grid");
        const speakerBtn = document.getElementById("btn-layout-speaker");
        if (gridBtn) gridBtn.classList.toggle("active", this.stageLayout === "grid");
        if (speakerBtn) speakerBtn.classList.toggle("active", this.stageLayout === "speaker");
        this.updateStageViewMode();
    }

    togglePinParticipant(participantId) {
        const pid = String(participantId || "");
        if (!pid) return;
        if (this.pinnedParticipantId === pid) {
            this.pinnedParticipantId = null;
        } else {
            this.pinnedParticipantId = pid;
        }
        if (this.cachedParticipants && this.cachedParticipants.length > 0) {
            this.renderVideoGrid(this.cachedParticipants);
        }
    }

    changeGridPage(delta) {
        const total = (this.cachedParticipants || []).length;
        const maxPage = Math.max(0, Math.ceil(total / this.gridPageSize) - 1);
        this.gridPage = Math.max(0, Math.min(maxPage, (this.gridPage || 0) + delta));
        if (this.cachedParticipants && this.cachedParticipants.length > 0) {
            this.renderVideoGrid(this.cachedParticipants);
        }
    }

    toggleStageFullscreen() {
        const stageEl = document.querySelector(".zm-stage-canvas");
        if (!stageEl) return;
        if (!document.fullscreenElement) {
            if (stageEl.requestFullscreen) {
                stageEl.requestFullscreen().catch(() => {});
            }
        } else if (document.exitFullscreen) {
            document.exitFullscreen().catch(() => {});
        }
    }

    updateStageViewMode() {
        const screenContainer = document.getElementById("stage-screenshare-container");
        if (screenContainer && screenContainer.style.display === "block") {
            return;
        }
        const videoGrid = document.getElementById("live-video-grid");
        const avatarBox = document.getElementById("stage-avatar-container");
        const stageVideo = document.getElementById("live-stage-video");
        const paginationBar = document.getElementById("video-grid-pagination");

        if (!videoGrid) return;

        if (this.stageLayout === "grid") {
            videoGrid.style.display = "grid";
            if (avatarBox) avatarBox.style.display = "none";
            if (stageVideo) stageVideo.style.display = "none";
        } else {
            // Speaker View: show single stage speaker or active camera
            videoGrid.style.display = "none";
            if (paginationBar) paginationBar.style.display = "none";
            let activeTrack = null;
            if (!this.isVideoOff && this.localCameraTrack) {
                activeTrack = this.localCameraTrack;
            } else if (this.remoteCameraTracks && this.remoteCameraTracks.size > 0) {
                const firstEntry = this.remoteCameraTracks.values().next().value;
                if (firstEntry && firstEntry.track) activeTrack = firstEntry.track;
            }
            if (activeTrack && stageVideo && typeof activeTrack.attach === "function") {
                activeTrack.attach(stageVideo);
                stageVideo.style.display = "block";
                if (avatarBox) avatarBox.style.display = "none";
            } else if (!this.isVideoOff && this.localVideoStream && stageVideo) {
                stageVideo.srcObject = this.localVideoStream;
                stageVideo.style.display = "block";
                if (avatarBox) avatarBox.style.display = "none";
            } else {
                if (stageVideo) stageVideo.style.display = "none";
                if (avatarBox) avatarBox.style.display = "flex";
            }
        }
    }

    renderVideoGrid(participants) {
        const gridEl = document.getElementById("live-video-grid");
        if (!gridEl || !Array.isArray(participants)) return;

        // Sort: pinned first, then active speakers, then Host/Co-Host, then others
        const sorted = participants.slice().sort((a, b) => {
            const aPin = String(a.id) === String(this.pinnedParticipantId) ? 1 : 0;
            const bPin = String(b.id) === String(this.pinnedParticipantId) ? 1 : 0;
            if (aPin !== bPin) return bPin - aPin;
            const aSpeak = this.speakingParticipantIds.has(String(a.id)) ? 1 : 0;
            const bSpeak = this.speakingParticipantIds.has(String(b.id)) ? 1 : 0;
            if (aSpeak !== bSpeak) return bSpeak - aSpeak;
            return 0;
        });

        const total = sorted.length;
        const totalPages = Math.max(1, Math.ceil(total / this.gridPageSize));
        if (this.gridPage >= totalPages) this.gridPage = totalPages - 1;
        const startIdx = this.gridPage * this.gridPageSize;
        const pageItems = sorted.slice(startIdx, startIdx + this.gridPageSize);

        // Update pagination bar for large meetings (13 to 1,000+ participants)
        const paginationEl = document.getElementById("video-grid-pagination");
        const pageLabelEl = document.getElementById("grid-page-label");
        if (paginationEl) {
            if (total > this.gridPageSize && this.stageLayout === "grid") {
                paginationEl.style.display = "flex";
                if (pageLabelEl) pageLabelEl.textContent = `Page ${this.gridPage + 1} of ${totalPages} (${total} participants)`;
            } else {
                paginationEl.style.display = "none";
            }
        }

        const countClass = `tiles-${Math.max(1, Math.min(12, pageItems.length))}`;
        gridEl.className = `zm-video-grid ${countClass}`;

        const keepIds = new Set(pageItems.map((p) => String(p.id)));
        Array.from(gridEl.querySelectorAll(".zm-video-tile")).forEach((tile) => {
            const tid = tile.getAttribute("data-participant-id");
            if (!keepIds.has(String(tid))) {
                tile.remove();
            }
        });

        pageItems.forEach((p) => {
            const pid = String(p.id);
            const isLocal = Boolean(this.myParticipantId && pid === String(this.myParticipantId));
            const parts = String(p.participant_name || "P").trim().split(/\s+/);
            const initials = parts.slice(0, 2).map((w) => w[0] || "").join("").toUpperCase() || "P";
            const isPinned = String(this.pinnedParticipantId) === pid;
            const isSpeaking = this.speakingParticipantIds.has(pid);

            let tile = gridEl.querySelector(`.zm-video-tile[data-participant-id="${this.escapeHtml(pid)}"]`);
            if (!tile) {
                tile = document.createElement("div");
                tile.className = "zm-video-tile";
                tile.setAttribute("data-participant-id", pid);
                tile.innerHTML = `
                    <video playsinline autoplay muted style="display:none;"></video>
                    <div class="zm-tile-avatar-wrap">
                        <div class="zm-tile-avatar">${this.escapeHtml(initials)}</div>
                    </div>
                    <button type="button" class="zm-tile-pin-btn js-pin-tile-btn" data-participant-id="${this.escapeHtml(pid)}" title="Pin Participant">📌</button>
                    <div class="zm-tile-footer">
                        <div class="zm-tile-name-wrap">
                            <span class="zm-tile-name"></span>
                            <span class="zm-tile-lang-pill"></span>
                        </div>
                        <span class="zm-tile-mic-state"></span>
                    </div>
                `;
                gridEl.appendChild(tile);
            }

            tile.classList.toggle("is-pinned", isPinned);
            tile.classList.toggle("is-speaking", isSpeaking);

            const avatarEl = tile.querySelector(".zm-tile-avatar");
            if (avatarEl) avatarEl.textContent = initials;

            const nameEl = tile.querySelector(".zm-tile-name");
            if (nameEl) {
                nameEl.textContent = `${p.participant_name || "Participant"}${isLocal ? " (You)" : ""}`;
            }

            const langPill = tile.querySelector(".zm-tile-lang-pill");
            if (langPill) {
                const shortSpk = this.getShortLang(p.speaking_language || "en-US").toUpperCase();
                const shortLst = this.getShortLang(p.listening_language || "fr-FR").toUpperCase();
                langPill.textContent = `${shortSpk}→${shortLst}`;
            }

            const micStateEl = tile.querySelector(".zm-tile-mic-state");
            if (micStateEl) {
                const muted = isLocal ? this.isAudioMuted : Boolean(p.is_muted);
                const hand = p.hand_raised ? "✋ " : "";
                micStateEl.innerHTML = `${hand}${muted ? '<span style="color:#FCA5A5;" title="Muted">🔇</span>' : '<span style="color:#4ADE80;" title="Mic Active">🎙️</span>'}`;
            }

            // Re-verify camera attachment if available
            if (isLocal && !this.isVideoOff && (this.localCameraTrack || this.localVideoStream)) {
                this.attachCameraTrackToTile(pid, this.localCameraTrack || this.localVideoStream, true, null);
            } else if (!isLocal && this.remoteCameraTracks.has(pid)) {
                const entry = this.remoteCameraTracks.get(pid);
                if (entry && entry.track) {
                    this.attachCameraTrackToTile(pid, entry.track, false, entry.participant);
                }
            }
        });

        this.updateStageViewMode();
    }

    attachCameraTrackToTile(participantId, trackOrStream, isLocal = false, participant = null) {
        const gridEl = document.getElementById("live-video-grid");
        if (!gridEl) return;
        let tile = gridEl.querySelector(`.zm-video-tile[data-participant-id="${this.escapeHtml(participantId)}"]`);
        if (!tile && participant) {
            // Create tile on the fly if roster delta hasn't arrived yet
            const pName = participant.name || participant.identity || "Participant";
            this.cachedParticipants = this.cachedParticipants || [];
            if (!this.cachedParticipants.some((p) => String(p.id) === String(participantId))) {
                this.cachedParticipants.push({
                    id: String(participantId),
                    participant_name: pName,
                    meeting_role: "Participant",
                    speaking_language: "en-US",
                    listening_language: "fr-FR",
                    is_muted: false
                });
                this.renderVideoGrid(this.cachedParticipants);
            }
            tile = gridEl.querySelector(`.zm-video-tile[data-participant-id="${this.escapeHtml(participantId)}"]`);
        }
        if (!tile) return;

        const videoEl = tile.querySelector("video");
        const avatarWrap = tile.querySelector(".zm-tile-avatar-wrap");
        if (!videoEl) return;

        if (trackOrStream && typeof trackOrStream.attach === "function") {
            trackOrStream.attach(videoEl);
        } else if (trackOrStream instanceof MediaStream) {
            videoEl.srcObject = trackOrStream;
        }
        videoEl.muted = true;
        videoEl.style.display = "block";
        if (isLocal) {
            videoEl.style.transform = "scaleX(-1)";
        } else {
            videoEl.style.transform = "none";
        }
        try { videoEl.play().catch(() => {}); } catch (_) {}
        if (avatarWrap) avatarWrap.style.display = "none";
    }

    detachCameraTrackFromTile(participantId) {
        const gridEl = document.getElementById("live-video-grid");
        if (!gridEl) return;
        const tile = gridEl.querySelector(`.zm-video-tile[data-participant-id="${this.escapeHtml(participantId)}"]`);
        if (!tile) return;
        const videoEl = tile.querySelector("video");
        const avatarWrap = tile.querySelector(".zm-tile-avatar-wrap");
        if (videoEl) {
            videoEl.srcObject = null;
            videoEl.style.display = "none";
        }
        if (avatarWrap) {
            avatarWrap.style.display = "flex";
        }
    }

    highlightSpeakingTiles() {
        const gridEl = document.getElementById("live-video-grid");
        if (!gridEl) return;
        gridEl.querySelectorAll(".zm-video-tile").forEach((tile) => {
            const pid = tile.getAttribute("data-participant-id");
            tile.classList.toggle("is-speaking", Boolean(pid && this.speakingParticipantIds.has(String(pid))));
        });
    }

    updateConnectionQualityPill(quality) {
        const pill = document.getElementById("webrtc-quality-pill");
        const label = document.getElementById("webrtc-quality-label");
        if (!pill || !label) return;
        const qStr = String(quality || "excellent").toLowerCase();
        const dot = pill.querySelector(".zm-quality-dot");
        if (qStr === "poor" || qStr === "lost") {
            label.textContent = "WebRTC SFU · Weak Signal";
            if (dot) dot.style.background = "#EF4444";
        } else if (qStr === "good") {
            label.textContent = "WebRTC SFU · Good";
            if (dot) dot.style.background = "#F59E0B";
        } else {
            label.textContent = "WebRTC SFU · HD";
            if (dot) dot.style.background = "#4ADE80";
        }
    }

    sendReaction(emoji) {
        if (!emoji) return;
        this.renderFloatingReaction(emoji, `${this.userDisplayName} (You)`);
        if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
            try {
                const payload = new TextEncoder().encode(
                    JSON.stringify({
                        type: "reaction",
                        emoji: emoji,
                        sender_name: this.userDisplayName,
                        participant_id: this.myParticipantId || ""
                    })
                );
                this.livekitRoom.localParticipant.publishData(payload, { reliable: false, topic: "wdos_reaction" }).catch(() => {});
            } catch (_) {}
        }
    }

    renderFloatingReaction(emoji, senderName = "") {
        const layer = document.getElementById("reaction-float-layer");
        if (!layer || !emoji) return;
        const item = document.createElement("div");
        item.className = "zm-floating-reaction";
        const offsetPx = Math.floor((Math.random() - 0.5) * 140);
        item.style.left = `calc(50% + ${offsetPx}px)`;
        item.innerHTML = `${this.escapeHtml(emoji)}${senderName ? `<span style="display:block;font-size:10px;color:#FFF;background:rgba(0,0,0,0.65);padding:1px 6px;border-radius:999px;font-weight:700;white-space:nowrap;">${this.escapeHtml(senderName)}</span>` : ""}`;
        layer.appendChild(item);
        setTimeout(() => {
            if (item.parentNode) item.parentNode.removeChild(item);
        }, 2300);
    }

    async initHardwareDeviceSelectors() {
        const micSelect = document.getElementById("select-mic-device");
        const camSelect = document.getElementById("select-cam-device");
        const spkSelect = document.getElementById("select-speaker-device");
        if (!micSelect && !camSelect && !spkSelect) return;
        if (!navigator.mediaDevices || typeof navigator.mediaDevices.enumerateDevices !== "function") return;

        const populateDevices = async () => {
            try {
                const devices = await navigator.mediaDevices.enumerateDevices();
                const inputsAudio = devices.filter((d) => d.kind === "audioinput");
                const inputsVideo = devices.filter((d) => d.kind === "videoinput");
                const outputsAudio = devices.filter((d) => d.kind === "audiooutput");

                if (micSelect && inputsAudio.length > 0) {
                    const prev = micSelect.value;
                    micSelect.innerHTML = `<option value="">Default Microphone</option>` + inputsAudio.map((d, i) =>
                        `<option value="${this.escapeHtml(d.deviceId)}">${this.escapeHtml(d.label || `Microphone ${i + 1}`)}</option>`
                    ).join("");
                    if (prev) micSelect.value = prev;
                }
                if (camSelect && inputsVideo.length > 0) {
                    const prev = camSelect.value;
                    camSelect.innerHTML = `<option value="">Default Camera</option>` + inputsVideo.map((d, i) =>
                        `<option value="${this.escapeHtml(d.deviceId)}">${this.escapeHtml(d.label || `Camera ${i + 1}`)}</option>`
                    ).join("");
                    if (prev) camSelect.value = prev;
                }
                if (spkSelect && outputsAudio.length > 0) {
                    const prev = spkSelect.value;
                    spkSelect.innerHTML = `<option value="">Default Speaker</option>` + outputsAudio.map((d, i) =>
                        `<option value="${this.escapeHtml(d.deviceId)}">${this.escapeHtml(d.label || `Speaker ${i + 1}`)}</option>`
                    ).join("");
                    if (prev) spkSelect.value = prev;
                }
            } catch (_) {}
        };

        await populateDevices();
        try {
            navigator.mediaDevices.addEventListener("devicechange", populateDevices);
        } catch (_) {}

        if (micSelect) {
            micSelect.addEventListener("change", async () => {
                if (this.livekitRoom && typeof this.livekitRoom.switchActiveDevice === "function" && micSelect.value) {
                    try { await this.livekitRoom.switchActiveDevice("audioinput", micSelect.value); } catch (_) {}
                }
            });
        }
        if (camSelect) {
            camSelect.addEventListener("change", async () => {
                if (this.livekitRoom && typeof this.livekitRoom.switchActiveDevice === "function" && camSelect.value) {
                    try { await this.livekitRoom.switchActiveDevice("videoinput", camSelect.value); } catch (_) {}
                }
            });
        }
        if (spkSelect) {
            spkSelect.addEventListener("change", async () => {
                if (this.livekitRoom && typeof this.livekitRoom.switchActiveDevice === "function" && spkSelect.value) {
                    try { await this.livekitRoom.switchActiveDevice("audiooutput", spkSelect.value); } catch (_) {}
                }
            });
        }
    }

    async handleRealtimeControlPacket(msg) {
        if (!msg || typeof msg !== "object") return;

        if (msg.type === "meeting_ended" || msg.type === "room_ended") {
            this.shutdownAllMedia();
            if (!document.getElementById("meeting-ended-screen")) {
                window.location.reload();
            }
            return;
        }

        if (msg.type === "recording_state" && msg.recording_state) {
            this.syncRecordingState(msg.recording_state);
        }

        if ((msg.type === "poll_created" || msg.type === "poll_updated" || msg.type === "poll_closed") && msg.poll) {
            this.cachedPolls = this.cachedPolls || [];
            const idx = this.cachedPolls.findIndex((p) => p.id === msg.poll.id);
            if (idx >= 0) {
                this.cachedPolls[idx] = msg.poll;
            } else {
                this.cachedPolls.push(msg.poll);
            }
            this.renderPolls(this.cachedPolls);
        }

        if (msg.type === "host_action" || msg.type === "host_command") {
            const targetId = String(msg.target_participant_id || msg.participant_id || "");
            const myId = String(this.myParticipantId || "");
            if ((msg.action === "remove_participant" || msg.action === "remove") && targetId && myId && targetId === myId) {
                this.shutdownAllMedia();
                window.location.href = `/foundation/rooms/${this.roomCode}/prejoin/`;
                return;
            }
            if (
                (msg.action === "mute_participant" && targetId && myId && targetId === myId) ||
                (msg.action === "mute_all" && !this.isHost)
            ) {
                if (!this.isAudioMuted) {
                    await this.toggleMicrophone(true);
                    this.setMicStatus("Your microphone was muted by the meeting host.");
                }
            }
            if (msg.action === "grant_floor" && targetId && myId && targetId === myId) {
                this.setMicStatus("Speaker floor granted by host — you may now unmute.");
            }
        }

        if (msg.type === "screenshare_state") {
            if (!msg.is_sharing && !this.isScreenSharing) {
                this.detachScreenTrack();
            }
        }

        // Force delta reconciliation on next fetch to apply updated participant roster / permissions immediately
        this.lastStateVersion = "";
        await this.fetchLatestTranscript(false);
    }

    syncRecordingState(recState) {
        if (!recState || typeof recState !== "object") return;
        this.isCloudRecording = Boolean(recState.is_recording);
        const recPill = document.getElementById("cloud-recording-pill");
        const recBtn = document.getElementById("btn-toggle-cloud-recording");
        if (recPill) {
            recPill.style.display = this.isCloudRecording ? "inline-flex" : "none";
        }
        if (recBtn) {
            recBtn.textContent = this.isCloudRecording ? "⏹ Stop Recording" : "⏺ Record to Cloud";
            recBtn.style.background = this.isCloudRecording ? "rgba(239,68,68,0.25)" : "rgba(255,255,255,0.1)";
            recBtn.style.borderColor = this.isCloudRecording ? "rgba(239,68,68,0.5)" : "rgba(255,255,255,0.18)";
        }
    }

    async toggleCloudRecording() {
        if (!this.switchLangUrl || !this.isHost) return;
        try {
            const formData = new URLSearchParams();
            formData.append("action", "toggle_recording");
            const resp = await fetch(this.switchLangUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": this.getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData.toString()
            });
            const data = await resp.json().catch(() => ({}));
            if (resp.ok) {
                if (data.recording_state) {
                    this.syncRecordingState(data.recording_state);
                }
                if (data.message) {
                    this.setMicStatus(data.message);
                }
            } else {
                if (data.recording_state) {
                    this.syncRecordingState(data.recording_state);
                }
                this.setMicStatus(data.error || "Cloud recording unavailable — verify LiveKit Egress is active.");
            }
        } catch (_) {}
    }

    async toggleWebinarMode() {
        if (!this.switchLangUrl || !this.isHost) return;
        try {
            const formData = new URLSearchParams();
            formData.append("action", "toggle_webinar_mode");
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
                this.webinarMode = Boolean(data.webinar_mode);
                const btn = document.getElementById("btn-toggle-webinar-mode");
                if (btn) {
                    btn.textContent = this.webinarMode ? "STAGE: WEBINAR (1000+)" : "STAGE: INTERACTIVE";
                }
            }
        } catch (_) {}
    }

    createLiveKitBlurTrackProcessor() {
        return {
            name: "background-blur",
            processedTrack: null,
            _sourceVideo: null,
            _canvas: null,
            _ctx: null,
            _rafId: null,
            _stream: null,
            async init(opts) {
                const track = opts && opts.track;
                if (!track) return;
                const settings = (typeof track.getSettings === "function" ? track.getSettings() : {}) || {};
                const width = settings.width || 640;
                const height = settings.height || 360;
                const videoEl = document.createElement("video");
                videoEl.muted = true;
                videoEl.playsInline = true;
                videoEl.srcObject = new MediaStream([track]);
                try { await videoEl.play(); } catch (_) {}
                const canvas = document.createElement("canvas");
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext("2d");
                this._sourceVideo = videoEl;
                this._canvas = canvas;
                this._ctx = ctx;

                const renderFrame = () => {
                    if (!this._ctx || !this._sourceVideo) return;
                    const w = canvas.width;
                    const h = canvas.height;
                    ctx.save();
                    ctx.filter = "blur(14px)";
                    ctx.drawImage(videoEl, 0, 0, w, h);
                    ctx.restore();

                    ctx.save();
                    ctx.beginPath();
                    ctx.ellipse(w * 0.5, h * 0.54, w * 0.27, h * 0.38, 0, 0, Math.PI * 2);
                    ctx.clip();
                    ctx.filter = "none";
                    ctx.drawImage(videoEl, 0, 0, w, h);
                    ctx.restore();
                    this._rafId = requestAnimationFrame(renderFrame);
                };
                renderFrame();
                this._stream = canvas.captureStream(24);
                this.processedTrack = this._stream.getVideoTracks()[0] || track;
            },
            async restart(opts) {
                await this.destroy();
                await this.init(opts);
            },
            async destroy() {
                if (this._rafId) {
                    cancelAnimationFrame(this._rafId);
                    this._rafId = null;
                }
                if (this._stream) {
                    this._stream.getTracks().forEach((t) => { try { t.stop(); } catch (_) {} });
                    this._stream = null;
                }
                if (this._sourceVideo) {
                    try { this._sourceVideo.pause(); } catch (_) {}
                    this._sourceVideo.srcObject = null;
                    this._sourceVideo = null;
                }
                this.processedTrack = null;
            }
        };
    }

    async applyCameraBlurProcessor(enableBlur) {
        if (!this.localCameraTrack) return;
        try {
            if (enableBlur && typeof this.localCameraTrack.setProcessor === "function") {
                this.blurProcessor = this.createLiveKitBlurTrackProcessor();
                await this.localCameraTrack.setProcessor(this.blurProcessor);
            } else if (!enableBlur && typeof this.localCameraTrack.stopProcessor === "function") {
                await this.localCameraTrack.stopProcessor();
                this.blurProcessor = null;
            }
        } catch (err) {
            console.warn("[WDOS Multilingua] TrackProcessor background blur error:", err);
        }
    }

    async toggleBackgroundBlur() {
        this.isBackgroundBlurEnabled = !this.isBackgroundBlurEnabled;
        await this.applyCameraBlurProcessor(this.isBackgroundBlurEnabled);
        const btn = document.getElementById("btn-toggle-bg-blur");
        if (btn) {
            btn.classList.toggle("active", Boolean(this.isBackgroundBlurEnabled));
            const span = btn.querySelector("span");
            if (span) {
                span.textContent = this.isBackgroundBlurEnabled ? "Blur: On" : "Blur: Off";
            } else {
                btn.textContent = this.isBackgroundBlurEnabled ? "Blur: On" : "Blur: Off";
            }
        }
        if (this.isVideoOff) {
            this.setMicStatus(
                this.isBackgroundBlurEnabled
                    ? "Background Blur enabled — will process outgoing WebRTC video when camera is turned on."
                    : "Background Blur turned off."
            );
        } else {
            this.setMicStatus(
                this.isBackgroundBlurEnabled
                    ? "WebRTC Background Blur active on outgoing camera stream."
                    : "WebRTC Background Blur turned off."
            );
        }
    }

    renderPolls(polls) {
        const container = document.getElementById("live-polls-container");
        if (!container || !Array.isArray(polls)) return;
        if (polls.length === 0) {
            container.innerHTML = "";
            return;
        }
        container.innerHTML = polls.slice(-3).reverse().map((poll) => {
            const total = poll.total_votes || 0;
            const optsHtml = (poll.options || []).map((opt, idx) => {
                const count = (poll.votes && poll.votes[idx]) || 0;
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return `
                    <button type="button" class="js-vote-poll-btn" data-poll-id="${this.escapeHtml(poll.id)}" data-opt-idx="${idx}" ${!poll.is_open ? "disabled" : ""} style="width:100%;text-align:left;background:#F9FAFB;border:1px solid #E5E7EB;border-radius:8px;padding:6px 10px;margin-bottom:5px;font-size:12px;font-weight:600;cursor:pointer;display:flex;justify-content:space-between;align-items:center;">
                        <span>${this.escapeHtml(opt)}</span>
                        <span style="font-size:11px;color:#D4006A;font-weight:700;">${count} (${pct}%)</span>
                    </button>
                `;
            }).join("");
            return `
                <div style="background:#FFF;border:1px solid #E5E7EB;border-radius:10px;padding:10px 12px;margin-bottom:10px;">
                    <div style="font-size:12.5px;font-weight:800;color:#19131A;margin-bottom:6px;">📊 ${this.escapeHtml(poll.question)}</div>
                    ${optsHtml}
                    <div style="font-size:10.5px;color:#6B7280;margin-top:4px;">${total} vote(s) · ${poll.is_open ? "Live Poll Open" : "Closed"}</div>
                </div>
            `;
        }).join("");
    }

    appendRealtimeSegmentToFeed(seg) {
        if (!seg) return;
        this.cachedSegments = this.cachedSegments || [];
        const exists = this.cachedSegments.some((s) => String(s.id || s.sequence_number) === String(seg.id || seg.sequence_number));
        if (!exists) {
            this.cachedSegments.push(seg);
            if (this.cachedSegments.length > 120) {
                this.cachedSegments = this.cachedSegments.slice(-120);
            }
            this.hasLiveSegments = true;
            this.renderTranscriptFeed(this.cachedSegments);
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

    async submitChatMessage(form) {
        const input = form.querySelector("#room-chat-input") || form.querySelector("input[name='message_text']");
        if (!input || !input.value.trim()) return;
        const text = input.value.trim();
        const isAnnouncement = Boolean(form.querySelector("#chat-is-announcement")?.checked);
        const sendBtn = form.querySelector("button[type='submit']");
        const origBtnText = sendBtn ? sendBtn.textContent : "";
        if (sendBtn) {
            sendBtn.disabled = true;
            sendBtn.textContent = "...";
        }
        input.value = "";

        try {
            const formData = new URLSearchParams();
            formData.append("message_text", text);
            formData.append("is_announcement", isAnnouncement ? "1" : "0");
            formData.append("sender_name", this.userDisplayName);

            const targetUrl = this.chatUrl || `/api/rooms/${this.roomCode}/chat/`;
            const resp = await fetch(targetUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-CSRFToken": this.getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData.toString(),
            });

            if (resp.ok) {
                const data = await resp.json();
                if (data && data.chat_message) {
                    this.appendChatMessage(data.chat_message, true);
                    if (this.livekitRoom && this.livekitRoom.state === "connected" && this.livekitRoom.localParticipant) {
                        try {
                            const payloadStr = JSON.stringify({ type: "chat_message", message: data.chat_message });
                            this.livekitRoom.localParticipant.publishData(
                                new TextEncoder().encode(payloadStr),
                                { reliable: true, topic: "wdos_chat" }
                            ).catch(() => {});
                        } catch (_) {}
                    }
                }
            }
        } catch (_) {
        } finally {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.textContent = origBtnText || "Send";
            }
        }
    }

    isChatTabActive() {
        const chatPane = document.getElementById("tab-pane-chat");
        if (!chatPane) return false;
        try {
            return window.getComputedStyle(chatPane).display !== "none";
        } catch (_) {
            return chatPane.style.display !== "none";
        }
    }

    clearUnreadChatCount() {
        this.unreadChatCount = 0;
        const dockBadge = document.getElementById("dock-chat-badge");
        if (dockBadge) {
            dockBadge.style.display = "none";
            dockBadge.textContent = "0";
        }
        try {
            if (this.roomCode) {
                sessionStorage.setItem(`wdos_chat_read_${this.roomCode}`, "1");
            }
        } catch (_) {}
    }

    syncChatMessages(messages) {
        if (!Array.isArray(messages)) return;
        let added = false;
        messages.forEach((msg) => {
            if (msg) {
                const msgId = String(msg.id || `${msg.sender_name}_${msg.timestamp}_${(msg.message_text || "").slice(0, 10)}`);
                if (!this.seenChatIds.has(msgId)) {
                    this.appendChatMessage(msg, false);
                    added = true;
                }
            }
        });
        if (added) {
            const feed = document.getElementById("room-chat-feed");
            if (feed) feed.scrollTop = feed.scrollHeight;
        }
    }

    appendChatMessage(msg, isLocal = false) {
        if (!msg || !msg.message_text) return;
        const msgId = String(msg.id || `${msg.sender_name}_${msg.timestamp}_${(msg.message_text || "").slice(0, 10)}`);
        if (this.seenChatIds.has(msgId)) return;
        this.seenChatIds.add(msgId);

        const feed = document.getElementById("room-chat-feed");
        if (!feed) return;

        const emptyNotice = document.getElementById("chat-empty-notice");
        if (emptyNotice) {
            emptyNotice.remove();
        }

        const isMe = msg.sender_name === this.userDisplayName;
        const isAnnouncement = Boolean(msg.is_host_announcement);

        let roleBadge = "";
        if (isAnnouncement) {
            roleBadge = `<span style="font-size:10px; background:#D97706; color:#FFF; padding:1px 5px; border-radius:4px; margin-left:4px;">ANNOUNCEMENT</span>`;
        } else if (msg.sender_role === "Host") {
            roleBadge = `<span style="font-size:10px; background:#FCEEF5; color:#D4006A; padding:1px 5px; border-radius:4px; margin-left:4px;">Host</span>`;
        } else if (msg.sender_role === "Co-Host") {
            roleBadge = `<span style="font-size:10px; background:#EDE9FE; color:#6D28D9; padding:1px 5px; border-radius:4px; margin-left:4px;">Co-Host</span>`;
        }

        const bgStyle = isAnnouncement
            ? "background:#FEF3C7; border:1px solid #FCD34D;"
            : (isMe ? "background:#FCEEF5; border:1px solid #F4C2DA; margin-left:12px;" : "background:#F9FAFB; border:1px solid #E5E7EB; margin-right:12px;");

        const msgDiv = document.createElement("div");
        msgDiv.className = "zm-chat-msg";
        msgDiv.setAttribute("data-chat-id", msgId);
        msgDiv.style.cssText = `padding:8px 12px; border-radius:10px; ${bgStyle}`;
        msgDiv.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:3px;">
                <span style="font-size:12px; font-weight:800; color:${isAnnouncement ? '#92400E' : '#19131A'};">
                    ${this.escapeHtml(msg.sender_name)}${roleBadge}
                </span>
                <span style="font-size:10.5px; color:#6B7280;">${this.escapeHtml(msg.timestamp || "")}</span>
            </div>
            <div style="font-size:13px; color:#1F2937; word-break:break-word; line-height:1.4;">${this.escapeHtml(msg.message_text)}</div>
        `;

        feed.appendChild(msgDiv);
        feed.scrollTop = feed.scrollHeight;

        const tabBadge = document.getElementById("tab-count-chat");
        if (tabBadge) {
            tabBadge.textContent = `${this.seenChatIds.size}`;
        }

        const dockBadge = document.getElementById("dock-chat-badge");
        if (this.isChatTabActive()) {
            this.clearUnreadChatCount();
        } else {
            if (!isMe && !isLocal) {
                this.unreadChatCount = (this.unreadChatCount || 0) + 1;
                if (dockBadge) {
                    dockBadge.textContent = `${this.unreadChatCount}`;
                    dockBadge.style.display = "inline-flex";
                }
            }
        }
    }

    startLivePolling() {
        // Strictly Event-Driven Architecture (Google Meet / Zoom / Teams standard):
        // Performs a single one-time state hydration on room boot. All subsequent updates
        // (audio, video, screen share, live captions, chat, reactions, polls, and host governance)
        // are pushed in real time over LiveKit WebRTC Media Tracks and DataChannels — zero HTTP polling loops.
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
        return this.fetchLatestTranscript(false);
    }

    async fetchLatestTranscript(speakNewSegments = true) {
        if (!this.transcriptUrl || this.isFetchingTranscript) return;
        this.isFetchingTranscript = true;
        try {
            const shortListen = this.getShortLang(this.listeningLang);
            const stateParam = this.lastStateVersion ? `&mode=delta&state_v=${encodeURIComponent(this.lastStateVersion)}` : "&mode=delta";
            const seqParam = this.lastSeenSequence > 0 ? `&after_seq=${this.lastSeenSequence}` : "";
            const resp = await fetch(`${this.transcriptUrl}?lang=${encodeURIComponent(shortListen)}${stateParam}${seqParam}`, {
                headers: { "Accept": "application/json" }
            });
            if (resp.status === 304) {
                this.unchangedPollStreak = (this.unchangedPollStreak || 0) + 1;
                return;
            }
            if (!resp.ok) return;
            const data = await resp.json();

            if (data.state_v) {
                this.lastStateVersion = String(data.state_v);
            }

            // Fast-path: Server confirmed room state is unchanged (~80-byte delta cursor response)
            if (data.unchanged === true) {
                this.unchangedPollStreak = (this.unchangedPollStreak || 0) + 1;
                if (typeof data.latest_seq === "number") {
                    this.lastSeenSequence = Math.max(this.lastSeenSequence, data.latest_seq);
                }
                if (data.live_interim && data.live_interim.original_text) {
                    const liveInterim = data.live_interim;
                    const hasActiveLocalInterim = Boolean(
                        (this.lastLocalInterimAt && (Date.now() - this.lastLocalInterimAt < 2500)) ||
                        (this.lastServerCaptionAt && (Date.now() - this.lastServerCaptionAt < 2500))
                    );
                    if (liveInterim.speaker_name !== this.userDisplayName || !hasActiveLocalInterim) {
                        this.triggerSpeakingPulse(liveInterim.speaker_name, 1600);
                        const interimTrans = (liveInterim.translations || {})[shortListen] || liveInterim.translated_text || liveInterim.original_text;
                        this.renderLiveCaption(liveInterim.speaker_name, liveInterim.original_text, interimTrans, false);
                    }
                }
                return;
            }

            this.unchangedPollStreak = 0;

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
            if (data.recording_state) {
                this.syncRecordingState(data.recording_state);
            }
            if (typeof data.webinar_mode === "boolean") {
                this.webinarMode = data.webinar_mode;
                const webBtn = document.getElementById("btn-toggle-webinar-mode");
                if (webBtn) {
                    webBtn.textContent = this.webinarMode ? "STAGE: WEBINAR (1000+)" : "STAGE: INTERACTIVE";
                }
            }
            if (Array.isArray(data.polls)) {
                this.cachedPolls = data.polls;
                this.renderPolls(data.polls);
            }
            if (data.my_participant) {
                if (data.my_participant.admission_status === "REMOVED" || data.my_participant.admission_status === "DENIED") {
                    this.shutdownAllMedia();
                    window.location.href = this.isGuest ? "/auth/login/" : "/foundation/meetings/";
                    return;
                }
                if (data.my_participant.admission_status === "LEFT") {
                    this.shutdownAllMedia();
                    window.location.href = `/foundation/rooms/${this.roomCode}/prejoin/`;
                    return;
                }
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

            if (typeof data.is_locked === "boolean") {
                const lockBadge = document.getElementById("badge-room-lock-status");
                const popoverLockBadge = document.getElementById("popover-lock-badge");
                const lockBtn = document.getElementById("btn-toggle-room-lock");
                if (lockBadge) lockBadge.style.display = data.is_locked ? "inline-flex" : "none";
                if (popoverLockBadge) {
                    popoverLockBadge.textContent = data.is_locked ? "Locked (Blocks entry)" : "Unlocked";
                    popoverLockBadge.style.background = data.is_locked ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.18)";
                    popoverLockBadge.style.color = data.is_locked ? "#FCA5A5" : "#86EFAC";
                    popoverLockBadge.style.borderColor = data.is_locked ? "rgba(239,68,68,0.4)" : "rgba(134,239,172,0.35)";
                }
                if (lockBtn) {
                    lockBtn.innerHTML = data.is_locked ? "<span>🔓 Unlock Meeting Room</span>" : "<span>🔒 Lock Meeting Room</span>";
                }
            }

            if (typeof data.has_passcode === "boolean") {
                const passBadge = document.getElementById("badge-passcode-status");
                const popoverPassBadge = document.getElementById("popover-passcode-badge");
                if (passBadge) passBadge.style.display = data.has_passcode ? "inline-flex" : "none";
                if (popoverPassBadge) {
                    popoverPassBadge.textContent = data.has_passcode ? "Passcode Set" : "No Passcode";
                    popoverPassBadge.style.background = data.has_passcode ? "rgba(245,158,11,0.2)" : "rgba(255,255,255,0.1)";
                    popoverPassBadge.style.color = data.has_passcode ? "#FCD34D" : "#E5D9E6";
                }
            }

            if (typeof data.allow_participant_screen_share === "boolean") {
                this.allowParticipantScreenShare = data.allow_participant_screen_share;
                const policyBtn = document.getElementById("btn-toggle-screenshare-policy");
                const policyInput = document.getElementById("input-screenshare-policy-action");
                const policyLabel = document.getElementById("screenshare-policy-btn-label");
                if (policyLabel) {
                    policyLabel.textContent = data.allow_participant_screen_share ? "Screen Share: All Allowed" : "Screen Share: Host Only";
                }
                if (policyBtn) {
                    policyBtn.style.background = data.allow_participant_screen_share ? "#DCFCE7" : "#F3F4F6";
                    policyBtn.style.color = data.allow_participant_screen_share ? "#166534" : "#4B5563";
                    policyBtn.style.borderColor = data.allow_participant_screen_share ? "#86EFAC" : "#E5E7EB";
                }
                if (policyInput) {
                    policyInput.value = data.allow_participant_screen_share ? "host_only" : "all_participants";
                }
            }

            if (typeof data.can_share_screen === "boolean") {
                this.canShareScreen = data.can_share_screen;
            }
            if (data.my_participant) {
                if (typeof data.my_participant.can_share_screen === "boolean") {
                    this.canShareScreen = data.my_participant.can_share_screen;
                }
                if (data.my_participant.meeting_role === "Host" || data.my_participant.meeting_role === "Co-Host") {
                    this.canShareScreen = true;
                }
            }
            this.updateScreenShareButtonVisibility();

            if (typeof data.active_screenshare_presenter === "string") {
                const newPresenter = data.active_screenshare_presenter.trim();
                if (!this.isScreenSharing && !newPresenter && this.activeScreensharePresenter) {
                    this.detachScreenTrack();
                }
            }

            if (Array.isArray(data.waiting_participants)) {
                this.renderWaitingRoomQueue(data.waiting_participants);
            }

            if (Array.isArray(data.participants)) {
                this.participantCount = data.participants.length;
                this.cachedParticipants = data.participants;
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
                this.renderVideoGrid(data.participants);
            }

            if (Array.isArray(data.chat_messages)) {
                this.syncChatMessages(data.chat_messages);
            }

            const incomingSegments = data.segments || [];
            if (incomingSegments.length > 0) {
                const existingBySeq = new Map((this.cachedSegments || []).map((s) => [s.sequence_number, s]));
                incomingSegments.forEach((seg) => {
                    existingBySeq.set(seg.sequence_number, seg);
                });
                this.cachedSegments = Array.from(existingBySeq.values())
                    .sort((a, b) => (a.sequence_number || 0) - (b.sequence_number || 0))
                    .slice(-120);
            }
            const segments = this.cachedSegments || [];
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
                    this.lastTranslatedText = translated;
                    this.lastOriginalText = latest.original_text || "";
                    this.lastOriginalLang = latest.original_language || "en-US";
                    this.renderLiveCaption(latest.speaker_name, latest.original_text, translated, true);
                } else if (liveInterim) {
                    if (liveInterim.speaker_name !== this.userDisplayName || !hasActiveLocalInterim) {
                        this.triggerSpeakingPulse(liveInterim.speaker_name, 1600);
                        const interimTrans = (liveInterim.translations || {})[shortListen] || liveInterim.translated_text || liveInterim.original_text;
                        this.renderLiveCaption(liveInterim.speaker_name, liveInterim.original_text, interimTrans, false);
                    }
                } else if (!hasActiveLocalInterim) {
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
              <div style="font-size:12.5px; font-weight:700; color:#19131A; display:flex; align-items:center; gap:4px; flex-wrap:wrap;">
                <span>${this.escapeHtml(wp.participant_name)}</span>
                ${wp.is_guest 
                  ? '<span style="font-size:10px; font-weight:700; color:#B45309; background:#FEF3C7; border:1px solid #FCD34D; border-radius:4px; padding:1px 5px;" title="Unverified guest join">⚠️ Unverified Guest</span>'
                  : '<span style="font-size:10px; font-weight:700; color:#15803D; background:#DCFCE7; border:1px solid #86EFAC; border-radius:4px; padding:1px 5px;" title="Verified registered member">✓ Verified Member</span>'}
              </div>
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

        const unverifiedCount = cleanList.filter((wp) => wp.is_guest).length;
        const unverifiedNotice = unverifiedCount > 0
          ? `<div style="color:#B45309; font-weight:700; margin-top:4px;">⚠️ Notice: Queue contains ${unverifiedCount} unverified guest(s). Please verify identities before admitting.</div>`
          : "";

        container.innerHTML = `
          <div id="waiting-room-queue" style="margin-bottom:12px; padding:10px 12px; border-radius:12px; background:#FFFBEB; border:1px solid #FDE68A;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <span style="font-size:12px; font-weight:800; color:#92400E;">Waiting Lobby (${cleanList.length})</span>
              <button type="button" id="btn-admit-all-trigger" onclick="if(typeof toggleAdmitAllConfirm==='function')toggleAdmitAllConfirm(true);" style="background:#D97706; color:#FFF; border:none; border-radius:6px; padding:3px 9px; font-size:11px; font-weight:700; cursor:pointer;">Admit All</button>
            </div>

            <div id="confirm-admit-all-box" style="display:none; margin-bottom:10px; padding:10px 12px; border-radius:8px; background:#FEF3C7; border:1.5px solid #F59E0B;">
              <div style="font-size:12px; font-weight:800; color:#92400E; margin-bottom:4px;">⚠️ Confirm Admit All</div>
              <div id="confirm-admit-all-msg" style="font-size:11.5px; color:#78350F; line-height:1.4; margin-bottom:8px;">
                Are you sure you want to admit all <strong>${cleanList.length}</strong> participant(s)?
                ${unverifiedNotice}
              </div>
              <div style="display:flex; justify-content:flex-end; gap:8px;">
                <button type="button" onclick="if(typeof toggleAdmitAllConfirm==='function')toggleAdmitAllConfirm(false);" style="background:#F3F4F6; color:#374151; border:1px solid #D1D5DB; border-radius:6px; padding:3px 8px; font-size:11px; font-weight:700; cursor:pointer;">Cancel</button>
                <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                  <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                  <input type="hidden" name="action" value="admit_all">
                  <input type="hidden" name="confirmed" value="1">
                  <button type="submit" id="btn-confirm-admit-all" style="background:#16A34A; color:#FFF; border:none; border-radius:6px; padding:4px 10px; font-size:11px; font-weight:700; cursor:pointer;">Yes, Admit All</button>
                </form>
              </div>
            </div>

            ${rowsHtml}
          </div>
        `;
    }

    renderParticipantsList(participants, force = false) {
        const container = document.getElementById("live-participants-list");
        const countEl = document.getElementById("live-participants-count");
        if (countEl) countEl.textContent = `${participants.length}`;
        const tabCountEl = document.getElementById("tab-count-people");
        if (tabCountEl) tabCountEl.textContent = `${participants.length}`;
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
            const screenBadge = p.can_share_screen ? `<span style="font-size:10px; font-weight:700; background:#DCFCE7; color:#166534; border:1px solid #BBF7D0; border-radius:4px; padding:1px 5px; margin-left:4px;">Screen Share</span>` : "";
            const guestBadge = p.is_guest ? `<span style="font-size:10px; font-weight:700; color:#B45309; background:#FEF3C7; border:1px solid #FCD34D; border-radius:4px; padding:1px 5px; margin-left:4px;" title="Unverified guest">Guest</span>` : "";
            const hostControls = (this.isHost && p.meeting_role !== "Host") ? `
              <div style="width:100%; display:flex; justify-content:flex-end; gap:6px; margin-top:6px; padding-top:6px; border-top:1px dashed #EFE6EE; flex-wrap:wrap;">
                <form method="post" action="${actionUrl}" class="js-host-ajax-form" style="display:inline;">
                  <input type="hidden" name="csrfmiddlewaretoken" value="${csrf}">
                  <input type="hidden" name="action" value="toggle_screenshare_permission">
                  <input type="hidden" name="participant_id" value="${this.escapeHtml(p.id)}">
                  <button type="submit" style="background:${p.can_share_screen ? '#FEE2E2' : '#ECFDF5'}; color:${p.can_share_screen ? '#991B1B' : '#047857'}; border:1px solid ${p.can_share_screen ? '#FCA5A5' : '#A7F3D0'}; border-radius:6px; padding:2px 8px; font-size:11px; font-weight:700; cursor:pointer;">${p.can_share_screen ? 'Revoke Share' : 'Allow Share'}</button>
                </form>
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
                  <div class="zm-person-name">${this.escapeHtml(p.participant_name)}${guestBadge}${handBadge}${screenBadge}</div>
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
