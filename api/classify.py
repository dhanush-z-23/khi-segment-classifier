"""Vercel serverless function — exposes Flask app as WSGI handler."""

import os
import sys
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from classify import classify_khi, load_articles, load_specialties

app = Flask(__name__, static_folder=str(Path(__file__).parent.parent / "public"))

DEFAULT_SPECIALTIES = str(Path(__file__).parent.parent / "data/main_specialties.xlsx")


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_static(path):
    if not path:
        path = "index.html"
    return send_from_directory(app.static_folder, path)


@app.route("/api/classify", methods=["POST"])
def api_classify():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "ANTHROPIC_API_KEY not configured"}), 500

    khi_file = request.files.get("khi_file")
    if not khi_file:
        return jsonify({"error": "khi_file is required"}), 400

    spec_file = request.files.get("specialties_file")

    khi_path = None
    spec_path = DEFAULT_SPECIALTIES

    try:
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            khi_file.save(tmp.name)
            khi_path = tmp.name

        if spec_file and spec_file.filename and spec_file.filename.endswith(".xlsx"):
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                spec_file.save(tmp.name)
                spec_path = tmp.name

        articles = load_articles(khi_path)
        specialties = load_specialties(spec_path)

        if not articles:
            return jsonify({"error": "No articles found (no rows with titles)"}), 400

        classification = classify_khi(articles, specialties)

        return jsonify({
            "filename": khi_file.filename,
            "num_articles": len(articles),
            "classification": classification,
            "articles": [
                {
                    "sno": a["sno"],
                    "title": a["title"],
                    "teaser": a["teaser"][:200] if a["teaser"] else "",
                    "content_preview": (
                        a["content_clean"][:300] + "..."
                        if len(a["content_clean"]) > 300
                        else a["content_clean"]
                    ),
                }
                for a in articles
            ],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if khi_path and os.path.exists(khi_path):
            os.unlink(khi_path)
        if spec_path != DEFAULT_SPECIALTIES and os.path.exists(spec_path):
            os.unlink(spec_path)
