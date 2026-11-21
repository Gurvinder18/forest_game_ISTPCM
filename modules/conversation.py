"""Keeps the chat history small enough to send to the model."""


def estimate_tokens(text: str) -> int:
    """Rough token count: about four characters per token for English text."""
    return len(text) // 4 + 1


def trim_history(history: list, max_tokens: int) -> list:
    """Drop the oldest turns until the history fits in max_tokens.

    The system prompt (first message, if its role is "system") and the latest
    message are always kept.
    """
    if not history:
        return history

    system = [history[0]] if history[0]["role"] == "system" else []
    turns = history[len(system):]

    def total(msgs):
        return sum(estimate_tokens(m["content"]) for m in msgs)

    while len(turns) > 1 and total(system + turns) > max_tokens:
        turns.pop(0)

    return system + turns
