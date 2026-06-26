from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import os
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Models in priority order - fallback if one hits quota
MODELS = [
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash-8b",
    "gemini-1.5-flash",
]

SYSTEM_PROMPT = """You are VEGA, a sharp bilingual (English/Spanish) AI assistant created by Anas Tahir.
- Be concise, direct, intelligent. Max 3 sentences unless asked for more.
- Reply in the SAME language the user writes/speaks in (EN or ES)
- Tool results injected as [TOOL]: — use them naturally
- You are VEGA — sharp, helpful, occasionally witty."""

conversation_history = {}

def gemini_chat(messages, system, retry=3):
    headers = {"Content-Type": "application/json"}
    payload = {
        "system_instruction": {"parts": [{"text": system}]},
        "contents": messages,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 512}
    }
    for model in MODELS:
        for attempt in range(retry):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
                r = requests.post(url, json=payload, headers=headers, timeout=20)
                data = r.json()
                if "candidates" in data:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                err = data.get("error", {})
                if err.get("code") == 429:
                    wait = 2 ** attempt
                    time.sleep(wait)
                    continue
                return f"Error: {err.get('message', 'Unknown')}"
            except Exception as e:
                if attempt < retry - 1:
                    time.sleep(1)
                continue
    return "I'm temporarily at capacity. Please try again in a moment."

def get_weather(city):
    try:
        if not WEATHER_API_KEY:
            return f"Weather API not configured for {city}"
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
        r = requests.get(url, timeout=5)
        d = r.json()
        if d.get("cod") == 200:
            return f"{city}: {d['main']['temp']}°C, {d['weather'][0]['description']}, humidity {d['main']['humidity']}%"
        return f"Could not get weather for {city}"
    except Exception as e:
        return f"Weather error: {e}"

def get_github(username="anas-tahi"):
    try:
        headers = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
        r = requests.get(f"https://api.github.com/users/{username}/events?per_page=10", headers=headers, timeout=5)
        events = r.json()
        if not isinstance(events, list):
            return "Could not fetch GitHub activity"
        summary = []
        for e in events[:5]:
            repo = e.get("repo", {}).get("name", "").replace(f"{username}/", "")
            if e.get("type") == "PushEvent":
                n = len(e.get("payload", {}).get("commits", []))
                summary.append(f"Pushed {n} commit(s) to {repo}")
            elif e.get("type") == "CreateEvent":
                summary.append(f"Created: {repo}")
        return "\n".join(summary) if summary else "No recent GitHub activity"
    except Exception as e:
        return f"GitHub error: {e}"

def chat_with_vega(session_id, user_message):
    if session_id not in conversation_history:
        conversation_history[session_id] = []

    history = conversation_history[session_id]
    msg_lower = user_message.lower()
    tools = []

    if any(w in msg_lower for w in ["weather", "tiempo", "temperatura", "clima", "rain", "sunny"]):
        words = user_message.split()
        city = "Granada"
        for i, w in enumerate(words):
            if w.lower() in ["in", "en", "for", "para"] and i + 1 < len(words):
                city = words[i + 1].strip("?.,!")
                break
        tools.append(f"[WEATHER]: {get_weather(city)}")

    if any(w in msg_lower for w in ["github", "commit", "repo", "pushed"]):
        tools.append(f"[GITHUB]: {get_github()}")

    if any(w in msg_lower for w in ["time", "hora", "date", "fecha", "today", "hoy", "now", "ahora"]):
        tools.append(f"[TIME]: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")

    messages = []
    for h in history[-8:]:
        messages.append({"role": h["role"], "parts": [{"text": h["content"]}]})

    user_content = user_message + ("\n\n" + "\n".join(tools) if tools else "")
    messages.append({"role": "user", "parts": [{"text": user_content}]})

    reply = gemini_chat(messages, SYSTEM_PROMPT)

    history.append({"role": "user", "content": user_message})
    history.append({"role": "model", "content": reply})
    if len(history) > 16:
        conversation_history[session_id] = history[-16:]

    return reply

@app.route("/health")
def health():
    return jsonify({"status": "OK", "service": "vega-web"})

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")
    if not message:
        return jsonify({"error": "No message"}), 400
    if not GEMINI_API_KEY:
        return jsonify({"error": "GEMINI_API_KEY not set"}), 500
    try:
        reply = chat_with_vega(session_id, message)
        return jsonify({"reply": reply})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/clear", methods=["POST"])
def clear():
    data = request.json or {}
    conversation_history.pop(data.get("session_id", "default"), None)
    return jsonify({"message": "cleared"})

FRONTEND = os.path.join(os.path.dirname(__file__), '..', 'frontend', 'public')

@app.route("/")
def index():
    return send_from_directory(FRONTEND, 'index.html')

@app.route("/<path:path>")
def static_files(path):
    return send_from_directory(FRONTEND, path)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
