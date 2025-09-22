import os
import json
import requests
from flask import Flask, request, jsonify, render_template, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime
from utils.prompt_engine import build_prompt_from_yaml
from openai import OpenAI

load_dotenv()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))  # Whisper: فقط یکبار ساخته شود

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "https://shared-deborah-neoprojects-65e1dc36.koyeb.app"
    }
})

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
PROMPT_MAP = {
    "en-US": "calendar_en.yaml",
    "fa-IR": "calendar_fa.yaml",
    "nl-NL": "calendar_nl.yaml",
    "fr-FR": "calendar_fr.yaml"
}
DEFAULT_PROMPT_FILE = "calendar_nl.yaml"  # پیش‌فرض هلندی

# ============= MAIN EXTRACTOR ROUTES (دست نخورده) =============
@app.route("/api/models")
def get_models():
    MODELS_FILE = "models.json"
    import os, json
    if not os.path.exists(MODELS_FILE):
        return jsonify({"models": []})
    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        try:
            models = json.load(f)
            if isinstance(models, list):
                active_models = [m["model"] for m in models if m.get("active")]
                return jsonify({"models": active_models})
        except Exception as e:
            return jsonify({"error": f"failed to parse models.json: {e}", "models": []})
    return jsonify({"models": []})


PROMPT_TYPES = {
    "calendar_event": "Extract calendar event details",
    "task_list": "Extract tasks from text",
    "trading_signal": "Extract trading signals"
}

@app.route("/api/prompts")
def get_prompts():
    try:
        prompt_files = [
            f for f in os.listdir("prompts")
            if f.endswith(".yaml") or f.endswith(".yml")
        ]
        # فقط اسم بدون پسوند رو برگردون
        prompt_names = [os.path.splitext(f)[0] for f in prompt_files]
        return jsonify({"prompts": prompt_names})
    except Exception as e:
        return jsonify({"error": str(e), "prompts": []}), 500

@app.route("/api/prompt_vars", methods=["GET", "POST"])
def get_prompt_vars():
    if request.method == "GET":
        name = request.args.get("name")
    else:
        data = request.json or {}
        name = data.get("name")

    if name in PROMPT_VARS:
        return jsonify({"vars": PROMPT_VARS[name]})
    return jsonify({"vars": []})

def normalize_reminder(rem):
    if not rem:
        return 0
    if isinstance(rem, int):
        return rem
    s = str(rem).lower().strip()
    if s.endswith("m"):
        return int(s[:-1]) or 0
    if s.endswith("h"):
        return (int(s[:-1]) or 0) * 60
    if s.endswith("d"):
        return (int(s[:-1]) or 0) * 1440
    try:
        return int(s)
    except:
        return 0

@app.route("/")
def serve_ui():
    return render_template("index.html")

# ==================  🟢 مدل منیجر (API Model Manager) =====================

MODELS_FILE = "models.json"

