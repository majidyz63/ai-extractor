// === 📋 سیستم لاگ دسته‌بندی شده ===
function log(msg, type = "INFO") {
    const debugBox = document.getElementById("debug");
    const timestamp = new Date().toISOString().split("T")[1].split(".")[0]; // فقط ساعت:دقیقه:ثانیه
    const line = `[${timestamp}] [${type}] ${msg}`;

    if (debugBox) {
        debugBox.textContent += line + "\n";
        debugBox.scrollTop = debugBox.scrollHeight;
    }

    if (type === "ERROR") console.error(line);
    else if (type === "SERVER") console.warn(line);
    else console.log(line);
}

// === گرفتن لیست مدل‌ها از سرور ===
async function fetchModels() {
    try {
        const resp = await fetch("/api/models");
        const data = await resp.json();
        const sel = document.getElementById("modelSelect");
        sel.innerHTML = "";
        (data.models || []).forEach(m => {
            const opt = document.createElement("option");
            opt.value = m;
            opt.textContent = m;
            sel.appendChild(opt);
        });
        log("Models loaded: " + JSON.stringify(data.models), "CLIENT");
    } catch (err) {
        log("⚠️ fetchModels failed: " + err, "ERROR");
    }
}

// === گرفتن لیست پرامپت‌ها از سرور ===
async function fetchPrompts() {
    try {
        const resp = await fetch("/api/prompts");
        const data = await resp.json();
        const sel = document.getElementById("promptSelect");
        sel.innerHTML = "";
        (data.prompts || []).forEach(p => {
            const opt = document.createElement("option");
            opt.value = p;
            opt.textContent = p;
            sel.appendChild(opt);
        });
        log("Prompts loaded: " + JSON.stringify(data.prompts), "CLIENT");
    } catch (err) {
        log("⚠️ fetchPrompts failed: " + err, "ERROR");
    }
}

// === نمایش ساده خروجی مدل (برای تست) ===
function renderExtractorOutput(data) {
    log("OUTPUT: " + JSON.stringify(data), "SERVER");

    const resultBox = document.getElementById("result");
    if (!resultBox) return;

    // فقط محتوای خام output رو نشون بده
    if (data.output) {
        resultBox.textContent = JSON.stringify(data.output, null, 2);
    } else {
        resultBox.textContent = "❌ خروجی خالی است یا داده ندارد.";
    }
}

// === DOMContentLoaded ===
document.addEventListener('DOMContentLoaded', async () => {
    await fetchModels();
    await fetchPrompts();
    await renderDynamicFields();
    document.getElementById('promptSelect').onchange = renderDynamicFields;
});

// ---------- WebSpeech API ----------
function startWebSpeech(lang) {
    if (!("webkitSpeechRecognition" in window)) {
        log("❌ Your browser does not support Web Speech API.", "ERROR");
        return;
    }

    const rec = new webkitSpeechRecognition();
    rec.lang = lang;
    rec.interimResults = true;
    rec.maxAlternatives = 1;
    rec.continuous = true;

    let finalTranscript = "";

    micBtn.textContent = "🎙️ Listening...";
    rec.start();

    rec.onresult = e => {
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
            const transcript = e.results[i][0].transcript;
            if (e.results[i].isFinal) {
                finalTranscript += transcript + " ";
            } else {
                interim += transcript;
            }
        }
        mainInput.value = (finalTranscript + interim).trim();
    };

    rec.onerror = (err) => {
        let msg = err.error || JSON.stringify(err);
        log("❌ Speech error: " + msg, "ERROR");
        micBtn.textContent = "🎤";
    };

    rec.onend = () => {
        micBtn.textContent = "🎤";
        mainInput.value = finalTranscript.trim();
    };
}

