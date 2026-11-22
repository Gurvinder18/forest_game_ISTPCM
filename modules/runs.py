"""Run rules: each run lasts 8-10 player moves and may hide one easter egg.

The server is stateless, so the run is chosen when the game starts and the
browser sends it back with every move. Anything it sends is re-validated here.
"""

import hashlib
import json
import random
import re

MIN_MOVES = 8
MAX_MOVES = 10
EGG_CHANCE = 0.05  # per easter egg; at most one egg per run

# The forest is deadly: each move the server rolls whether the player dies,
# depending on how the narrator rates their decision. Escape on the final move
# needs more GOOD than BAD decisions AND a lucky roll.
DEATH_CHANCE = {"BAD": 0.45, "NEUTRAL": 0.15, "GOOD": 0.04}
ESCAPE_CHANCE = 0.4

# Hidden quality of each A-D option the narrator offers, drawn per option.
CHOICE_SHARES = {"BAD": 0.60, "NEUTRAL": 0.25, "GOOD": 0.15}
NUM_CHOICES = 4
_DECISION_TAG = re.compile(r"\[\s*Decision\s*:\s*(GOOD|NEUTRAL|BAD)\b", re.IGNORECASE)

EASTER_EGGS = {
    "bigfoot": {
        "title": "Bigfoot to the rescue",
        "status": "WON",
        "foreshadow": (
            "Subtly foreshadow a huge, hairy, surprisingly gentle creature watching the player from the trees: "
            "giant footprints, a musky smell, a distant friendly grunt. Don't reveal what it is yet."
        ),
        "ending": (
            "Bigfoot steps out of the trees and helps the player escape the forest: carrying them, scaring off "
            "threats, or showing them a secret path. Make it a fun, triumphant ending. The player has WON."
        ),
    },
    "vampire": {
        "title": "A friendly vampire from Hotel Transylvania",
        "status": "WON",
        "foreshadow": (
            "Subtly foreshadow a vampire who is oddly polite and hospitable rather than hungry: a bow, an offer "
            "of directions, complaints about bad guest reviews. Keep the player unsure whether to trust him."
        ),
        "ending": (
            "The vampire reveals he runs the guest experience at Hotel Transylvania, is mortified by the "
            "forest's terrible hospitality, and personally guides the player out. Make it a warm, funny "
            "ending. The player has WON."
        ),
    },
    "dream": {
        "title": "It was all a dream",
        "status": "DREAM",
        "foreshadow": (
            "Let small things feel slightly unreal: the same tree twice, the sky the wrong color for a moment, "
            "a sound like an alarm clock far away. Don't explain it."
        ),
        "ending": (
            "The player suddenly wakes up in their own bed: the whole forest was a dream. Describe waking up, "
            "tangled in sheets, maybe with one odd detail from the dream still there. Neither victory nor "
            "death: it was a dream."
        ),
    },
}


def new_run(rng=random):
    """Pick a move limit and maybe one easter egg (5% each, never two)."""
    roll = rng.random()
    egg = None
    for i, name in enumerate(EASTER_EGGS):
        # round() avoids float drift (0.05 * 3 is 0.15000000000000002)
        if roll < round(EGG_CHANCE * (i + 1), 10):
            egg = name
            break
    return {"max_moves": rng.randint(MIN_MOVES, MAX_MOVES), "egg": egg}


def validate_run(raw):
    """Return the run the browser sent back, or None if it's not valid."""
    if not isinstance(raw, dict):
        return None
    max_moves = raw.get("max_moves")
    egg = raw.get("egg")
    if not isinstance(max_moves, int) or isinstance(max_moves, bool) or not MIN_MOVES <= max_moves <= MAX_MOVES:
        return None
    if egg is not None and egg not in EASTER_EGGS:
        return None
    return {"max_moves": max_moves, "egg": egg}


def decision_tally(history) -> dict:
    """Count the narrator's earlier [Decision: ...] ratings in the chat history."""
    tally = {"GOOD": 0, "NEUTRAL": 0, "BAD": 0}
    for msg in history or []:
        if msg.get("role") == "assistant":
            for m in _DECISION_TAG.finditer(msg.get("content", "")):
                tally[m.group(1).upper()] += 1
    return tally


def choice_labels(run: dict, commands) -> list:
    """The hidden BAD/NEUTRAL/GOOD label of each option offered after `commands`.

    Seeded from the run and the player's commands so the next move can
    recompute exactly which labels the previous options had.
    """
    key = json.dumps([run["max_moves"], run["egg"], list(commands)])
    rng = random.Random(hashlib.sha256(key.encode("utf-8")).hexdigest())
    ratings, weights = zip(*CHOICE_SHARES.items())
    return rng.choices(ratings, weights=weights, k=NUM_CHOICES)


def _labelled(labels) -> str:
    names = ["first", "second", "third", "fourth"]
    return ", ".join(f"{name} {label}" for name, label in zip(names, labels))


