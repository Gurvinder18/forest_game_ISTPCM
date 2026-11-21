"""Run rules: each run lasts 8-10 player moves and may hide one easter egg.

The server is stateless, so the run is chosen when the game starts and the
browser sends it back with every move. Anything it sends is re-validated here.
"""

import random

MIN_MOVES = 8
MAX_MOVES = 10
EGG_CHANCE = 0.05  # per easter egg; at most one egg per run

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


def stage_instructions(run: dict, move: int) -> str:
    """Extra narrator instructions for this point in the run.

    Move 0 is the opening scene; moves 1..max_moves are the player's actions,
    and the last one always ends the story.
    """
    max_moves = run["max_moves"]
    egg = EASTER_EGGS.get(run["egg"])
    left = max_moves - move

    if move == 0:
        return "This is the opening scene. Set the scene and ask what the player does."

    lines = [f"This is the player's move {move} of {max_moves}."]
    if left == 0:
        lines.append(
            "This is the FINAL move. End the story in this reply. Do NOT ask what the player does next."
        )
        if egg:
            lines.append(egg["ending"])
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
        lines.append(
            "The player can only escape on the final move, but may die earlier if they are truly reckless."
        )
    if left == 1:
        lines.append("The next move is the last one: build toward a climax.")
    return "\n".join(lines)


def final_status(run: dict, move: int, status: str) -> str:
    """Make sure the final move always ends the run the way the rules say."""
    if move < run["max_moves"]:
        return status
    egg = EASTER_EGGS.get(run["egg"])
    if egg:
        return egg["status"]
    return status if status in ("WON", "DEAD") else "DEAD"


def revealed_egg(run: dict, move: int):
    """The easter egg to announce, once its ending has played out."""
    if run["egg"] and move >= run["max_moves"]:
        return {"id": run["egg"], "title": EASTER_EGGS[run["egg"]]["title"], "total": len(EASTER_EGGS)}
    return None
