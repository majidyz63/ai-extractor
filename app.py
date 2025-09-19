import os
import json
import requests
from flask import Flask, request, jsonify, render_template
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

@app.route("/api/models")
def get_models():
    try:
        resp = requests.get(
            "https://common-junglefowl-neoprojects-82c5720a.koyeb.app/api/active-models",
            timeout=10
        )
        models = resp.json()
        # اگه API بیرونی خالی داد یا خراب بود → fallback
        if not models or not isinstance(models, list):
            models = ["mistral/mistral-7b-instruct:free", "meta-llama/llama-3.1-8b-instruct"]
        return jsonify({"models": models})
    except Exception as e:
        return jsonify({
            "error": f"failed to fetch models: {e}",
            "models": ["mistral/mistral-7b-instruct:free", "meta-llama/llama-3.1-8b-instruct"]
        })


# ---------- Prompts ----------
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


# ---------- Prompt Variables ----------
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


# ---------- Utilities ----------
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

# ---------- Serve UI ----------
@app.route("/")
def serve_ui():
    return render_template("index.html")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))  # پورت رو از Koyeb بگیره
    app.run(host="0.0.0.0", port=port, debug=False)

@app.route("/api/extract", methods=["POST"])
def extract_debug():
    try:
        data = request.json or {}
        model = data.get("model")
        prompt_type = data.get("prompt_type")
        user_input = data.get("input")
        lang = data.get("lang", "en-US")

        # بررسی ورودی‌ها
        if not model:
            return jsonify({"error": "❌ No model provided"}), 400
        if not prompt_type:
            return jsonify({"error": "❌ No prompt_type provided"}), 400
        if not user_input:
            return jsonify({"error": "❌ No input text provided"}), 400

        # ساخت prompt
        final_prompt = f"""
        Extract structured {prompt_type} information from the following text.
        Always return valid JSON.
        Input: {user_input}
        """

        # صدا زدن OpenRouter API
        headers = {
            "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": final_prompt}
            ]
        }

        resp = requests.post(
            os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions"),
            headers=headers,
            json=payload,
            timeout=60
        )

        raw = resp.json()
        print("🤖 Raw Model Response:", raw)

        ai_text = None
        if "choices" in raw and raw["choices"]:
            ai_text = raw["choices"][0]["message"]["content"]

        return jsonify({
            "model": model,
            "prompt_type": prompt_type,
            "input": user_input,
            "lang": lang,
            "raw": raw,
            "output": ai_text
        })

    except Exception as e:
        return jsonify({"error": f"⚠️ AI call failed: {str(e)}"}), 500
