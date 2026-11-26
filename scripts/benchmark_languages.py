#!/usr/bin/env python3
"""Run a local Welsh/English response benchmark against an Ollama model.

This script sends requests only to an Ollama API bound to localhost. It records
model outputs for human scoring; it does not claim to judge fluency automatically.
Example:
    python scripts/benchmark_languages.py --model qwen2.5:1.5b
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SYSTEM_PROMPT = (
    "You are Orinoco, a helpful assistant. Reply in the language of the user's "
    "message: use natural Welsh (Cymraeg) for Welsh and English for English. "
    "Preserve Welsh spelling and diacritics. Do not translate unless asked. "
    "Follow the user's requested format and length."
)

# Keep each English/Welsh pair equivalent so the outputs can be compared.
CASES = [
    {
        "id": "greeting",
        "language": "en",
        "prompt": "Hello, what can you help me with?",
    },
    {
        "id": "greeting",
        "language": "cy",
        "prompt": "Helo, beth allwch chi fy helpu i ag ef?",
    },
    {
        "id": "simple_explanation",
        "language": "en",
        "prompt": "Explain why the sky looks blue in simple terms.",
    },
    {
        "id": "simple_explanation",
        "language": "cy",
        "prompt": "Eglurwch pam mae'r awyr yn edrych yn las mewn termau syml.",
    },
    {
        "id": "practical_steps",
        "language": "en",
        "prompt": "Give me three simple steps to make a cup of tea.",
    },
    {
        "id": "practical_steps",
        "language": "cy",
        "prompt": "Rhowch dri cham syml i mi wneud paned o de.",
    },
    {
        "id": "summary",
        "language": "en",
        "prompt": "Summarise this in two sentences: Orinoco is a self-hosted assistant. It runs a local language model and aims to support Welsh and English.",
    },
    {
        "id": "summary",
        "language": "cy",
        "prompt": "Crynhowch hyn mewn dwy frawddeg: Mae Orinoco yn gynorthwyydd hunan-gynhaliol. Mae'n rhedeg model iaith lleol ac yn anelu at gefnogi'r Gymraeg a'r Saesneg.",
    },
    {
        "id": "follow_up",
        "language": "en",
        "history": [
            {"role": "user", "content": "Explain why the sky looks blue in simple terms."},
            {"role": "assistant", "content": "The sky looks blue because air scatters blue sunlight more than other colours."},
        ],
        "prompt": "Now make that explanation shorter.",
    },
    {
        "id": "follow_up",
        "language": "cy",
        "history": [
            {"role": "user", "content": "Eglurwch pam mae'r awyr yn edrych yn las mewn termau syml."},
            {"role": "assistant", "content": "Mae'r awyr yn edrych yn las oherwydd bod yr aer yn gwasgaru golau glas yr haul yn fwy na lliwiau eraill."},
        ],
        "prompt": "Nawr gwnewch yr eglurhad hwnnw'n fyrrach.",
    },
    {
        "id": "welsh_names",
        "language": "en",
        "prompt": "Write a short sentence containing Ceredigion, Llŷr and Siân, with their spelling unchanged.",
    },
    {
        "id": "welsh_names",
        "language": "cy",
        "prompt": "Ysgrifennwch frawddeg fer sy'n cynnwys Ceredigion, Llŷr a Siân, gan gadw'r sillafu'n gywir.",
    },
    {
        "id": "code_switch",
        "language": "cy-en",
        "prompt": "Dw i'n gweithio ar Orinoco. Can you explain in one sentence what a local language model is?",
    },
    {
        "id": "code_switch",
        "language": "en-cy",
        "prompt": "I'm testing Orinoco. Allwch chi egluro mewn un frawddeg beth yw model iaith lleol?",
    },
]


def local_endpoint(value: str) -> str:
    """Validate that the Ollama endpoint is loopback-only."""
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("Ollama URL must use http://localhost, 127.0.0.1 or [::1].")
    if parsed.username or parsed.password:
        raise ValueError("Do not put credentials in the Ollama URL.")
    if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
        raise ValueError("Use the Ollama API origin only; paths, queries and fragments are not allowed.")
    return value.rstrip("/")


def ask_ollama(
    endpoint: str, model: str, prompt: str, context: int, timeout: int,
    history: list[dict[str, str]] | None = None,
) -> str:
    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            *(history or []),
            {"role": "user", "content": prompt},
        ],
        "options": {"num_ctx": context},
    }
    request = urllib.request.Request(
        endpoint + "/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    class RejectRedirects(urllib.request.HTTPRedirectHandler):
        """Keep loopback requests from being redirected to a remote host."""

        def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
            return None

    opener = urllib.request.build_opener(RejectRedirects())
    with opener.open(request, timeout=timeout) as response:
        result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
    message = result.get("message", {})
    answer = message.get("content")
    if not isinstance(answer, str):
        raise RuntimeError("Ollama response did not contain message.content.")
    return answer


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Exact local Ollama model tag.")
    parser.add_argument("--url", default="http://127.0.0.1:11434", help="Loopback Ollama API URL.")
    parser.add_argument("--context", type=int, default=4096, help="Ollama context length.")
    parser.add_argument("--timeout", type=int, default=600, help="Per-prompt timeout in seconds.")
    parser.add_argument("--output", type=Path, help="Output JSON path (default: timestamped file).")
    args = parser.parse_args()

    if args.context < 512 or args.timeout < 1:
        parser.error("--context must be at least 512 and --timeout must be positive.")
    try:
        endpoint = local_endpoint(args.url)
    except ValueError as exc:
        parser.error(str(exc))

    output_path = args.output or Path(
        "language-benchmark-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json"
    )
    results: list[dict[str, Any]] = []
    started = time.monotonic()

    for index, case in enumerate(CASES, start=1):
        print(f"[{index}/{len(CASES)}] {case['id']} ({case['language']})", flush=True)
        try:
            answer = ask_ollama(endpoint, args.model, case["prompt"], args.context, args.timeout, case.get("history"))
            results.append({**case, "response": answer, "error": None})
        except (urllib.error.URLError, TimeoutError, RuntimeError, json.JSONDecodeError) as exc:
            results.append({**case, "response": None, "error": str(exc)})
            print(f"  ERROR: {exc}", flush=True)

    report = {
        "benchmark": "Orinoco Welsh-English local model check",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "ollama_endpoint": endpoint,
        "context_length": args.context,
        "system_prompt": SYSTEM_PROMPT,
        "duration_seconds": round(time.monotonic() - started, 2),
        "results": results,
        "scoring_note": "Score each response manually using docs/LANGUAGE_SUPPORT.md; this script does not auto-score fluency.",
    }
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved responses to {output_path}")
    print("Review the JSON locally; it may contain prompt text or model output you consider private.")
    return 0 if all(item["error"] is None for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
