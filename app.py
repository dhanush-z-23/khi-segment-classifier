#!/usr/bin/env python3
"""
KHI Segment Classifier — Web Dashboard

Upload KHI article Excel files and classify them by medical specialty.
Uses the specialties list bundled in the uploads or a default one.

Usage:
    export ANTHROPIC_API_KEY='your-key'
    python app.py [--port 5001]
"""

import argparse
import io
import os
import tempfile
from pathlib import Path

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from classify import (
    classify_khi,
    clean_html,
    load_articles,
    load_specialties,
    write_output,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Store results in memory for the session (simple approach)
_results_store: dict = {}

# Default specialties file path (bundled)
DEFAULT_SPECIALTIES = str(
    Path(__file__).parent / "data/main_specialties.xlsx"
)


@app.route("/")
def index():
    return render_template("index.html", results=_results_store.get("latest"))


@app.route("/classify", methods=["POST"])
def classify():
    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        flash("ANTHROPIC_API_KEY not set. Export it before starting the server.", "error")
        return redirect(url_for("index"))

    # Get uploaded KHI file
    khi_file = request.files.get("khi_file")
    if not khi_file or not khi_file.filename.endswith(".xlsx"):
        flash("Please upload a valid .xlsx file with KHI articles.", "error")
        return redirect(url_for("index"))

    # Optional specialties file
    spec_file = request.files.get("specialties_file")

    # Save uploads to temp files
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_khi:
        khi_file.save(tmp_khi.name)
        khi_path = tmp_khi.name

    if spec_file and spec_file.filename.endswith(".xlsx"):
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_spec:
            spec_file.save(tmp_spec.name)
            spec_path = tmp_spec.name
    else:
        spec_path = DEFAULT_SPECIALTIES

    try:
        # Load data
        articles = load_articles(khi_path)
        specialties = load_specialties(spec_path)

        if not articles:
            flash("No articles found in the uploaded file (no rows with titles).", "error")
            return redirect(url_for("index"))

        # Classify
        classification = classify_khi(articles, specialties)

        # Generate output Excel
        output_path = khi_path.replace(".xlsx", "_classified.xlsx")
        write_output(khi_path, output_path, classification, articles)

        # Build result for dashboard
        result = {
            "filename": khi_file.filename,
            "num_articles": len(articles),
            "classification": classification,
            "articles": [
                {
                    "sno": a["sno"],
                    "title": a["title"],
                    "teaser": a["teaser"][:200] if a["teaser"] else "",
                    "content_preview": a["content_clean"][:300] + "..."
                    if len(a["content_clean"]) > 300
                    else a["content_clean"],
                }
                for a in articles
            ],
            "specialties": specialties,
            "output_path": output_path,
        }
        _results_store["latest"] = result

    except Exception as e:
        flash(f"Classification failed: {str(e)}", "error")
        return redirect(url_for("index"))
    finally:
        os.unlink(khi_path)
        if spec_path != DEFAULT_SPECIALTIES and os.path.exists(spec_path):
            os.unlink(spec_path)

    return redirect(url_for("index"))


@app.route("/download")
def download():
    result = _results_store.get("latest")
    if not result or not os.path.exists(result.get("output_path", "")):
        flash("No classified file available. Run classification first.", "error")
        return redirect(url_for("index"))

    return send_file(
        result["output_path"],
        as_attachment=True,
        download_name=result["filename"].replace(".xlsx", "_classified.xlsx"),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.route("/api/classify", methods=["POST"])
def api_classify():
    """JSON API endpoint for programmatic use."""
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
        classification = classify_khi(articles, specialties)

        return jsonify({
            "filename": khi_file.filename,
            "num_articles": len(articles),
            "classification": classification,
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
