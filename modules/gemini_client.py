"""Talks to Google AI Studio (Gemini / Gemma) with model fallback."""

import logging
import os

from google import genai
from google.genai import errors, types

from modules.text_formatter import parse_status

logger = logging.getLogger(__name__)

_client = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env (see .env.example).")
        _client = genai.Client(api_key=api_key)
    return _client


def _supports_system_instruction(model: str) -> bool:
    # Gemma models on AI Studio reject system instructions.
    return not model.startswith("gemma")


def _build_request(model: str, system_prompt: str, messages: list):
    """Turn {"role", "content"} messages into Gemini contents + config."""
    contents = []
    for msg in messages:
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    config = types.GenerateContentConfig()
    if system_prompt:
        if _supports_system_instruction(model):
            config.system_instruction = system_prompt
        else:
            # Fold the instructions into the first user turn instead.
            first = contents[0] if contents and contents[0].role == "user" else None
            if first:
                first.parts[0].text = f"{system_prompt.strip()}\n\n{first.parts[0].text}"
            else:
                contents.insert(0, types.Content(role="user", parts=[types.Part(text=system_prompt)]))
    return contents, config


def _generate(models: list, system_prompt: str, messages: list, temperature=None) -> str:
    """Try each model in order; move on if one fails (rate limit, overload, etc.)."""
    if not models:
        raise RuntimeError("No models configured")

    last_error = None
    for model in models:
        contents, config = _build_request(model, system_prompt, messages)
        if temperature is not None:
            config.temperature = temperature
        try:
            response = get_client().models.generate_content(model=model, contents=contents, config=config)
            text = (response.text or "").strip()
            if text:
                return text
            last_error = RuntimeError(f"{model} returned an empty response")
            logger.warning("%s returned an empty response, trying next model", model)
        except errors.APIError as exc:
            last_error = exc
            logger.warning("%s failed (%s), trying next model", model, exc.code)
    raise last_error


def generate_reply(history: list, models: list) -> str:
    """Get the narrator's next line from the chat history."""
    system_prompt = "\n".join(m["content"] for m in history if m["role"] == "system")
    turns = [m for m in history if m["role"] != "system"]
    return _generate(models, system_prompt, turns)


def classify_status(status_prompt: str, reply: str, models: list) -> str:
    """Return DEAD, WON or UNKNOWN for the narrator's latest reply."""
    try:
        raw = _generate(models, status_prompt, [{"role": "user", "content": reply}], temperature=0)
    except Exception:
        logger.exception("Status check failed, assuming UNKNOWN")
        return "UNKNOWN"

    return parse_status(raw)
