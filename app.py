import os
import re
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ---------------- Settings ----------------
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

MODELS_FILE = "models.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


# ---------------- Helpers ----------------
def load_config():
    if not os.path.exists(MODELS_FILE):
        return {}
    with open(MODELS_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}


def save_config(config):
    with open(MODELS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def safe_json_parse(ai_text: str):
    """پاکسازی و parse امن خروجی مدل AI حتی وقتی JSON وسط متن باشه"""
    clean = ai_text.strip()

    if clean.startswith("```"):
        parts = clean.split("```")
        if len(parts) > 1:
            clean = parts[1].strip()

    if clean.lower().startswith("json"):
        clean = clean[4:].strip()

    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if match:
        clean = match.group(0).strip()

    try:
        parsed = json.loads(clean)
        if isinstance(parsed, str):
            parsed = json.loads(parsed)
        return parsed
    except Exception as e:
        app.logger.error(f"❌ JSON Parse Error: {e}")
        app.logger.error(f"📝 Clean string was:\n{clean}")
        return {"raw_text": clean}


# ---------------- Manager UI ----------------
@app.route("/")
def home():
    config = load_config()
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>AI Extractor Model Manager</title>
        <style>
            body {
                font-family: sans-serif;
                background: #f3f3f3;
                padding: 20px;
            }
            .container {
                max-width: 700px;
                margin: auto;
                background: white;
                padding: 20px;
                border-radius: 10px;
            }
            h2 {
                margin-bottom: 15px;
            }
            form {
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-bottom: 20px;
            }
            input[type="text"] {
                flex: 1;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 6px;
            }
            button {
                padding: 10px 16px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-weight: bold;
            }
            button.add {
                background: #007bff;
                color: white;
            }
            button.add:hover {
                background: #0056b3;
            }
            .model {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 0;
                border-bottom: 1px solid #ddd;
            }
            .model span {
                flex: 1;
            }
            .actions {
                display: flex;
                gap: 8px;
            }
            .btn {
                padding: 6px 12px;
                border-radius: 6px;
                border: none;
                cursor: pointer;
                font-size: 14px;
            }
            .btn-toggle {
                background: #ffc107;
                color: black;
            }
            .btn-toggle:hover {
                background: #e0a800;
            }
            .btn-delete {
                background: #dc3545;
                color: white;
            }
            .btn-delete:hover {
                background: #a71d2a;
            }
            @media (max-width: 600px) {
                .model {
                    flex-direction: column;
                    align-items: flex-start;
                }
                .actions {
                    margin-top: 10px;
                    width: 100%;
                    justify-content: flex-start;
                    flex-wrap: wrap;
                    gap: 6px;
                }
                .btn {
                    flex: 1 1 calc(50% - 6px);
                    min-width: 120px;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h2>⚙️ AI Extractor Model Manager</h2>
            <form method="POST" action="/add">
                <input type="text" name="model" placeholder="e.g. mistral/mistral-7b-instruct:free" required>
                <label><input type="checkbox" name="active"> Active</label>
                <button type="submit" class="add">➕ Add / Update</button>
            </form>
            <hr>
            {% for name, info in config.items() %}
              <div class="model">
                <span>{{name}} — {{ "✅ Active" if info.active else "❌ Inactive" }}</span>
                <div class="actions">
                  <a href="/toggle?model={{name}}"><button type="button" class="btn btn-toggle">🔄 Toggle</button></a>
                  <a href="/delete?model={{name}}"><button type="button" class="btn btn-delete">🗑 Delete</button></a>
                </div>
              </div>
            {% endfor %}
        </div>
    </body>
    </html>
    """
    return render_template_string(html, config=config)


# ---------------- Manager APIs ----------------
@app.route("/api/active-models")
def active_models():
    config = load_config()
    return jsonify([m for m, info in config.items() if info.get("active")])


@app.route("/api/complete", methods=["POST"])
def complete():
    data = request.json or {}
    model = data.get("model")
    messages = data.get("messages", [])

    config = load_config()
    if model not in config or not config[model].get("active", False):
        return jsonify({"error": "❌ Model not active or not found"}), 400

    if not OPENROUTER_API_KEY:
        return jsonify({"error": "❌ No OPENROUTER_API_KEY set"}), 500

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "AI Extractor Manager"
            },
            json={"model": model, "messages": messages},
            timeout=30
        )
        raw = resp.json()

        output = None
        if isinstance(raw, dict):
            if "choices" in raw and raw["choices"]:
                output = raw["choices"][0]["message"]["content"]
            elif "error" in raw:
                output = f"❌ Error: {raw['error']}"
            else:
                output = str(raw)

        return jsonify({
            "model": model,
            "output": output or "⚠️ No content returned from model",
            "raw": raw
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/add", methods=["POST"])
def add_model():
    model = request.form.get("model")
    active = "active" in request.form
    config = load_config()
    config[model] = {"active": active}
    save_config(config)
    return "✅ Model added/updated. <a href='/'>Back</a>"


@app.route("/delete")
def delete_model():
    model = request.args.get("model")
    config = load_config()
    if model in config:
        del config[model]
        save_config(config)
    return "🗑 Deleted. <a href='/'>Back</a>"


@app.route("/toggle")
def toggle_model():
    model = request.args.get("model")
    config = load_config()
    if model in config:
        config[model]["active"] = not config[model].get("active", False)
        save_config(config)
    return "🔄 Toggled. <a href='/'>Back</a>"


# ---------------- Extractor API ----------------
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

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": final_prompt}
        ]
    }

    try:
        resp = requests.post(
           request.host_url.rstrip("/") + "/api/complete",
           json=payload,
           timeout=60
        )
        raw = resp.json()

        ai_text = None 
        if isinstance(raw, dict):
            ai_text = raw.get("output") or raw.get("content")
            if not ai_text and "choices" in raw:
                ai_text = raw["choices"][0]["message"]["content"]

        if not ai_text:
            return jsonify({"error": "No content in response", "raw": raw}), 200

        parsed = safe_json_parse(ai_text)

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
        return jsonify({"error": f"extract failed: {e}"}), 200


# ---------------- Run ----------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=False)
