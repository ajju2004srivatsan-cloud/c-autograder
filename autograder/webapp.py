"""Minimal zero-dependency HTTP server for uploading C submissions and viewing grading reports."""

from __future__ import annotations

import json
import tempfile
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from autograder.coordinator import evaluate_submission, format_student_text_report


class AutoGraderHTTPHandler(BaseHTTPRequestHandler):
    rules_path: Path = Path("rules/add_two_integers.json")

    def do_GET(self) -> None:
        body = (
            "<html><head><title>c-autograder</title></head>"
            "<body style='font-family:monospace;max-width:780px;margin:2rem auto;'>"
            "<h2>c-autograder HTTP API</h2>"
            "<p>POST raw C source code to <code>/grade</code> to receive a full JSON & text evaluation.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/grade":
            self.send_error(404, "Endpoint not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        source = self.rfile.read(length).decode("utf-8", errors="replace")
        with tempfile.NamedTemporaryFile(suffix=".c", mode="w", encoding="utf-8", delete=False) as tmp:
            tmp.write(source)
            tmp_path = Path(tmp.name)
        try:
            report = evaluate_submission(tmp_path, self.rules_path)
            report["text_report"] = format_student_text_report(report)
            payload = json.dumps(report, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        finally:
            tmp_path.unlink(missing_ok=True)


def run_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    server = HTTPServer((host, port), AutoGraderHTTPHandler)
    server.serve_forever()
