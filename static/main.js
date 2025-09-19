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

        console.log("📤 Sending body:", body);

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
            // 👇 نمایش نتیجه در UI
            document.getElementById("result").textContent =
                JSON.stringify(data, null, 2);
            document.getElementById("outputArea").style.display = "block";
        } catch (err) {
            // 👇 حتی اگر fetch شکست بخوره، خطا در UI نمایش داده میشه
            document.getElementById("result").textContent =
                "⚠️ Error: " + err.message;
            document.getElementById("outputArea").style.display = "block";
            console.error("Extract error:", err);
        }
    });


    const micBtn = document.getElementById('micBtn');
    const mainInput = document.getElementById('mainInput');
    const engineSelect = document.getElementById('voiceEngine');
    const langSelect = document.getElementById('langSelect');
    const clearBtn = document.getElementById('clearBtn');

    // 🎯 وضعیت MediaRecorder
    let isRecording = false;
    let mediaRecorder;
    let chunks = [];
    let recordTimeout;

    // ---------- WebSpeech API ----------
    function startWebSpeech(lang) {
        if (!("webkitSpeechRecognition" in window)) {
            alert("Your browser does not support Web Speech API.");
            return;
        }

        const rec = new webkitSpeechRecognition();
        rec.lang = lang;
        rec.interimResults = true;   // نتایج لحظه‌ای
        rec.maxAlternatives = 1;
        rec.continuous = true;       // 🟢 مداوم

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
            console.warn("❌ Speech error:", err);
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
        const arrayBuffer = await blob.arrayBuffer();
        const audioCtx = new AudioContext();
        const decoded = await audioCtx.decodeAudioData(arrayBuffer);

        const wavBuffer = audioBufferToWav(decoded);
        const wavBlob = new Blob([wavBuffer], { type: "audio/wav" });

        const formData = new FormData();
        formData.append("file", wavBlob, "audio.wav");
        formData.append("lang", langCode);

        try {
            const r = await fetch(endpoint, { method: "POST", body: formData });
            const data = await r.json();

            if (data.title) {
                mainInput.value = `${data.title} ${data.date} ${data.time} ${data.location}`;
                document.getElementById('result').textContent = JSON.stringify(data, null, 2);
                showOutput(data);
            } else if (data.text) {
                mainInput.value = data.text;
                document.getElementById('result').textContent = data.text;
                document.getElementById("outputArea").style.display = "none";
            } else {
                mainInput.value = "";
            }

        } catch (err) {
            alert("Error sending audio: " + err);
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
            mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
            chunks = [];

            mediaRecorder.ondataavailable = e => chunks.push(e.data);
            mediaRecorder.onstop = async () => {
                clearTimeout(recordTimeout);
                if (engine === "google" || engine === "vosk" || engine === "whisper") {
                    await recordAndSend("https://common-junglefowl-neoprojects-82c5720a.koyeb.app/api/extract", lang);
                }
            };

            // اگر روی VPS اجرا شدی این خط رو جایگزین کن:
            // await recordAndSend("https://your-domain.com/api/voice_event", lang);

            mediaRecorder.start();
            micBtn.textContent = "⏹️ Stop";
            isRecording = true;

            recordTimeout = setTimeout(() => {
                if (isRecording) {
                    mediaRecorder.stop();
                    micBtn.textContent = "🎤";
                    isRecording = false;
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
    };

});
