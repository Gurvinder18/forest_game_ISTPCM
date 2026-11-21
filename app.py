import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv(override=True)  # must run before config reads model overrides; override so edits to .env win on reload
logging.basicConfig(level=logging.INFO)  # before module imports so their startup logs show

from config import MAX_HISTORY_TOKENS, NARRATOR_MODELS, NARRATOR_PROMPT, STATUS_MODELS, STATUS_PROMPT
from modules.conversation import trim_history
from modules.llm import classify_status, generate_reply
from modules.text_formatter import extract_status, format_reply

# Static files live in public/static so Vercel can serve them from its CDN.
# Locally, Flask serves the same folder at the same /static URLs.
app = Flask(__name__, static_folder="public/static", static_url_path="/static")

MAX_COMMAND_CHARS = 500
MAX_HISTORY_MESSAGES = 60
MAX_MESSAGE_CHARS = 4000


def clean_history(raw) -> list:
    """Validate the chat history the browser sends back.

    The server keeps no game state (serverless functions don't keep memory
    between requests), so the browser holds the history and sends it with
    every command. Only user/assistant turns are accepted; the system prompt
    is always added here on the server.
    """
    if not isinstance(raw, list):
        return []
    history = []
    for msg in raw[-MAX_HISTORY_MESSAGES:]:
        if (
            isinstance(msg, dict)
            and msg.get("role") in ("user", "assistant")
            and isinstance(msg.get("content"), str)
        ):
            history.append({"role": msg["role"], "content": msg["content"][:MAX_MESSAGE_CHARS]})
    return history


@app.route("/")
def home():
    """Render the start menu."""
    return render_template("menu.html")


@app.route("/terminal", methods=["GET", "POST"])
def terminal():
    """GET renders the game terminal; POST processes a player command."""
    if request.method == "GET":
        return render_template("terminal.html")

    data = request.get_json(silent=True)
    command = data.get("message") if isinstance(data, dict) else None
    if not isinstance(command, str) or not command.strip():
        logging.error("Invalid JSON data: %s", request.data[:200])
        return jsonify({"error": "Invalid JSON data"}), 400

    history = clean_history(data.get("history"))
    history.append({"role": "user", "content": command[:MAX_COMMAND_CHARS]})
    chat = trim_history([{"role": "system", "content": NARRATOR_PROMPT}] + history, MAX_HISTORY_TOKENS)

    try:
        # The narrator tags its own reply with the player's status, so most
        # turns need one AI call. Only if the tag is missing do we make a
        # second, separate classifier call.
        reply, status = extract_status(generate_reply(chat, NARRATOR_MODELS))
        reply = format_reply(reply)
        if status is None:
            logging.info("Narrator left out the status tag; using the classifier")
            status = classify_status(STATUS_PROMPT, reply, STATUS_MODELS)
    except Exception:
        logging.exception("AI request failed")
        return jsonify({"error": "The AI service is unavailable"}), 502

    logging.info("Player status: %s", status)
    return jsonify({"answer": reply, "status": status})


if __name__ == "__main__":
    app.run(debug=True)
