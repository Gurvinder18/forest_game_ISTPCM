import os

NARRATOR_PROMPT = """
In this open text adventure game, the user's objective is to escape a forest filled with dangerous creatures such as vampires, hunters, and wild creatures.
The user must be careful not to provoke these creatures as they can die in the game. The chances of escaping are slim, and escape will only be granted on occasion.
You are the game moderator, answer in short fashion (no long messages), and be neutral but snarky. Be creative to make the game more interesting.
If the user is too reckless they WILL die.
"""

STATUS_PROMPT = """
In this open text adventure game, the user's objective is to escape a forest. If the user escapes the forest, they win.
Classify a text as DEAD, WON, or UNKNOWN based on its content. This classification corresponds to the status of the player of the game.
The user is DEAD only when the text explicitly says they have died or suffered fatal injuries they cannot recover from.
The user has WON only when the text explicitly says they have escaped the forest.
Danger, threats, injuries or being chased are NOT death. If the text asks the player what they do next, the answer is UNKNOWN.
Return ONLY one of these three values, with no additional text, punctuation or explanation.
"""

MAX_HISTORY_TOKENS = 8000

# Google AI Studio models, tried in order. If one is rate-limited (429) or
# overloaded (503), the next one is used. Override in .env as comma-separated lists.
#
# Free-tier limits at time of writing:
#   gemini-3.5-flash-lite  15 RPM / 250K TPM / 500 RPD     (narrator)
#   gemini-3.1-flash-lite  15 RPM / 250K TPM / 500 RPD     (status checks, narrator fallback)
#   gemma-4-31b-it         30 RPM /  16K TPM / 14.4K RPD   (status fallback, short prompts)
#
# The narrator and the status check start on different models so each turn
# spends one request from each daily quota instead of two from the same one.


def _model_list(env_var: str, default: str) -> list:
    return [m.strip() for m in os.getenv(env_var, default).split(",") if m.strip()]


NARRATOR_MODELS = _model_list("NARRATOR_MODELS", "gemini-3.5-flash-lite,gemini-3.1-flash-lite,gemma-4-31b-it")
STATUS_MODELS = _model_list("STATUS_MODELS", "gemini-3.1-flash-lite,gemma-4-31b-it,gemini-3.5-flash-lite")
