import base64
import json
import mimetypes
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
CATEGORIES = {
    "organic": {
        "label": "Organic / Compost",
        "color": "green",
        "description": "Food scraps and other biodegradable material for composting.",
        "tip": "Keep it free of plastic, glass, and metal before adding it to a compost bin.",
    },
    "recyclable": {
        "label": "Recyclable",
        "color": "blue",
        "description": "Clean paper, cardboard, metal, or accepted rigid plastic.",
        "tip": "Empty, rinse, and dry the item. Check local recycling rules for the material.",
    },
    "e_waste": {
        "label": "Electronic Waste",
        "color": "purple",
        "description": "Devices, batteries, chargers, and other items containing electronics.",
        "tip": "Never place electronics or batteries in household bins. Use an e-waste drop-off point.",
    },
    "hazardous": {
        "label": "Hazardous Waste",
        "color": "red",
        "description": "Material that can harm people or the environment if handled incorrectly.",
        "tip": "Keep it sealed and follow your local hazardous-waste collection guidance.",
    },
    "general": {
        "label": "General Waste",
        "color": "gray",
        "description": "Waste that cannot currently be reused, composted, or recycled locally.",
        "tip": "Look for a reuse or take-back option first, then place it in general waste.",
    },
}


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def clean_json(text: str) -> dict:
    """Extract JSON even if a model wraps it in markdown fences."""
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "").strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("The AI response did not contain JSON")
    return json.loads(match.group(0))


def _is_retryable_gemini_error(error: Exception) -> bool:
    """Return true for temporary quota/service failures, not bad requests or auth errors."""
    status = getattr(error, "status_code", None)
    if status in {429, 500, 502, 503, 504}:
        return True
    # Some google-genai versions expose the status only in the exception text.
    return any(code in str(error) for code in (" 429 ", " 500 ", " 502 ", " 503 ", " 504 "))


def classify_with_gemini(file_bytes: bytes, mime_type: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    # Import lazily so the app can still start in demo mode without an API key.
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    prompt = """You are EcoSort, a careful waste-sorting assistant. Inspect the image and identify the primary item.
Return ONLY valid JSON with these keys:
{"item":"short item name","category":"one of organic, recyclable, e_waste, hazardous, general","confidence":0.0,"reason":"one sentence","preparation":"short disposal preparation instruction"}
Use general when uncertain. Do not invent local recycling rules. Confidence must be between 0 and 1."""

    primary_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    fallback_models = os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.5-flash").split(",")
    models = list(dict.fromkeys([primary_model] + [model.strip() for model in fallback_models if model.strip()]))
    last_error = None

    for model in models:
        # 503 means the selected model is temporarily overloaded. Retry with
        # backoff, then try the configured fallback model if it remains unavailable.
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                        prompt,
                    ],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        response_mime_type="application/json",
                    ),
                )
                result = clean_json(response.text)
                category = str(result.get("category", "general")).lower().strip()
                if category not in CATEGORIES:
                    category = "general"
                result["category"] = category
                result["confidence"] = max(0, min(1, float(result.get("confidence", 0.5))))
                return result
            except Exception as error:
                last_error = error
                if not _is_retryable_gemini_error(error) or attempt == 2:
                    break
                time.sleep(2 ** attempt)

    raise RuntimeError("Gemini is temporarily unavailable after retries") from last_error


def demo_result(filename: str) -> dict:
    return {
        "item": Path(filename).stem.replace("_", " ").replace("-", " ") or "Uploaded item",
        "category": "general",
        "confidence": 0,
        "reason": "AI vision is not configured yet, so this is a safe demo result.",
        "preparation": "Add a Gemini API key to enable image classification.",
        "demo": True,
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/classify")
def classify():
    uploaded = request.files.get("image")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Please choose an image first."}), 400
    if not allowed_file(uploaded.filename):
        return jsonify({"error": "Use a JPG, PNG, WEBP, or GIF image."}), 400

    file_bytes = uploaded.read()
    mime_type = uploaded.mimetype or mimetypes.guess_type(uploaded.filename)[0] or "image/jpeg"
    try:
        result = classify_with_gemini(file_bytes, mime_type)
    except Exception as error:
        if os.getenv("ALLOW_DEMO_MODE", "true").lower() == "true" and "GEMINI_API_KEY" not in os.environ:
            result = demo_result(uploaded.filename)
        else:
            app.logger.exception("Image classification failed")
            return jsonify({"error": "The image service is temporarily unavailable. Please try again."}), 503

    result["category_details"] = CATEGORIES[result["category"]]
    return jsonify(result)


@app.errorhandler(413)
def too_large(_error):
    return jsonify({"error": "That image is too large. Please use an image under 10 MB."}), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