// ---------- Google / Vosk / Whisper ----------
async function recordAndSend(endpoint, langCode) {
    const blob = new Blob(chunks, { type: "audio/webm" });
    log("Final blob size: " + blob.size, "CLIENT");
    const arrayBuffer = await blob.arrayBuffer();
    const audioCtx = new AudioContext();
    const decoded = await audioCtx.decodeAudioData(arrayBuffer);

    const wavBuffer = audioBufferToWav(decoded);
    const wavBlob = new Blob([wavBuffer], { type: "audio/wav" });

    function mapWhisperLang(lang) {
        if (lang.startsWith("fa")) return "fa";
        if (lang.startsWith("en")) return "en";
        if (lang.startsWith("nl")) return "nl";
        if (lang.startsWith("fr")) return "fr";
        return "en";
    }

    const formData = new FormData();
    formData.append("file", wavBlob, "audio.wav");
    formData.append("lang", mapWhisperLang(langCode));

    try {
        const r = await fetch(endpoint, { method: "POST", body: formData });
        const data = await r.json();
        log("SERVER RESPONSE: " + JSON.stringify(data), "SERVER");

        if (data.title) {
            mainInput.value = `${data.title} ${data.date} ${data.time} ${data.location}`;
            renderExtractorOutput(data);
        } else if (data.text) {
            mainInput.value = data.text;
            document.getElementById('result').textContent = data.text;
            const outputArea = document.getElementById("outputArea");
            if (outputArea) outputArea.style.display = "none";
        } else {
            mainInput.value = "";
        }
    } catch (err) {
        log("Error sending audio: " + err, "ERROR");
    }
}

function audioBufferToWav(buffer) {
    const numOfChan = buffer.numberOfChannels,
        length = buffer.length * numOfChan * 2 + 44,
        buffer2 = new ArrayBuffer(length),
        view = new DataView(buffer2),
        channels = [],
        sampleRate = buffer.sampleRate;

    let offset = 0;
    function setUint16(data) { view.setUint16(offset, data, true); offset += 2; }
    function setUint32(data) { view.setUint32(offset, data, true); offset += 4; }

    setUint32(0x46464952);
    setUint32(length - 8);
    setUint32(0x45564157);

    setUint32(0x20746d66);
    setUint32(16);
    setUint16(1);
    setUint16(numOfChan);
    setUint32(sampleRate);
    setUint32(sampleRate * 2 * numOfChan);
    setUint16(numOfChan * 2);
    setUint16(16);

    setUint32(0x61746164);
    setUint32(length - offset - 4);

    for (let i = 0; i < buffer.numberOfChannels; i++)
        channels.push(buffer.getChannelData(i));

    let interleaved = interleave(channels[0], channels[1]);
    for (let i = 0; i < interleaved.length; i++, offset += 2) {
        let s = Math.max(-1, Math.min(1, interleaved[i]));
        view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }
    return buffer2;
}

function interleave(left, right) {
    if (!right) return left;
    const length = left.length + right.length;
    const result = new Float32Array(length);
    let index = 0, inputIndex = 0;
    while (index < length) {
        result[index++] = left[inputIndex];
        result[index++] = right[inputIndex];
        inputIndex++;
    }
    return result;
}

async function handleMediaRecorder(engine, lang) {
    if (!isRecording) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        chunks = [];

        mediaRecorder.ondataavailable = e => {
            log("ondataavailable: " + e.data.type + " size=" + e.data.size, "CLIENT");
            if (e.data && e.data.size > 0) chunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            log("onstop called! Chunks: " + chunks.length, "CLIENT");
            clearTimeout(recordTimeout);
            if (!chunks.length) {
                log("❌ No audio recorded on mobile. Try another browser or device.", "ERROR");
                return;
            }
            if (engine === "whisper") {
                try {
                    await recordAndSend("/api/whisper_speech_to_text", lang);
                } catch (err) {
                    log("Whisper error: " + err, "ERROR");
                }
            } else if (engine === "google" || engine === "vosk") {
                try {
                    await recordAndSend("/api/extract", lang);
                } catch (err) {
                    log("recordAndSend error: " + err, "ERROR");
                }
            }
        };

        mediaRecorder.start();
        micBtn.textContent = "⏹️ Stop";
        isRecording = true;

        recordTimeout = setTimeout(() => {
            if (isRecording) {
                mediaRecorder.stop();
                micBtn.textContent = "🎤";
                isRecording = false;
                log("⏹️ Auto-stopped after timeout", "CLIENT");
            }
        }, 60000);

    } else {
        mediaRecorder.stop();
        micBtn.textContent = "🎤";
        isRecording = false;
    }
}

micBtn.onclick = () => {
    const engine = engineSelect.value;
    const lang = langSelect.value;

    if (engine === "webspeech") {
        startWebSpeech(lang);
    } else {
        handleMediaRecorder(engine, lang);
    }
};

clearBtn.onclick = () => {
    mainInput.value = "";
    mainInput.focus();
    log("Input cleared", "CLIENT");
};
