# EcoSort.AI

EcoSort is a polished Flask web app that uses Gemini vision to identify waste from a photo and recommend the right disposal category. It supports organic, recyclable, e-waste, hazardous, and general waste, with practical preparation guidance.

## Run locally

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env
```

Add a Gemini API key to `.env` as `GEMINI_API_KEY=...`, then start the server:

```bash
python app.py
```

Open <http://localhost:5000>. If no key is configured, the app runs in a safe demo mode so the interface can still be explored. Set `ALLOW_DEMO_MODE=false` to return an error instead.

## API

`POST /api/classify` accepts a multipart form field named `image`. The response includes the detected item, category, confidence, reasoning, and disposal preparation tip.

## Responsible use

AI results are guidance, not a substitute for local waste authority rules. Always verify hazardous materials, batteries, medical waste, and local recycling requirements before disposal.
