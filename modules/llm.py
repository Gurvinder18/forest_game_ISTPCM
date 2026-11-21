"""Picks the AI backend from LLM_PROVIDER: "gemini" (default) or "lmstudio"."""

import logging
import os

logger = logging.getLogger(__name__)

PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

if PROVIDER == "lmstudio":
    from modules.lmstudio_client import classify_status, generate_reply
elif PROVIDER == "gemini":
    from modules.gemini_client import classify_status, generate_reply
else:
    raise RuntimeError(f"Unknown LLM_PROVIDER '{PROVIDER}'. Use 'gemini' or 'lmstudio'.")

logger.info("AI backend: %s", PROVIDER)

__all__ = ["PROVIDER", "classify_status", "generate_reply"]
