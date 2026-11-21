# Forest Game

A terminal-style text adventure built for the ISTPCM group assignment. You wake up in a dangerous forest full of vampires, hunters and wild creatures, and the only way out is to talk your way through it. Google's Gemini models, through Google AI Studio, act as the narrator and decide whether you survive.

## Features

- AI narrator and win/lose detection powered by Gemini (Google AI Studio)
- Old-school computer terminal look and feel
- Open-ended gameplay: type anything, and the story reacts

## Technology Stack

- **Flask**: Python backend that serves the pages and relays player commands to the AI
- **Plain CSS**: terminal styling and text formatting
- **JavaScript**: terminal input, command history and async requests to the server
- **Gemini via Google AI Studio**: `gemini-3.5-flash-lite` narrates the game and `gemini-3.1-flash-lite` checks whether the player has won or died. If a model is rate-limited or overloaded, the app falls back to the next one (including `gemma-4-31b-it`), so the free tier gives roughly 500 turns a day

## Installation

You need Python 3.10 or newer. Download it [here](https://www.python.org/downloads/).

1. Clone the repository:

```bash
git clone https://github.com/Gurvinder18/forest_game_ISTPCM.git
```

2. Change to the project directory:

```bash
cd forest_game_ISTPCM
```

3. Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

4. Install the dependencies:

```bash
pip install -r requirements.txt
```

5. Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey). Copy `.env.example` to `.env` and paste the key in:

```bash
GEMINI_API_KEY=your_google_ai_studio_api_key
```

`.env` is git-ignored, so your key never gets committed.

6. Run the game:

```bash
python app.py
```

7. Open `http://127.0.0.1:5000/` in your browser.

### Optional: run with a local model (LM Studio)

Instead of calling Gemini, you can play against a model running on your own machine, with no API key and no rate limits. This only works locally; hosted deployments (like Vercel) must use Gemini.

1. Install [LM Studio](https://lmstudio.ai/) and download a small instruct model (for example Gemma 4 E4B).
2. In LM Studio's **Developer** tab, load the model and start the server (default `http://localhost:1234`).
3. In `.env`, set:

```bash
LLM_PROVIDER=lmstudio
```

4. Run `python app.py` as usual. Set `LMSTUDIO_MODEL` only if you have more than one model loaded.

### Running the tests

The tests replace the AI with a fake, so they run offline and use no API quota:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Deploying to Vercel

The same code runs locally and on Vercel. The server keeps no game state: the browser holds the story so far and sends it with each command, which is what serverless functions need. Static files live in `public/static/`, so Vercel serves them from its CDN while Flask serves the same folder locally.

1. Import this GitHub repo as a new project on [Vercel](https://vercel.com/new). It detects Flask from `app.py`; no build settings are needed.
2. Under **Settings → Environment Variables**, add `GEMINI_API_KEY`. Optionally add `NARRATOR_MODELS` and `STATUS_MODELS`.
3. Deploy. Every push to `main` redeploys automatically.

`vercel.json` gives each request up to 60 seconds, and `.python-version` pins Python 3.12. Leave `LLM_PROVIDER` unset (Gemini) on Vercel, because it can't reach an LM Studio server on your laptop.

## How to Play

- Type `help` for a list of available commands.
- Type `start` to begin.
- Type what you want to do and press `enter`.
- Think before you act. Reckless players don't make it out.
- To use different models, set `NARRATOR_MODELS` or `STATUS_MODELS` in `.env` as comma-separated lists, tried in order.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Author

Maintained by **Gurvinder Singh**.