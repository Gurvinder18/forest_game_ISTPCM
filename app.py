import logging

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv(override=True)  # must run before config reads model overrides; override so edits to .env win on reload
logging.basicConfig(level=logging.INFO)  # before module imports so their startup logs show

from config import MAX_HISTORY_TOKENS, NARRATOR_MODELS, NARRATOR_PROMPT, STATUS_MODELS, STATUS_PROMPT
from modules.conversation import trim_history
from modules.llm import classify_status, generate_reply
from modules.text_formatter import format_reply

app = Flask(__name__)


def new_history() -> list:
    return [{"role": "system", "content": NARRATOR_PROMPT}]


chat_history = new_history()


@app.route("/")
def home():
    """Render the start menu."""
    return render_template("menu.html")


@app.route("/terminal", methods=["GET", "POST"])
def terminal():
    """GET renders the game terminal; POST processes a player command."""
    global chat_history

    if request.method == "GET":
        chat_history = new_history()  # fresh game on every page load
        return render_template("terminal.html")

    try:
        command = request.get_json(silent=True)["message"]
    except (KeyError, TypeError):
        logging.error("Invalid JSON data: %s", request.data)
        return jsonify({"error": "Invalid JSON data"}), 400

    chat_history.append({"role": "user", "content": command})
    chat_history = trim_history(chat_history, MAX_HISTORY_TOKENS)

    try:
        reply = format_reply(generate_reply(chat_history, NARRATOR_MODELS))
        chat_history.append({"role": "assistant", "content": reply})
        status = classify_status(STATUS_PROMPT, reply, STATUS_MODELS)
    except Exception:
        logging.exception("Gemini request failed")
        chat_history.pop()  # drop the unanswered command
        return jsonify({"error": "The AI service is unavailable"}), 502

    logging.info("Player status: %s", status)
    return jsonify({"answer": reply, "status": status})


if __name__ == "__main__":
    app.run(debug=True)
