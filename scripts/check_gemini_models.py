"""Check which Gemini models your API key can really use.

Run from the project folder:
    python scripts/check_gemini_models.py            (lists models + tests your chain)
    python scripts/check_gemini_models.py --no-list  (only tests your chain)
    python scripts/check_gemini_models.py gemini-3.8-flash gemini-3.5-flash-lite

It never prints your API key.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from src.enhance.provider import GeminiProvider, parse_model_list

BASE = "https://generativelanguage.googleapis.com/v1beta"


def list_models(client: httpx.Client, key: str) -> None:
    print("\nModels your key can call with generateContent (use these exact ids):")
    token = None
    shown = 0
    while True:
        params = {"pageSize": 200, **({"pageToken": token} if token else {})}
        response = client.get(f"{BASE}/models", params=params, headers={"x-goog-api-key": key})
        if response.status_code != 200:
            print(f"  Could not list models (HTTP {response.status_code}). Check GEMINI_API_KEY.")
            return
        data = response.json()
        for item in data.get("models", []):
            if "generateContent" in item.get("supportedGenerationMethods", []):
                print(f"  {item['name'].removeprefix('models/'):40s} {item.get('displayName', '')}")
                shown += 1
        token = data.get("nextPageToken")
        if not token:
            break
    print(f"  ({shown} models)")


def test_model(client: httpx.Client, key: str, model: str) -> bool:
    body = {
        "contents": [{"parts": [{"text": 'Reply with this JSON only: {"ok": true}'}]}],
        "generationConfig": {"maxOutputTokens": 512, "responseMimeType": "application/json"},
    }
    started = time.monotonic()
    try:
        response = client.post(f"{BASE}/models/{model}:generateContent", json=body, headers={"x-goog-api-key": key})
    except httpx.HTTPError as error:
        print(f"  FAIL  {model:32s} network problem ({type(error).__name__})")
        return False
    seconds = time.monotonic() - started
    if response.status_code == 200:
        print(f"  OK    {model:32s} answered in {seconds:.1f}s")
        return True
    reasons = {404: "model id not found / not enabled", 429: "quota or rate limit used up", 403: "no access", 400: "bad request or bad key", 503: "overloaded right now"}
    print(f"  FAIL  {model:32s} HTTP {response.status_code} - {reasons.get(response.status_code, 'error')}")
    return False


def main(argv: list[str]) -> int:
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        print("GEMINI_API_KEY is not set. Put it in your .env file first.")
        return 1
    show_list = "--no-list" not in argv
    models = parse_model_list(",".join(a for a in argv if not a.startswith("--"))) or list(GeminiProvider().models)
    with httpx.Client(timeout=60.0) as client:
        if show_list:
            list_models(client, key)
        print("\nTesting the models your app will use, in order:")
        working = [m for m in models if test_model(client, key, m)]
    print("\nSuggested line for your .env file:")
    print(f"GEMINI_MODELS={','.join(working)}" if working else "  (no model worked - see the messages above)")
    return 0 if working else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
