import os
import json
import requests
from flask import Flask, request, jsonify, render_template, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app, resources={
    r"/*": {
        "origins": "https://shared-deborah-neoprojects-65e1dc36.koyeb.app"
    }
})

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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
    prompts = list(PROMPT_TYPES.keys())
    if not prompts:  # اگه خالی شد، پیش‌فرض بده
        prompts = ["calendar_event", "task_list", "trading_signal"]
    return jsonify({"prompts": prompts})

PROMPT_VARS = {
    "calendar_event": ["title", "date", "time", "reminder"],
    "task_list": ["tasks"],
    "trading_signal": ["symbol", "action", "price"]
}

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
    # فقط مدل‌های active
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
            "https://openrouter.ai/api/v1/chat/completions",  # اینجا آدرس OpenRouter یا سرور خودت را بگذار
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
    data = request.json or {}
    model = data.get("model")
    user_input = data.get("input", "")
    prompt_type = data.get("prompt_type", "calendar_event")
    lang = data.get("lang", "en-US")

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    today_str = datetime.now().strftime("%Y-%m-%d")
    final_prompt = f"""
Extract structured {prompt_type} information from the following text.
Always return valid JSON.
Convert relative dates to absolute (today is {today_str}).
Input: {user_input}
"""

    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": final_prompt}
            ]
        }
        # ارسال به API داخلی بجای OpenRouter مستقیم
        resp = requests.post(
            "http://127.0.0.1:8000/api/complete",  # یا اگر در سرور هستی، آدرس لوکال سرور خودت را بگذار
            json=payload,
            timeout=60
        )
        raw = resp.json()
        print("🤖 Raw Model Response:", raw)
        ai_text = None
        if isinstance(raw, dict):
            ai_text = raw.get("output") or raw.get("content")
            if not ai_text and "choices" in raw:
                ai_text = raw["choices"][0]["message"]["content"]
        if not ai_text:
            return jsonify({"error": "No content in response", "raw": raw}), 500
        clean = ai_text.replace("```json", "").replace("```", "").strip()
        try:
            parsed = json.loads(clean)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
        except Exception as e:
            app.logger.error(f"❌ JSON Parse Error: {e}")
            app.logger.error(f"📝 Clean string was:\n{clean}")
            return jsonify({"error": f"JSON parse failed: {e}", "raw": clean}), 500
        return jsonify({
            "model": model,
            "prompt_type": prompt_type,
            "input": user_input,
            "lang": lang,
            "output": parsed,
            "raw": raw
        })
    except Exception as e:
        app.logger.error(f"🔥 Unexpected extract error: {e}")
        return jsonify({"error": f"extract failed: {e}"}), 500

# ================ RUN APP ================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
