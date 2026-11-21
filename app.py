import json
import logging

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request

load_dotenv(override=True)  # must run before config reads model overrides; override so edits to .env win on reload
logging.basicConfig(level=logging.INFO)  # before module imports so their startup logs show

from config import MAX_HISTORY_TOKENS, NARRATOR_LENGTH, NARRATOR_MODELS, NARRATOR_PROMPT, STATUS_MODELS, STATUS_PROMPT
from modules.conversation import trim_history
from modules.llm import classify_status, generate_reply, stream_reply
from modules.text_formatter import StreamStatusFilter, extract_status, format_reply

# Static files live in public/static so Vercel can serve them from its CDN.
# Locally, Flask serves the same folder at the same /static URLs.
app = Flask(__name__, static_folder="public/static", static_url_path="/static")
logging.info("Narrator reply length: %s", NARRATOR_LENGTH)

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


def build_chat():
    """Turn a player command request into the chat to send to the AI.

    Returns (chat, None) or (None, error_response).
    """
    data = request.get_json(silent=True)
    command = data.get("message") if isinstance(data, dict) else None
    if not isinstance(command, str) or not command.strip():
        logging.error("Invalid JSON data: %s", request.data[:200])
        return None, (jsonify({"error": "Invalid JSON data"}), 400)

    history = clean_history(data.get("history"))
    history.append({"role": "user", "content": command[:MAX_COMMAND_CHARS]})
    chat = trim_history([{"role": "system", "content": NARRATOR_PROMPT}] + history, MAX_HISTORY_TOKENS)
    return chat, None


def finish_reply(raw_reply: str):
    """Split off the status tag and tidy the reply.

    The narrator tags its own reply with the player's status, so most turns
    need one AI call. Only if the tag is missing do we make a second,
    separate classifier call.
    """
    reply, status = extract_status(raw_reply)
    reply = format_reply(reply)
    if status is None:
        logging.info("Narrator left out the status tag; using the classifier")
        status = classify_status(STATUS_PROMPT, reply, STATUS_MODELS)
    logging.info("Player status: %s", status)
    return reply, status


@app.route("/")
def home():
    """Render the start menu."""
    return render_template("menu.html")


@app.route("/terminal", methods=["GET", "POST"])
def terminal():
    """GET renders the game terminal; POST processes a player command in one response."""
    if request.method == "GET":
        return render_template("terminal.html")

    chat, error = build_chat()
    if error:
        return error

    try:
        reply, status = finish_reply(generate_reply(chat, NARRATOR_MODELS))
    except Exception:
        logging.exception("AI request failed")
        return jsonify({"error": "The AI service is unavailable"}), 502

    return jsonify({"answer": reply, "status": status})


@app.route("/terminal/stream", methods=["POST"])
def terminal_stream():
    """Process a player command and stream the reply as it's written.

    The response is newline-delimited JSON:
      {"type": "chunk", "text": "..."}            pieces of the reply, as they arrive
      {"type": "done", "answer": "...", "status": "..."}  the final, cleaned-up reply
      {"type": "error", "error": "..."}           if the AI fails
    If a host buffers the response, the browser still gets every line, just
    all at once.
    """
    chat, error = build_chat()
    if error:
        return error

    def events():
        pieces = []
        status_filter = StreamStatusFilter()
        try:
            for piece in stream_reply(chat, NARRATOR_MODELS):
                pieces.append(piece)
                visible = status_filter.feed(piece)
                if visible:
                    yield json.dumps({"type": "chunk", "text": visible}) + "\n"
            visible = status_filter.finish()
            if visible:
                yield json.dumps({"type": "chunk", "text": visible}) + "\n"
            reply, status = finish_reply("".join(pieces))
            yield json.dumps({"type": "done", "answer": reply, "status": status}) + "\n"
        except Exception:
            logging.exception("AI request failed")
            yield json.dumps({"type": "error", "error": "The AI service is unavailable"}) + "\n"

    return Response(
        events(),
        mimetype="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True)
