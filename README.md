# AI Intake Auditor

AI Intake Auditor is an interview-style demo: a **multi-turn chat** on the left and a **live Markdown attorney brief** on the right. Orchestration is **async Python**: **scribe** → **parallel** (auditor + matcher + researcher) → **compose assistant reply**. (We avoid `LangGraph.ainvoke` here because its dict merge was **dropping accumulated `logs`** from earlier steps.)

> Folder on disk: `AI_Auditor/`.

## Screenshots

![AI Intake Auditor — UI overview](img1.png)

![AI Intake Auditor — chat and live brief](img2.png)

![AI Intake Auditor — intake flow](img3.png)

## Features

- **Stateful conversation** with server-side sessions (`session_id`)
- **SCRIBE**: incremental fact extraction from the full transcript
- **AUDITOR**: assumptions, risk, **case readiness score (1–10)**, and **`off_topic` detection** — small talk or unrelated turns get a polite redirect to case-only details (LLM + heuristics)
- **MATCHER**: ranks attorneys from `data/lawyers.json` (multi-practice roster); **top 6** matches in the API/UI
- **RESEARCHER** (runs **in parallel** with auditor + matcher): plausibility triage, **illustrative case themes** for the brief (LLM when configured, typed fallbacks otherwise) — not caselaw or legal advice
- **Gaps helper** (`effective_missing_fields`): brief and replies use **fact-based** gaps so “complete” is not shown while fields are still empty
- **FastAPI**: `POST /chat` (primary), `POST /analyze` (one-shot), `GET /welcome`, and a **React** single-page UI at `/`
- **Web UI**: intake chat and live brief use **in-panel scrolling** so long threads stay usable on one screen

## Project structure

```text
AI_Auditor/
├── app/
│   ├── main.py              # FastAPI: /health, /chat, /analyze
│   ├── controller.py        # handle_message: append user, run graph, compose reply
│   ├── graph.py             # Async pipeline: scribe → parallel → compose reply
│   ├── state.py             # ConversationalState schema
│   ├── llm.py               # Gemini chat helper (text + JSON)
│   ├── agents/
│   │   ├── scribe.py
│   │   ├── auditor.py
│   │   ├── matcher.py
│   │   ├── researcher.py
│   ├── utils/
│   │   ├── prompts.py
│   │   ├── formatter.py   # Markdown brief (right panel)
│   │   ├── logger.py
├── ui/
│   ├── index.html           # Web UI shell
│   ├── static/
│   │   ├── App.jsx      # React UI (Babel in-browser)
│   │   ├── app.css
│   │   └── app.js
├── data/
│   ├── lawyers.json
├── tests/                   # pytest unit tests
├── requirements.txt
├── requirements-dev.txt     # pytest, ruff
├── pyproject.toml           # ruff + pytest config
├── Dockerfile               # container image for Railway / Docker
├── railway.toml             # Railway: Docker build + /health
├── README.md
```

## Conversational state (persistent)

```json
{
  "conversation": [{ "role": "user|assistant", "content": "..." }],
  "extracted_facts": {
    "location": "",
    "date": "",
    "incident_type": "",
    "injuries": ""
  },
  "missing_fields": [],
  "assumptions": [],
  "risk_analysis": "",
  "case_score": 0.0,
  "lawyer_matches": [],
  "next_question": "",
  "confidence_score": 0.0,
  "plausibility": "",
  "researcher_reasoning": "",
  "case_research_summary": "",
  "off_topic": false,
  "logs": []
}
```

## Setup

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure Gemini (optional; heuristics apply if the key is missing or the API errors):

   - Copy `.env.example` to `.env` and set `GEMINI_API_KEY`.
   - Optional: `GEMINI_MODEL`, `GEMINI_TEMPERATURE`.

3. Run the API (and built-in web UI):

```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

4. Open:

   - **App:** <http://127.0.0.1:8000/>
   - API docs: <http://127.0.0.1:8000/docs>

## Deploy on Railway

The repo includes a **`Dockerfile`**, **`railway.toml`** (Docker build + `/health` check), and **`.dockerignore`**.

### One-time setup

1. Create a [Railway](https://railway.app/) account and install the [Railway CLI](https://docs.railway.app/develop/cli) (optional; the web UI is enough).
2. **New project** → **Deploy from GitHub repo** → select this repository.
3. Railway will detect the Dockerfile and build the image.

### Environment variables

In the Railway service → **Variables**, add at least:

| Variable | Required | Notes |
|----------|----------|--------|
| `GEMINI_API_KEY` | Yes (for real LLM) | Same as local `.env` |
| `GEMINI_MODEL` | No | Optional override |
| `GEMINI_TEMPERATURE` | No | Optional |

Railway injects **`PORT`** automatically; the container listens on `0.0.0.0` using that port.

### Deploy flow

- **GitHub:** Push to `main` (or your connected branch) → Railway rebuilds and redeploys.
- **CLI (optional):** `railway login` → `railway link` in the project folder → `railway up` for deploys.

### After deploy

- Open the **public URL** Railway assigns (Settings → Networking → generate domain if needed).
- Health: `https://<your-domain>/health` should return JSON.

### Local Docker check (optional)

```bash
docker build -t ai-intake-auditor .
docker run --rm -p 8000:8000 -e GEMINI_API_KEY=your_key -e PORT=8000 ai-intake-auditor
```

Then visit <http://127.0.0.1:8000/>.

**Note:** Chat sessions are stored **in memory** on one instance. For a single Railway instance this is fine for demos; scale-out would need shared storage (e.g. Redis).

## API

### `POST /chat` (primary)

Request:

```json
{
  "message": "I slipped in a Dallas store yesterday and hurt my wrist.",
  "session_id": null
}
```

Response:

```json
{
  "reply": "...",
  "brief": "## Attorney Brief\\n...",
  "logs": ["..."],
  "session_id": "uuid-returned-by-server"
}
```

Send the same `session_id` on subsequent turns to continue the conversation.

### `POST /analyze` (one-shot)

Single user message, full pipeline, Markdown brief (no session).

## Development

Install dev tools:

```bash
pip install -r requirements-dev.txt
```

Run tests:

```bash
python -m pytest
```

Lint with Ruff:

```bash
python -m ruff check app tests
```

Optional format:

```bash
python -m ruff format app tests
```

## Notes

- **Research output** is **illustrative** (general patterns, disclaimers in the brief). It is **not** a substitute for research counsel or authoritative citations.
- **Off-topic** turns are steered back to intake facts; the assistant does not engage unrelated chitchat as the main task.
- Assistant replies are composed **after** `run_pipeline` via `response_composer` (natural phrasing from `next_question`, including off-topic redirects).
- Sessions are **in-memory** per server process — fine for a single-instance demo; use Redis or a DB if you scale horizontally.
