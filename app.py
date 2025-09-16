import os
import json
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ---------- Models ----------
@app.route("/api/models")
def get_models():
    try:
        resp = requests.get("http://127.0.0.1:8000/api/active-models", timeout=10)
        return jsonify(resp.json())
    except Exception as e:
        return jsonify({"error": f"failed to fetch models: {e}", "models": []})


# ---------- Prompts ----------
PROMPT_TYPES = {
    "calendar_event": "Extract calendar event details",
    "task_list": "Extract tasks from text",
    "trading_signal": "Extract trading signals"
}

@app.route("/api/prompts")
def get_prompts():
    return jsonify({"prompts": list(PROMPT_TYPES.keys())})


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


# ---------- Text Extraction ----------
@app.route("/api/extract", methods=["POST"])
def extract():
    data = request.json or {}
    model = data.get("model")
    user_input = data.get("input", "")

    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    today_str = datetime.now().strftime("%Y-%m-%d")

    final_prompt = f"""
Extract structured calendar event information from the following text.
Always return valid JSON with keys:
title, date (YYYY-MM-DD), time (HH:MM, 24h), location, notes, reminder (minutes).
Convert relative dates to absolute (today is {today_str}).
Input: {user_input}
"""

    print("Raw UI Request:", data)
    print("📝 Final Prompt Sent:\n", final_prompt)

    try:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": final_prompt}
            ]
        }

        resp = requests.post(
            "http://127.0.0.1:8000/api/complete",
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

        clean = ai_text.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        try:
            parsed = json.loads(clean)
            if isinstance(parsed, str):
                parsed = json.loads(parsed)
        except Exception as e:
            return jsonify({"error": f"JSON parse failed: {e}", "raw": clean}), 500

        normalized = {
            "title": parsed.get("title") or "Untitled Event",
            "date": parsed.get("date") or today_str,
            "time": parsed.get("time") or "00:00",
            "location": parsed.get("location", ""),
            "notes": parsed.get("notes", ""),
            "reminder": int(parsed.get("reminder", 0)),
        }
        normalized["datetime"] = f"{normalized['date']}T{normalized['time']}"
        normalized["id"] = int(datetime.now().timestamp() * 1000)

        print("✅ Final Normalized Event:", normalized)
        return jsonify(normalized)

    except Exception as e:
        return jsonify({"error": f"extract failed: {e}"}), 500


# ---------- Serve UI ----------
@app.route("/")
def serve_ui():
    return render_template("index.html")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))  # پورت رو از Koyeb بگیره
    app.run(host="0.0.0.0", port=port, debug=False)

