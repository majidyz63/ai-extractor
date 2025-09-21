async function fetchModels() {
    const r = await fetch('/api/models');
    const data = await r.json();
    const sel = document.getElementById('modelSelect');
    sel.innerHTML = '';
    data.models.forEach(m => sel.innerHTML += `<option>${m}</option>`);
}

async function fetchPrompts() {
    const r = await fetch('/api/prompts');
    const data = await r.json();
    const sel = document.getElementById('promptSelect');
    sel.innerHTML = '';
    data.prompts.forEach(p => sel.innerHTML += `<option>${p}</option>`);
    sel.dispatchEvent(new Event("change"));
}

async function fetchPromptVars(promptType) {
    const r = await fetch('/api/prompt_vars', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: promptType })
    });
    const data = await r.json();
    return data.vars || [];
}

async function renderDynamicFields() {
    const promptType = document.getElementById('promptSelect').value;
    const fields = await fetchPromptVars(promptType);
    const div = document.getElementById('dynamicFields');
    div.innerHTML = '';
    fields.forEach(f => {
        if (f === "today" || f === "input") return;
        div.innerHTML += `<label>${f}:<input name="${f}" /></label>`;
    });
}

// ---------------- لاگ دسته‌بندی‌شده ----------------
function log(msg, category = "CLIENT") {
    const debugBox = document.getElementById("debug");
    const now = new Date();
    const pad = n => n.toString().padStart(2, '0');
    const timestamp = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
    const cat = category.toUpperCase();
    const line = `[${timestamp}] [${cat}] ${msg}`;
    if (debugBox) {
        debugBox.textContent += line + "\n";
        debugBox.scrollTop = debugBox.scrollHeight;
    }
    if (cat === "ERROR") {
        console.error(line);
    } else if (cat === "SERVER") {
        console.warn(line);
    } else {
        console.log(line);
    }
}

function renderExtractorOutput(data) {
    let ce = data.output?.calendar_event;
    log("OUTPUT: " + JSON.stringify(ce), "SERVER");
    let message = "";
    if (!ce) {
        document.getElementById('result').innerHTML =
            "<span style='color:#d00'>❌ خروجی استخراج یافت نشد.</span>";
        return;
    }
    let missing = [];
    if (!ce.summary) missing.push("عنوان");
    if (!ce.start?.date) missing.push("تاریخ شروع");
    if (!ce.start?.time) missing.push("ساعت شروع");
    if (!ce.end?.date) missing.push("تاریخ پایان");
    if (!ce.end?.time) missing.push("ساعت پایان");
    if (!ce.location) missing.push("مکان");

    if (missing.length > 0) {
        message += `<div style="color:#b63;background:#fff4e6;border-radius:6px;padding:8px 10px;margin-bottom:7px;">
        ⚠️ بعضی قسمت‌ها ناقصند: <b>${missing.join("، ")}</b><br>
        لطفاً جمله را دقیق‌تر وارد کنید یا مقدار را دستی کامل نمایید.
        </div>`;
    }

    let lang = document.getElementById("langSelect").value;
    let rangeWord = "to";
    if (lang === "fa-IR") rangeWord = "تا";
    else if (lang === "nl-NL") rangeWord = "tot";
    else if (lang === "fr-FR") rangeWord = "à";

    let timeLine = "";
    if (ce.start?.date && ce.end?.date && ce.start.date === ce.end.date) {
        timeLine = `${ce.start.date} ${ce.start.time || ""} ${rangeWord} ${ce.end.time || ""}`;
    } else {
        timeLine = `${ce.start?.date || ""} ${ce.start?.time || ""} ${rangeWord} ${ce.end?.date || ""} ${ce.end?.time || ""}`;
    }

    message += `<div style="border:1px solid #d0d0d0;border-radius:8px;padding:10px;line-height:2;">
        <b>📄 ${ce.summary || "<i>بدون عنوان</i>"}</b><br>
        📅 ${timeLine} <br>
        📍 ${ce.location || "<i>بدون مکان</i>"}
    </div>`;

    document.getElementById('result').innerHTML = message;
}

function showOutput(json) {
    const outputArea = document.getElementById("outputArea");
    const outputForm = document.getElementById("outputForm");
    outputArea.style.display = "block";
    outputForm.innerHTML = "";
    Object.entries(json).forEach(([k, v]) => {
        outputForm.innerHTML += `<label>${k}<input name="${k}" value="${v ?? ""}"></label>`;
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    await fetchModels();
    await fetchPrompts();
    await renderDynamicFields();
    document.getElementById('promptSelect').onchange = renderDynamicFields;

    document.getElementById("extractForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const body = {
            model: document.getElementById("modelSelect").value,
            prompt_type: document.getElementById("promptSelect").value,
            input: document.getElementById("mainInput").value,
            lang: document.getElementById("langSelect").value
        };

        log("📤 Sending body: " + JSON.stringify(body), "CLIENT");

        try {
            const r = await fetch("/api/extract", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body)
            });

            if (!r.ok) {
                throw new Error(`❌ Server error: ${r.status}`);
            }

            const data = await r.json();
            renderExtractorOutput(data);
        } catch (err) {
            document.getElementById("result").textContent =
                "⚠️ Error: " + err.message;
            log("Extract error: " + err, "ERROR");
        }
    });

    const micBtn = document.getElementById('micBtn');
    const mainInput = document.getElementById('mainInput');
    const engineSelect = document.getElementById('voiceEngine');
    const langSelect = document.getElementById('langSelect');
    const clearBtn = document.getElementById('clearBtn');

    let isRecording = false;
    let mediaRecorder;
    let chunks = [];
    let recordTimeout;

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

        // دسته‌بندی زبان برای Whisper
        function mapLangCode(lang) {
            if (lang.startsWith("fa")) return "fa";
            if (lang.startsWith("en")) return "en";
            if (lang.startsWith("nl")) return "nl";
            if (lang.startsWith("fr")) return "fr";
            return "en";
        }

        const formData = new FormData();
        formData.append("file", wavBlob, "audio.wav");
        formData.append("lang", mapLangCode(langCode));

        try {
            const r = await fetch(endpoint, { method: "POST", body: formData });
            const data = await r.json();
            log("SERVER RESPONSE: " + JSON.stringify(data), "SERVER");

            if (data.title) {
                mainInput.value = `${data.title} ${data.date} ${data.time} ${data.location}`;
                renderExtractorOutput(data);
                showOutput(data);
            } else if (data.text) {
                mainInput.value = data.text;
                document.getElementById('result').textContent = data.text;
                document.getElementById("outputArea").style.display = "none";
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
});
