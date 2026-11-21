"""Cleans up model output so it reads well in a plain-text terminal."""

import re


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