def decision_score(tally: dict) -> int:
    return tally["GOOD"] - 2 * tally["BAD"]


def roll_fate(run: dict, move: int, tally: dict, rng=random):
    """Decide this move's outcome before the narrator writes it.

    Returns None for the opening scene and egg runs, {"BAD": bool, ...}
    (True = the player dies if their action gets that rating) for normal
    moves, and "WON" or "DEAD" for the final move.
    """
    if move == 0 or run["egg"]:
        return None
    if move >= run["max_moves"]:
        earned = tally["GOOD"] > tally["BAD"]
        return "WON" if earned and rng.random() < ESCAPE_CHANCE else "DEAD"
    return {rating: rng.random() < chance for rating, chance in DEATH_CHANCE.items()}


RATING_RULES = (
    "Start your reply with ONE line rating the player's latest decision, exactly like "
    "'[Decision: BAD (-2)]', '[Decision: NEUTRAL (0)]' or '[Decision: GOOD (+1)]'. Be harsh: this forest "
    "punishes mistakes, so most decisions are BAD, some are NEUTRAL, and GOOD is only for genuinely clever, "
    "careful, well-informed choices. Rushing, making noise, trusting strangers, leaving cover, "
    "touching unknown things or picking fights are BAD."
)


def stage_instructions(run: dict, move: int, tally=None, fate=None, prev_labels=None, next_labels=None) -> str:
    """Extra narrator instructions for this point in the run.

    Move 0 is the opening scene; moves 1..max_moves are the player's actions,
    and the last one always ends the story.
    """
    max_moves = run["max_moves"]
    egg = EASTER_EGGS.get(run["egg"])
    left = max_moves - move

    offer = (
        f"SECRET quality of the 4 courses of action you weave into the end of this reply, in the order they appear: "
        f"{_labelled(next_labels)}. Write each to match its quality (BAD ones should still look tempting), "
        "and never reveal the labels."
        if next_labels else ""
    )

    if move == 0:
        return "\n".join(filter(None, ["This is the opening scene. Set the scene and ask what the player does.", offer]))

    lines = [f"This is the player's move {move} of {max_moves}.", RATING_RULES]
    if prev_labels:
        lines.append(
            f"The courses of action you offered last time, in the order they appeared, were secretly: "
            f"{_labelled(prev_labels)}. If the player chose one of them, rate their decision with exactly that "
            "label; if they did something else, rate it yourself."
        )
    if tally is not None:
        lines.append(
            f"Their decisions so far: {tally['GOOD']} good, {tally['NEUTRAL']} neutral, {tally['BAD']} bad "
            f"(score {decision_score(tally)})."
        )
    if left == 0:
        lines.append(
            "This is the FINAL move. End the story in this reply. Do NOT ask what the player does next."
        )
        if egg:
            lines.append(egg["ending"])
        elif fate == "WON":
            lines.append(
                "Fate has decided: the player narrowly ESCAPES the forest, battered and barely alive. "
                "End with STATUS: WON."
            )
        elif fate == "DEAD":
            lines.append(
                "Fate has decided: the player DIES here. Make the death follow from their choices "
                "and the forest's dangers. End with STATUS: DEAD."
            )
        else:
            lines.append(
                "Based on how wisely the player has acted so far, they either escape the forest (STATUS: WON) "
                "or die (STATUS: DEAD). Careful, clever play should usually be rewarded with escape; "
                "reckless play with death."
            )
        return "\n".join(lines)

    if egg:
        lines.append(
            "In this run the player must NOT die or escape before the final move: give them close calls "
            "and narrow escapes instead, and use STATUS: ALIVE."
        )
        if left <= 3:
            lines.append(egg["foreshadow"])
    else:
        lines.append("The player can only escape on the final move.")
        if isinstance(fate, dict):
            outcomes = "; ".join(
                f"if you rate it {r}, the player "
                + ("DIES in this reply (STATUS: DEAD)" if dies else "survives but is worse off (STATUS: ALIVE)")
                for r, dies in fate.items()
            )
            lines.append(f"Fate is already decided by the dice: {outcomes}. Follow this exactly.")
        else:
            lines.append("Death comes easily here: reckless or careless players die.")
    if left == 1:
        lines.append("The next move is the last one: build toward a climax.")
    if offer:
        lines.append(offer)
    return "\n".join(lines)


def final_status(run: dict, move: int, status: str, fate=None) -> str:
    """Make sure the final move always ends the run the way the rules say."""
    if move < run["max_moves"]:
        return status
    egg = EASTER_EGGS.get(run["egg"])
    if egg:
        return egg["status"]
    if fate in ("WON", "DEAD"):
        return fate
    return status if status in ("WON", "DEAD") else "DEAD"


def revealed_egg(run: dict, move: int):
    """The easter egg to announce, once its ending has played out."""
    if run["egg"] and move >= run["max_moves"]:
        return {"id": run["egg"], "title": EASTER_EGGS[run["egg"]]["title"], "total": len(EASTER_EGGS)}
    return None
