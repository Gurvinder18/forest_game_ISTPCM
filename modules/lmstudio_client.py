"""Talks to a local LM Studio server (OpenAI-compatible API).

Only works when the app runs on the same machine as LM Studio, so use it for
local play and keep Gemini for hosted deployments like Vercel.
"""

import json
import logging
import os
import re
import urllib.error
import urllib.request

from modules.text_formatter import parse_status

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 180  # local models can be slow on the first request


def _base_url() -> str:
    return os.getenv("LMSTUDIO_URL", "http://localhost:1234/v1").rstrip("/")


def _request(path: str, payload=None) -> dict:
    url = f"{_base_url()}{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as res:
            return json.loads(res.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")[:300]
        raise RuntimeError(f"LM Studio returned {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Can't reach LM Studio at {_base_url()}. Start the server in LM Studio's Developer tab and load a model."
        ) from exc


_model_cache = None


def _model() -> str:
    """Use LMSTUDIO_MODEL if set, otherwise the first model LM Studio has loaded."""
    global _model_cache
    configured = os.getenv("LMSTUDIO_MODEL", "").strip()
    if configured:
        return configured
    if _model_cache is None:
        # Embedding models can't chat, so skip them.
        models = [m for m in _request("/models").get("data", []) if "embed" not in m["id"].lower()]
        if not models:
            raise RuntimeError("LM Studio has no model loaded. Load one in LM Studio first.")
        _model_cache = models[0]["id"]
        logger.info("Using LM Studio model: %s", _model_cache)
    return _model_cache


def _to_messages(system_prompt: str, turns: list) -> list:
    """Build OpenAI-style messages.

    The system prompt is folded into the first user turn because some local
    chat templates (Gemma's included) don't accept a separate system role.
    """
    messages = [{"role": m["role"], "content": m["content"]} for m in turns]
    if system_prompt:
        if messages and messages[0]["role"] == "user":
            messages[0]["content"] = f"{system_prompt.strip()}\n\n{messages[0]['content']}"
        else:
            messages.insert(0, {"role": "user", "content": system_prompt.strip()})
    return messages


def _chat(system_prompt: str, turns: list, temperature=0.8, max_tokens=300) -> str:
    payload = {
        "model": _model(),
        "messages": _to_messages(system_prompt, turns),
        "temperature": temperature,
        "max_tokens": max_tokens,
        # Thinking models (e.g. Gemma 4) otherwise spend the whole token budget
        # reasoning and return an empty reply. Short narration doesn't need it.
        "reasoning_effort": "none",
        "stream": False,
    }
    data = _request("/chat/completions", payload)
    text = data["choices"][0]["message"].get("content") or ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # drop reasoning if present
    if not text:
        raise RuntimeError("LM Studio returned an empty response")
    return text


def generate_reply(history: list, models=None) -> str:
    """Get the narrator's next line. `models` is ignored (LM Studio uses one local model)."""
    system_prompt = "\n".join(m["content"] for m in history if m["role"] == "system")
    turns = [m for m in history if m["role"] != "system"]
    return _chat(system_prompt, turns)


def classify_status(status_prompt: str, reply: str, models=None) -> str:
    """Return DEAD, WON or UNKNOWN for the narrator's latest reply."""
    try:
        raw = _chat(status_prompt, [{"role": "user", "content": reply}], temperature=0, max_tokens=10)
    except Exception:
        logger.exception("Status check failed, assuming UNKNOWN")
        return "UNKNOWN"
    return parse_status(raw)
