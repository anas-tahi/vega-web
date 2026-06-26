# 🤖 VEGA Web — Bilingual AI Assistant

Web version of VEGA — the bilingual (EN/ES) AI assistant by Anas Tahir.

## Deploy on Render

1. Push this repo to GitHub
2. New Web Service on Render → connect repo
3. Settings:
   - Root Directory: `backend`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app`
4. Environment Variables:
   - `GEMINI_API_KEY` — from aistudio.google.com
   - `WEATHER_API_KEY` — from openweathermap.org (free)
   - `GITHUB_TOKEN` — optional, for private repos

## Local Dev
```bash
cd backend
pip install -r requirements.txt
GEMINI_API_KEY=your_key python app.py
```
Then open http://localhost:5000
