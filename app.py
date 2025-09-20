import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template, render_template_string
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ---------------- AI Extractor (نسخه اصلی سالم) ---------------- #

@app.route("/")
def index():
    return render_template("index.html")

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

        complete_url = request.host_url.rstrip("/") + "/api/complete"
        resp = requests.post(
            complete_url,
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


# ---------------- API Model Manager ---------------- #

CONFIG_FILE = "models.json"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)

@app.route("/api/active-models")
def get_active_models():
    cfg = load_config()
    active = [m for m, v in cfg.items() if v.get("active")]
    return jsonify(active)

@app.route("/api/complete", methods=["POST"])
def complete():
    data = request.json
    model = data.get("model")
    messages = data.get("messages", [])

    cfg = load_config()
    if model not in cfg or not cfg[model].get("active", False):
        return jsonify({"error": "❌ Model not active or not found"}), 400

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        return jsonify({"error": "❌ No OPENROUTER_API_KEY set"}), 500

    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
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

# ---------------- Manager UI ---------------- #

@app.route("/manager")
def manager_ui():
    return render_template_string("""
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>مدیریت مدل‌ها</title>
  <style>
    body { font-family: sans-serif; background:#f3f3f3; padding:20px; }
    .container { max-width:600px; margin:auto; background:#fff; padding:20px; border-radius:10px; }
    input, button { width:100%; margin-top:10px; padding:10px; }
    .model { display:flex; justify-content:space-between; align-items:center; padding:8px 0; border-bottom:1px solid #ddd; }
    .actions { display:flex; gap:10px; }
    .btn { padding:5px 10px; border:none; cursor:pointer; border-radius:5px; }
    .btn-test { background:#007bff; color:#fff; }
    .btn-toggle { background:#ffc107; }
    .btn-delete { background:#dc3545; color:#fff; }
  </style>
</head>
<body>
  <div class="container">
    <h2>⚙️ مدیریت مدل‌ها</h2>
    <form method="POST" action="/add">
      <input type="text" name="model" placeholder="مثال: mistral/mistral-7b-instruct:free" required />
      <label><input type="checkbox" name="active"> فعال</label>
      <button type="submit">➕ افزودن/بروزرسانی</button>
    </form>
    <hr/>
    {% for m, v in models.items() %}
      <div class="model">
        <span>{{m}} {% if v.active %}✅{% else %}❌{% endif %}</span>
        <div class="actions">
          <a href="/toggle?model={{m}}" class="btn btn-toggle">🔄 تغییر وضعیت</a>
          <a href="/delete?model={{m}}" class="btn btn-delete">🗑 حذف</a>
        </div>
      </div>
    {% endfor %}
  </div>
</body>
</html>
    """, models=load_config())

@app.route("/add", methods=["POST"])
def add_model():
    m = request.form.get("model")
    active = "active" in request.form
    cfg = load_config()
    cfg[m] = {"active": active}
    save_config(cfg)
    return jsonify({"status": "✅ Model added/updated", "model": m, "active": active})

@app.route("/toggle")
def toggle_model():
    m = request.args.get("model")
    cfg = load_config()
    if m in cfg:
        cfg[m]["active"] = not cfg[m].get("active", False)
        save_config(cfg)
    return jsonify({"status": "toggled", "model": m, "active": cfg.get(m, {}).get("active")})

@app.route("/delete")
def delete_model():
    m = request.args.get("model")
    cfg = load_config()
    if m in cfg:
        del cfg[m]
        save_config(cfg)
    return jsonify({"status": "deleted", "model": m})

# ---------------- Run ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
