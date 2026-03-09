#!/usr/bin/env python3
"""
KHI Segment Classifier — Web Dashboard (Local Server)

Upload KHI article Excel files and classify them by medical specialty.

Usage:
    export ANTHROPIC_API_KEY='your-key'
    python app.py [--port 5001]
"""

import argparse
import os
import tempfile
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from classify import (
    classify_khi,
    load_articles,
    load_specialties,
)

app = Flask(__name__, static_folder="public", static_url_path="")

DEFAULT_SPECIALTIES = str(Path(__file__).parent / "data/main_specialties.xlsx")


@app.route("/")
def index():
    return send_from_directory("public", "index.html")


@app.route("/api/classify", methods=["POST"])
def api_classify():
    """JSON API endpoint — works for both dashboard and programmatic use."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return jsonify({"error": "ANTHROPIC_API_KEY not set"}), 500

    khi_file = request.files.get("khi_file")
    if not khi_file:
        return jsonify({"error": "khi_file is required"}), 400

    spec_file = request.files.get("specialties_file")

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        khi_file.save(tmp.name)
        khi_path = tmp.name

    if spec_file and spec_file.filename.endswith(".xlsx"):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            spec_file.save(tmp.name)
            spec_path = tmp.name
    else:
        spec_path = DEFAULT_SPECIALTIES

    try:
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
        os.unlink(khi_path)
        if spec_path != DEFAULT_SPECIALTIES and os.path.exists(spec_path):
            os.unlink(spec_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KHI Classifier Web Dashboard")
    parser.add_argument("--port", type=int, default=5001, help="Port (default: 5001)")
    parser.add_argument("--debug", action="store_true", help="Debug mode")
    args = parser.parse_args()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY not set. Set it before classifying.")
        print("  export ANTHROPIC_API_KEY='your-key-here'")

    print(f"\n  KHI Classifier Dashboard: http://localhost:{args.port}\n")
    app.run(host="0.0.0.0", port=args.port, debug=args.debug)