def read_models():
    if not os.path.exists(MODELS_FILE):
        with open(MODELS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        try:
            models = json.load(f)
            if isinstance(models, list):
                return models
            return []
        except:
            return []

def write_models(models):
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(models, f, ensure_ascii=False, indent=2)

@app.route("/manager")
def manager_ui():
    models = read_models()
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>API Model Manager</title>
        <style>
            body { font-family: sans-serif; background: #f7f7f7; margin: 0; padding: 0;}
            .container { max-width: 450px; margin:40px auto; background:white; border-radius:12px; box-shadow:0 1px 6px #0001; padding:20px;}
            h2 {margin-top:0;}
            input,button { padding:8px; margin:5px 0;}
            .model {display:flex;align-items:center;justify-content:space-between;padding:7px 0;border-bottom:1px solid #eee;}
            .model:last-child{border-bottom:0;}
            .model span{flex:1;}
            .btn {margin-left:6px;padding:4px 12px;border-radius:5px;}
            .active{color:#009688;font-weight:bold;}
        </style>
    </head>
    <body>
    <div class="container">
        <h2>API Model Manager</h2>
        <a href="https://openrouter.ai/models" target="_blank" style="display:inline-block;margin-bottom:16px;padding:6px 14px;border-radius:6px;background:#2269d6;color:#fff;text-decoration:none;font-size:.96em;">🌐 OpenRouter Models</a>                
        <form id="addForm">
            <input type="text" id="model" placeholder="model/name:version" required>
            <button type="submit" class="btn">Add</button>
        </form>
        <div id="models"></div>
    </div>
    <script>
    function render(models) {
        const root = document.getElementById("models");
        if (!models.length) { root.innerHTML = "<i>No models yet.</i>"; return; }
        root.innerHTML = models.map((m,i) => `
        <div class="model">
            <span class="${m.active?'active':''}">${m.model}</span>
            <button onclick="toggleModel(${i})" class="btn">${m.active ? "Deactivate" : "Activate"}</button>
            <button onclick="deleteModel(${i})" class="btn" style="color:#d32f2f;">Delete</button>
        </div>
        `).join("");
    }
    function fetchModels() {
        fetch("/api/active-models?all=1").then(r=>r.json()).then(res=>render(res.models||[]));
    }
    function toggleModel(idx) {
        fetch("/toggle", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({idx})}).then(fetchModels);
    }
    function deleteModel(idx) {
        fetch("/delete", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({idx})}).then(fetchModels);
    }
    document.getElementById("addForm").onsubmit = e => {
        e.preventDefault();
        fetch("/add", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({model:document.getElementById("model").value})}).then(fetchModels);
        document.getElementById("model").value = "";
    };
    fetchModels();
    </script>
    </body>
    </html>
    """, models=models)

@app.route("/api/active-models")
def api_active_models():
    all_flag = request.args.get("all")
    models = read_models()
    if all_flag:
        return jsonify({"models": models})
    actives = [m["model"] for m in models if m.get("active")]
    return jsonify({"models": actives})

@app.route("/add", methods=["POST"])
def add_model():
    data = request.json or {}
    model = (data.get("model") or "").strip()
    if not model:
        return jsonify({"error":"Model required"}),400
    models = read_models()
    for m in models:
        if m["model"] == model:
            m["active"] = True
            write_models(models)
            return jsonify({"status":"✅ Model added/updated"})
    models.append({"model":model,"active":True})
    write_models(models)
    return jsonify({"status":"✅ Model added"})

@app.route("/toggle", methods=["POST"])
def toggle_model():
    data = request.json or {}
    idx = data.get("idx")
    models = read_models()
    if idx is None or not (0 <= idx < len(models)):
        return jsonify({"error":"Invalid index"}),400
    models[idx]["active"] = not models[idx].get("active",True)
    write_models(models)
    return jsonify({"status":"toggled"})

@app.route("/delete", methods=["POST"])
def delete_model():
    data = request.json or {}
    idx = data.get("idx")
    models = read_models()
    if idx is None or not (0 <= idx < len(models)):
        return jsonify({"error":"Invalid index"}),400
    models.pop(idx)
    write_models(models)
    return jsonify({"status":"deleted"})

@app.route("/api/complete", methods=["POST"])
def api_complete():
    data = request.json or {}
    model = data.get("model")
    messages = data.get("messages", [])
    if not model or not messages:
        return jsonify({"error":"Model & messages required"}),400
    try:
        payload = {
            "model": model,
            "messages": messages
        }
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY','sk-...')}"
            },
            json=payload, timeout=60
        )
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error":f"complete failed: {e}"}),500

# =============== تغییر کوچک در /api/extract (فقط فوروارد) ==============
@app.route("/api/extract", methods=["POST"])
def extract():
    try:
        data = request.get_json(force=True) or {}
        model = data.get("model")
        user_input = data.get("input", "")
        lang = data.get("lang", "nl-NL")
        prompt_type = data.get("prompt_type", "calendar_event")

        if not user_input:
            return jsonify({"error": "No input provided"}), 400

        prompt_file = PROMPT_MAP.get(lang, DEFAULT_PROMPT_FILE)
        prompt_path = os.path.join("prompts", prompt_file)
        today_str = datetime.now().strftime("%Y-%m-%d")
        user_vars = {"input": user_input}
        sys_vars = {"today": today_str}

        final_prompt = build_prompt_from_yaml(prompt_path, user_vars, sys_vars)

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": final_prompt}
            ]
        }

        # تنظیم کلید OpenRouter خودت!
        OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
        HEADERS = {
            "Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}",
            "Content-Type": "application/json"
        }

        resp = requests.post(OPENROUTER_API_URL, headers=HEADERS, json=payload, timeout=40)
        if resp.status_code != 200:
            return jsonify({"error": f"OpenRouter error {resp.status_code}", "details": resp.text}), 500

        ai_result = resp.json()
        output_text = ai_result["choices"][0]["message"]["content"]

        # تلاش برای تبدیل به JSON
        output_json = None
        try:
            if output_text.strip().startswith("```"):
                output_text = output_text.split("```")[1]
            output_json = json.loads(output_text)
        except Exception as e:
            return jsonify({
                "error": f"JSON parse failed: {e}",
                "raw": output_text
            }), 500

        return jsonify({
            "model": model,
            "lang": lang,
            "input": user_input,
            "output": output_json,
            "prompt_type": prompt_type,
            "raw": ai_result
        })

    except Exception as e:
        return jsonify({"error": f"Server error: {e}"}), 500
   
# ---------------- Whisper Speech-to-Text ---------------- #
@app.route("/api/whisper_speech_to_text", methods=["POST"])
def whisper_speech_to_text():
    try:
        if "file" not in request.files:
            return jsonify({"error": "❌ No file uploaded"}), 400

        audio_file = request.files["file"]
        lang = request.form.get("lang", "en")

        # ذخیره موقت فایل برای سازگاری با OpenAI
        temp_path = os.path.join(UPLOAD_FOLDER, "temp.wav")
        audio_file.save(temp_path)

        with open(temp_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language=lang
            )

        return jsonify({
            "text": transcript.text,
            "lang": lang
        })
    except Exception as e:
        print("❌ Whisper error:", e)
        return jsonify({"error": str(e)}), 500

# ================ RUN APP ================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
