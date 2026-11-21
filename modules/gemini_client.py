"""Talks to Google AI Studio (Gemini / Gemma) with model fallback."""

import logging
import os
import time

import httpx
from google import genai
from google.genai import errors, types

from modules.text_formatter import parse_status

logger = logging.getLogger(__name__)

# Time limits (seconds). Vercel kills a request after 60s (vercel.json), so
# narrator + status check together must finish well inside that.
PER_CALL_TIMEOUT_S = 20  # one model call
NARRATOR_BUDGET_S = 38  # all narrator attempts, including fallbacks
STATUS_BUDGET_S = 12  # all status-check attempts; on failure the turn still counts
MIN_ATTEMPT_S = 3  # don't start a call with less time than this left

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

    # The game uses no tools, so turn off automatic function calling; this also
    # silences the SDK's "AFC is enabled" log line on every request.
    config = types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
    )
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


def _generate(models: list, system_prompt: str, messages: list, budget_s: float, temperature=None) -> str:
    """Try each model in order; move on if one fails, hangs or is overloaded.

    Each call gets a timeout and the SDK's own retries are turned off, so a
    hung or overloaded model can't eat the whole request. On Vercel a request
    is killed after maxDuration (60s), so all attempts together stay within
    `budget_s` seconds.
    """
    if not models:
        raise RuntimeError("No models configured")

    deadline = time.monotonic() + budget_s
    last_error = None
    for model in models:
        remaining = deadline - time.monotonic()
        if remaining < MIN_ATTEMPT_S:
            logger.warning("Out of time before trying %s", model)
            break
        contents, config = _build_request(model, system_prompt, messages)
        if temperature is not None:
            config.temperature = temperature
        config.http_options = types.HttpOptions(
            timeout=int(min(remaining, PER_CALL_TIMEOUT_S) * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        )
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
        except httpx.HTTPError as exc:  # timeouts and connection errors
            last_error = exc
            logger.warning("%s failed (%s), trying next model", model, type(exc).__name__)
    raise last_error or RuntimeError("No time left to call a model")


def generate_reply(history: list, models: list) -> str:
    """Get the narrator's next line from the chat history."""
    system_prompt = "\n".join(m["content"] for m in history if m["role"] == "system")
    turns = [m for m in history if m["role"] != "system"]
    return _generate(models, system_prompt, turns, budget_s=NARRATOR_BUDGET_S)


def stream_reply(history: list, models: list):
    """Yield the narrator's reply in pieces as Gemini writes it.

    Falls back to the next model only if the current one fails before sending
    any text; once text has gone out, a failure is raised to the caller.
    """
    if not models:
        raise RuntimeError("No models configured")
    system_prompt = "\n".join(m["content"] for m in history if m["role"] == "system")
    turns = [m for m in history if m["role"] != "system"]

    deadline = time.monotonic() + NARRATOR_BUDGET_S
    last_error = None
    for model in models:
        remaining = deadline - time.monotonic()
        if remaining < MIN_ATTEMPT_S:
            logger.warning("Out of time before trying %s", model)
            break
        contents, config = _build_request(model, system_prompt, turns)
        config.http_options = types.HttpOptions(
            timeout=int(min(remaining, PER_CALL_TIMEOUT_S) * 1000),
            retry_options=types.HttpRetryOptions(attempts=1),
        )
        sent_any = False
        try:
            for chunk in get_client().models.generate_content_stream(model=model, contents=contents, config=config):
                text = chunk.text
                if text:
                    sent_any = True
                    yield text
            if sent_any:
                return
            last_error = RuntimeError(f"{model} returned an empty response")
            logger.warning("%s returned an empty response, trying next model", model)
        except (errors.APIError, httpx.HTTPError) as exc:
            if sent_any:
                raise
            last_error = exc
            logger.warning("%s failed (%s), trying next model", model, getattr(exc, "code", type(exc).__name__))
    raise last_error or RuntimeError("No time left to call a model")


def classify_status(status_prompt: str, reply: str, models: list) -> str:
    """Return DEAD, WON or UNKNOWN for the narrator's latest reply."""
    try:
        raw = _generate(
            models, status_prompt, [{"role": "user", "content": reply}], budget_s=STATUS_BUDGET_S, temperature=0
        )
    except Exception:
        logger.exception("Status check failed, assuming UNKNOWN")
        return "UNKNOWN"

    return parse_status(raw)
