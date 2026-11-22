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


class StreamStatusFilter:
    """Hides the narrator's STATUS line while a reply is being streamed.

    Text is passed through as it arrives, except a line that might turn out to
    be the status line: that is held back until it's complete, then dropped if
    it is one. The final reply sent at the end of the stream (from
    extract_status) is what the player keeps; this only keeps the live view
    clean.
    """

    _LEAD = re.compile(r"^[^\w\n]*")

    def __init__(self):
        self._line = ""  # current line, not yet shown
        self._line_shown = False  # current line already passed through
        self._held_status = ""  # a complete status line, shown only if more text follows

    def _could_be_status(self, line: str) -> bool:
        word = self._LEAD.sub("", line).lower()
        return word[:6] == "status"[: len(word[:6])]

    def _emit(self, out: list, text: str):
        if self._held_status and text.strip():
            out.append(self._held_status)  # it wasn't the last line after all
            self._held_status = ""
        out.append(text)

    def feed(self, chunk: str) -> str:
        out = []
        for ch in chunk:
            if ch == "\n":
                if self._line_shown:
                    out.append("\n")
                elif _STATUS_LINE.fullmatch(self._line.strip()):
                    self._held_status = self._line + "\n"
                else:
                    self._emit(out, self._line + "\n")
                self._line, self._line_shown = "", False
            elif self._line_shown:
                out.append(ch)
            else:
                self._line += ch
                if not self._could_be_status(self._line):
                    self._emit(out, self._line)
                    self._line_shown = True
        return "".join(out)

    def finish(self) -> str:
        out = []
        if not self._line_shown and self._line and not _STATUS_LINE.fullmatch(self._line.strip()):
            self._emit(out, self._line)
        self._line, self._line_shown = "", False
        return "".join(out)


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
