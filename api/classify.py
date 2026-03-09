"""Vercel serverless function for KHI classification."""

import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Add parent dir to path so we can import classify module
sys.path.insert(0, str(Path(__file__).parent.parent))

from classify import classify_khi, load_articles, load_specialties

DEFAULT_SPECIALTIES = str(Path(__file__).parent.parent / "data/main_specialties.xlsx")


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_type = self.headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            self._json_response(400, {"error": "Content-Type must be multipart/form-data"})
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            self._json_response(500, {"error": "ANTHROPIC_API_KEY not configured on server"})
            return

        try:
            # Parse multipart form data
            import cgi
            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={
                    "REQUEST_METHOD": "POST",
                    "CONTENT_TYPE": content_type,
                },
            )

            khi_field = form["khi_file"]
            if not khi_field.filename:
                self._json_response(400, {"error": "khi_file is required"})
                return

            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                tmp.write(khi_field.file.read())
                khi_path = tmp.name

            # Check for optional specialties file
            spec_path = DEFAULT_SPECIALTIES
            if "specialties_file" in form and form["specialties_file"].filename:
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                    tmp.write(form["specialties_file"].file.read())
                    spec_path = tmp.name

            # Load and classify
            articles = load_articles(khi_path)
            specialties = load_specialties(spec_path)

            if not articles:
                self._json_response(400, {"error": "No articles found (no rows with titles)"})
                return

            classification = classify_khi(articles, specialties)

            result = {
                "filename": khi_field.filename,
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
            }

            self._json_response(200, result)

        except Exception as e:
            self._json_response(500, {"error": str(e)})

        finally:
            # Cleanup temp files
            if "khi_path" in locals() and os.path.exists(khi_path):
                os.unlink(khi_path)
            if "spec_path" in locals() and spec_path != DEFAULT_SPECIALTIES and os.path.exists(spec_path):
                os.unlink(spec_path)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _json_response(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
