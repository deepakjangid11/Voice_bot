const API_URL = "/chat";

const micButton = document.getElementById("micButton");
const micIcon = document.getElementById("micIcon");
const buttonText = document.getElementById("buttonText");
const stateText = document.getElementById("stateText");
const hint = document.getElementById("hint");
const recordingTime = document.getElementById("recordingTime");
const conversation = document.getElementById("conversation");
const emptyState = document.getElementById("emptyState");
const auraStage = document.getElementById("auraStage");
const noiseToast = document.getElementById("noiseToast");

let mediaRecorder = null;
let audioChunks = [];
let stream = null;
let audioContext = null;
let analyser = null;
let filter = null;
let animationFrame = null;
let timer = null;
let seconds = 0;
let currentAudio = null;
let vadInstance = null;

let assistantActive = false;
let processing = false;
let speaking = false;
let speechDetected = false;

let speechStartedAt = 0;
let silenceStartedAt = null;
let activeAudioSession = 0;
let responseLatencyStart = null;

let noiseFloor = 0.008;
let noiseSamples = [];
let noiseCalibrationStartedAt = 0;
let noiseToastTimeout = null;

const NOISE_CALIBRATION_TIME = 600;
const HIGH_NOISE_THRESHOLD = 0.045;

function setState(state, message) {
    if (stateText) {
        stateText.textContent = state;
        stateText.className = `state-pill ${state.toLowerCase()}`;
    }

    if (hint && message) {
        hint.textContent = message;
    }

    if (auraStage) {
        auraStage.className = `aura-stage ${state.toLowerCase()}`;
    }

    updateControlsUI(state);
}

function updateControlsUI(state) {
    if (!buttonText || !micButton) return;

    if (speaking) {
        buttonText.textContent = "TAP TO INTERRUPT";
        if (micIcon) micIcon.textContent = "⏹";
        micButton.className = "primary-voice-btn active speaking";
    } else if (state === "LISTENING") {
        buttonText.textContent = "LISTENING...";
        if (micIcon) micIcon.textContent = "🎙";
        micButton.className = "primary-voice-btn active";
    } else if (state === "THINKING") {
        buttonText.textContent = "PROCESSING...";
        if (micIcon) micIcon.textContent = "✦";
        micButton.className = "primary-voice-btn active";
    } else {
        buttonText.textContent = "TAP TO TALK";
        if (micIcon) micIcon.textContent = "🎙";
        micButton.className = "primary-voice-btn";
    }
}

function updateTime() {
    const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
    const secs = String(seconds % 60).padStart(2, "0");
    if (recordingTime) {
        recordingTime.textContent = `${minutes}:${secs}`;
    }
}

function startTimer() {
    clearInterval(timer);
    timer = setInterval(function() {
        seconds++;
        updateTime();
    }, 1000);
}

function stopTimer() {
    clearInterval(timer);
    timer = null;
}

function resetTimer() {
    stopTimer();
    seconds = 0;
    updateTime();
}

function activateStageLayout() {
    const stage = document.getElementById("appStage");
    if (stage && !stage.classList.contains("active-mode")) {
        stage.classList.add("active-mode");
    }
}

function addMessage(role, text) {
    if (!text || !conversation) {
        return;
    }

    activateStageLayout();

    if (emptyState && emptyState.parentNode) {
        emptyState.remove();
    }

    const message = document.createElement("div");
    message.className = `message ${role}`;

    const label = document.createElement("span");
    label.className = "message-label";
    label.textContent = role === "user" ? "YOU" : "NOVA";

    const content = document.createElement("div");
    content.textContent = text;

    message.appendChild(label);
    message.appendChild(content);
    conversation.appendChild(message);

    conversation.scrollTop = conversation.scrollHeight;
}

function getMimeType() {
    if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
        return "audio/webm;codecs=opus";
    }
    if (MediaRecorder.isTypeSupported("audio/webm")) {
        return "audio/webm";
    }
    return "";
}

function cleanupAudioAnalysis() {
    if (animationFrame) {
        cancelAnimationFrame(animationFrame);
        animationFrame = null;
    }

    if (audioContext) {
        audioContext.close().catch(function() {});
    }

    audioContext = null;
    analyser = null;
    filter = null;
    silenceStartedAt = null;
}

