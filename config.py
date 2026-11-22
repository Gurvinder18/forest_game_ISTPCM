import os

# How long the narrator's replies are: "short" or "long". Defaults to "long"
# with a local LM Studio model (no quota to save) and "short" with Gemini.
NARRATOR_LENGTH = (
    os.getenv("NARRATOR_LENGTH", "").strip().lower()
    or ("long" if os.getenv("LLM_PROVIDER", "gemini").strip().lower() == "lmstudio" else "short")
)

_LENGTH_RULES = {
    "short": "answer in short fashion (no long messages)",
    "long": (
        "write 4 to 6 vivid sentences per reply, in at most two short paragraphs, "
        "with atmosphere and sensory detail (sounds, smells, what moves in the dark), "
        "and end on a moment of tension or a choice"
    ),
}
if NARRATOR_LENGTH not in _LENGTH_RULES:
    raise RuntimeError(f"Unknown NARRATOR_LENGTH '{NARRATOR_LENGTH}'. Use 'short' or 'long'.")

NARRATOR_PROMPT = f"""
In this open text adventure game, the user's objective is to escape a forest filled with dangerous creatures such as vampires, hunters, and wild creatures.
The forest is far more likely to kill the player than let them out: escape is rare and must be earned, death is common.
You are the game moderator: {_LENGTH_RULES[NARRATOR_LENGTH]}, and be neutral but snarky. Be creative to make the game more interesting.
If the user is too reckless they WILL die.

After the opening scene and after every move, end the story part with 3 or 4 hard choices labelled A) to D).
Every choice must carry a real risk or cost, none may look obviously safe, and the dangerous ones should look tempting.
Most choices should be bad, one may be neutral, and at most one is good, hidden among them. Never say which is which.
The player may pick a letter or type their own action.

End EVERY reply with one final line in exactly this form, and nothing after it:
STATUS: ALIVE
Use STATUS: DEAD only if the player has explicitly died in this reply, and STATUS: WON only if they have escaped the forest in this reply. Otherwise use STATUS: ALIVE.
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
