"""Local Ollama HTTP client for optional LLM-backed code review at T=0, seed=42."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def query_ollama_readability(
    source_code: str,
    model: str = "llama3.1",
    seed: int = 42,
    host: str = "http://127.0.0.1:11434",
    timeout_s: float = 4.0,
) -> Optional[Dict[str, Any]]:
    """Query a local Ollama server for a deterministic JSON readability review."""
    prompt = (
        "Review this C program for readability (naming, comments, formatting). "
        "Return ONLY a JSON object with keys 'score' (integer 1-10) and 'reasons' (list of short strings).\n\n"
        f"```c\n{source_code}\n```"
    )
    payload = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "seed": seed},
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            parsed = json.loads(body.get("response", "{}"))
            if isinstance(parsed, dict) and "score" in parsed:
                return parsed
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
        return None
    return None