async function cleanupVAD() {
    if (!vadInstance) {
        return;
    }

    const currentVAD = vadInstance;
    vadInstance = null;

    try {
        await currentVAD.pause();
    } catch (error) {}

    try {
        await currentVAD.destroy();
    } catch (error) {}
}

async function cleanupStream() {
    await cleanupVAD();

    if (stream) {
        stream.getTracks().forEach(function(track) {
            track.stop();
        });
        stream = null;
    }

    cleanupAudioAnalysis();
}

function getRms(data) {
    let sum = 0;
    for (let i = 0; i < data.length; i++) {
        const value = (data[i] - 128) / 128;
        sum += value * value;
    }
    return Math.sqrt(sum / data.length);
}

function resetNoiseCalibration() {
    noiseFloor = 0.008;
    noiseSamples = [];
    noiseCalibrationStartedAt = Date.now();
}

function updateNoiseFloor(rms, now) {
    if (now - noiseCalibrationStartedAt > NOISE_CALIBRATION_TIME) {
        if (noiseSamples.length > 0) {
            const sorted = [...noiseSamples].sort(function(a, b) {
                return a - b;
            });
            const middle = Math.floor(sorted.length / 2);
            noiseFloor = sorted[middle];
        }
        return;
    }

    noiseSamples.push(rms);
    if (noiseSamples.length > 100) {
        noiseSamples.shift();
    }
}

function hideNoiseAlert() {
    if (noiseToastTimeout) {
        clearTimeout(noiseToastTimeout);
        noiseToastTimeout = null;
    }
    if (noiseToast) {
        noiseToast.classList.remove("show");
        noiseToast.style.display = "none";
    }
}

function showNoiseAlert() {
    if (!noiseToast || !assistantActive || speaking || processing) return;

    noiseToast.style.display = "flex";
    void noiseToast.offsetWidth;
    noiseToast.classList.add("show");

    if (noiseToastTimeout) {
        clearTimeout(noiseToastTimeout);
    }

    noiseToastTimeout = setTimeout(function() {
        if (noiseToast) {
            noiseToast.classList.remove("show");
            setTimeout(function() {
                if (noiseToast && !noiseToast.classList.contains("show")) {
                    noiseToast.style.display = "none";
                }
            }, 300);
        }
    }, 3000);
}

function checkBackgroundNoise(rms, now) {
    if (now - noiseCalibrationStartedAt < NOISE_CALIBRATION_TIME) {
        return;
    }

    if (noiseFloor >= HIGH_NOISE_THRESHOLD || rms >= HIGH_NOISE_THRESHOLD * 1.5) {
        showNoiseAlert();
    }
}

function startNoiseMonitoring() {
    if (!stream) {
        return;
    }

    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();

        const source = audioContext.createMediaStreamSource(stream);

        filter = audioContext.createBiquadFilter();
        filter.type = "highpass";
        filter.frequency.value = 100;
        filter.Q.value = 0.7;

        analyser = audioContext.createAnalyser();
        analyser.fftSize = 2048;
        analyser.smoothingTimeConstant = 0.75;

        source.connect(filter);
        filter.connect(analyser);

        const data = new Uint8Array(analyser.fftSize);

        resetNoiseCalibration();

        function analyse() {
            if (!mediaRecorder || mediaRecorder.state !== "recording" || speaking) {
                return;
            }

            analyser.getByteTimeDomainData(data);

            const rms = getRms(data);
            const now = Date.now();

            updateNoiseFloor(rms, now);
            checkBackgroundNoise(rms, now);

            animationFrame = requestAnimationFrame(analyse);
        }

        animationFrame = requestAnimationFrame(analyse);
    } catch (error) {}
}

