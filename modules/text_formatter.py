"""Cleans up model output so it reads well in a plain-text terminal."""

import re


_STATUS_LINE = re.compile(
    r"^[^\w\n]*STATUS[^\w\n]*[:=\-][^\w\n]*(ALIVE|DEAD|WON|UNKNOWN)\b[^\n]*$",
    re.IGNORECASE | re.MULTILINE,
)


def extract_status(text: str):
    """Split the narrator's 'STATUS: ...' tag off its reply.

    Returns (reply_without_tag, status), where status is DEAD, WON or UNKNOWN,
    or None if the narrator left the tag out (the caller then falls back to a
    separate classifier call). Tolerates markdown like '**Status:** dead'.
    """
    if not text:
        return text, None
    matches = list(_STATUS_LINE.finditer(text))
    if not matches:
        return text, None
    last = matches[-1]
    # Only trust a tag on the last non-empty line, so a mid-story mention
    # can't end the game.
    if text[last.end():].strip():
        return text, None
    value = last.group(1).upper()
    status = "UNKNOWN" if value in ("ALIVE", "UNKNOWN") else value
    return text[: last.start()].rstrip(), status


def parse_status(raw: str) -> str:
    """Map a classifier answer to DEAD, WON or UNKNOWN."""
    raw = (raw or "").upper()
    if "DEAD" in raw:
        return "DEAD"
    if "WON" in raw:
        return "WON"
    return "UNKNOWN"


def format_reply(text: str) -> str:
    """Strip markdown the terminal can't render and tidy whitespace."""
    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", text)  # italics
    text = re.sub(r"`([^`]*)`", r"\1", text)  # inline code
    text = re.sub(r"^[ \t]*[*\-][ \t]+", "- ", text, flags=re.MULTILINE)  # bullets (keep blank lines above)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