async function initializeVAD() {
    if (!stream) {
        return false;
    }

    if (!window.vad || !window.vad.MicVAD) {
        setState("VAD ERROR", "Voice detection could not be loaded");
        return false;
    }

    try {
        vadInstance = await window.vad.MicVAD.new({
            getStream: async function() {
                return stream;
            },
            model: "v5",
            positiveSpeechThreshold: 0.82,
            negativeSpeechThreshold: 0.45,
            minSpeechMs: 220,
            redemptionMs: 400,
            onSpeechStart: function() {
                if (!assistantActive || processing || speaking) {
                    return;
                }

                speechDetected = true;
                speechStartedAt = Date.now();
                silenceStartedAt = null;

                setState("LISTENING", "Listening to you...");
            },
            onSpeechEnd: function() {
                if (!assistantActive || processing || speaking) {
                    return;
                }

                if (!speechDetected) {
                    return;
                }

                const speechDuration = Date.now() - speechStartedAt;
                if (speechDuration < 200) {
                    return;
                }

                stopRecordingAndSend();
            },
            onVADMisfire: function() {
                speechDetected = false;
                speechStartedAt = 0;
                silenceStartedAt = null;

                if (assistantActive && !processing && !speaking) {
                    setState("LISTENING", "Listening... start speaking");
                }
            },
            onnxWASMBasePath: "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/",
            baseAssetPath: "https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.31/dist/"
        });

        await vadInstance.start();
        return true;
    } catch (error) {
        vadInstance = null;
        setState("VAD ERROR", "Voice detection could not start");
        return false;
    }
}

async function startRecording() {
    if (!assistantActive || processing || speaking) {
        return;
    }

    if (mediaRecorder && mediaRecorder.state === "recording") {
        return;
    }

    try {
        await cleanupVAD();

        if (stream) {
            stream.getTracks().forEach(function(track) {
                track.stop();
            });
            stream = null;
        }

        stream = await navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1
            }
        });

        const mimeType = getMimeType();
        if (mimeType) {
            mediaRecorder = new MediaRecorder(stream, { mimeType: mimeType });
        } else {
            mediaRecorder = new MediaRecorder(stream);
        }

        audioChunks = [];
        speechDetected = false;
        speechStartedAt = 0;
        silenceStartedAt = null;

        seconds = 0;
        updateTime();

        mediaRecorder.ondataavailable = function(event) {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = function() {
            cleanupAudioAnalysis();

            if (!speechDetected) {
                processing = false;
                if (assistantActive && !speaking) {
                    setState("LISTENING", "Listening... start speaking");
                }
                return;
            }

            sendAudio();
        };

        mediaRecorder.onerror = function() {
            cleanupStream();
            processing = false;
            responseLatencyStart = null;
        };

        mediaRecorder.start(100);
        startTimer();
        startNoiseMonitoring();

        const vadStarted = await initializeVAD();
        if (!vadStarted) {
            if (mediaRecorder && mediaRecorder.state === "recording") {
                mediaRecorder.onstop = null;
                mediaRecorder.stop();
            }
            await cleanupStream();
            assistantActive = false;
            setState("READY", "Click the microphone to start");
            return;
        }

        setState("LISTENING", "Listening... start speaking");
    } catch (error) {
        await cleanupStream();
        assistantActive = false;
        setState("MIC ERROR", "Please allow microphone access");
    }
}

function stopRecordingAndSend() {
    if (!mediaRecorder || mediaRecorder.state !== "recording") {
        return;
    }

    if (!speechDetected) {
        return;
    }

    responseLatencyStart = performance.now();

    stopTimer();
    cleanupAudioAnalysis();

    processing = true;

    setState("THINKING", "Processing your thoughts...");

    if (vadInstance) {
        vadInstance.pause().catch(function() {});
    }

    mediaRecorder.stop();

    if (stream) {
        stream.getTracks().forEach(function(track) {
            track.stop();
        });
        stream = null;
    }
}

function stopMonitor() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.onstop = null;
        mediaRecorder.stop();
    }
    cleanupStream();
}

function base64ToBlob(base64, mimeType) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return new Blob([bytes], { type: mimeType });
}

function isStopCommand(text) {
    const value = text
        .toLowerCase()
        .trim()
        .replace(/[.!?,]/g, "");

    const commands = [
        "stop",
        "stop listening",
        "stop now",
        "please stop",
        "okay stop",
        "ok stop",
        "shut up",
        "cancel"
    ];

    return commands.includes(value);
}

async function sendAudio() {
    try {
        await cleanupVAD();

        if (!audioChunks.length) {
            processing = false;
            responseLatencyStart = null;
            if (assistantActive && !speaking) {
                await startRecording();
            }
            return;
        }

        const mimeType = mediaRecorder?.mimeType || "audio/webm";
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        const extension = mimeType.includes("webm") ? "webm" : "wav";

        const formData = new FormData();
        formData.append("audio_file", audioBlob, `recording.${extension}`);

        const response = await fetch(API_URL, {
            method: "POST",
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`Server Error: ${errorText}`);
        }

        const data = await response.json();
        const userText = data.user_text || "";
        const responseText = data.response_text || "";

        if (userText) {
            addMessage("user", userText);
        }

        if (data.stopped || isStopCommand(userText)) {
            stopAssistant();
            setState("STOPPED", "Voice assistant stopped");
            hint.textContent = "Tap the microphone when you want to speak again";
            return;
        }

        if (responseText) {
            addMessage("ai", responseText);
        }

        if (!data.audio) {
            processing = false;
            responseLatencyStart = null;
            if (assistantActive) {
                setState("LISTENING", "Listening... start speaking");
                await startRecording();
            }
            return;
        }

        const audioBlobResponse = base64ToBlob(data.audio, "audio/mpeg");
        const audioUrl = URL.createObjectURL(audioBlobResponse);
        const audio = new Audio(audioUrl);

        const session = ++activeAudioSession;
        currentAudio = audio;

        audio.onplay = function() {
            if (responseLatencyStart !== null) {
                const latency = performance.now() - responseLatencyStart;
                console.log(`Latency: ${(latency / 1000).toFixed(2)}s`);
                responseLatencyStart = null;
            }
        };

        processing = false;
        speaking = true;

        setState("SPEAKING", "Nova is speaking... tap button to interrupt");

        audio.onended = async function() {
            if (session !== activeAudioSession) {
                return;
            }

            URL.revokeObjectURL(audioUrl);
            currentAudio = null;
            speaking = false;

            stopMonitor();
            resetTimer();

            if (assistantActive) {
                setTimeout(async function() {
                    if (assistantActive && !speaking) {
                        setState("LISTENING", "Listening... start speaking");
                        await startRecording();
                    }
                }, 250);
            } else {
                setState("READY", "Tap the microphone to start");
            }
        };

        audio.onerror = function() {
            URL.revokeObjectURL(audioUrl);
            currentAudio = null;
            speaking = false;
            processing = false;
            responseLatencyStart = null;

            stopMonitor();
            setState("ERROR", "Could not play AI response");
        };

        await audio.play();

    } catch (error) {
        processing = false;
        speaking = false;
        responseLatencyStart = null;

        await cleanupStream();
        setState("ERROR", "Connection issue, retrying...");

        if (assistantActive) {
            setTimeout(function() {
                if (assistantActive && !speaking) {
                    startRecording();
                }
            }, 1000);
        }
    }
}

function stopCurrentAudio(forceUserClick = false) {
    if (speaking && !forceUserClick) {
        return false;
    }

    activeAudioSession++;

    if (currentAudio) {
        currentAudio.pause();
        currentAudio.currentTime = 0;
        currentAudio = null;
    }

    speaking = false;
    responseLatencyStart = null;
    return true;
}

async function interruptBot() {
    stopCurrentAudio(true);
    stopTimer();
    resetTimer();
    hideNoiseAlert();

    assistantActive = true;
    processing = false;

    setState("LISTENING", "Interrupted. Speak now...");
    await startRecording();
}

async function startAssistant() {
    if (assistantActive) {
        return;
    }

    activateStageLayout();
    hideNoiseAlert();
    assistantActive = true;
    processing = false;
    speaking = false;
    responseLatencyStart = null;

    setState("LISTENING", "Listening... start speaking");
    await startRecording();
}

function stopAssistant() {
    assistantActive = false;
    processing = false;
    speaking = false;
    responseLatencyStart = null;

    stopCurrentAudio(true);
    stopTimer();
    stopMonitor();
    resetTimer();
    hideNoiseAlert();

    setState("READY", "Tap the microphone to start");
}

micButton.addEventListener("click", async function() {
    activateStageLayout();

    if (speaking) {
        await interruptBot();
        return;
    }

    if (assistantActive) {
        stopAssistant();
        return;
    }

    await startAssistant();
});

setState("READY", "Tap the microphone to begin a real-time conversation");
updateTime();
