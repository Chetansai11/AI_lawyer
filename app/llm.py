from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

_ROOT = Path(__file__).resolve().parent.parent
_DOTENV_LOADED = False
_client: genai.Client | None = None


def _load_dotenv() -> None:
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(_ROOT / ".env")
    except ImportError:
        pass
    _DOTENV_LOADED = True


def get_gemini_model() -> str:
    _load_dotenv()
    raw = (os.getenv("GEMINI_MODEL") or "").strip()
    if not raw:
        return "models/gemini-2.0-flash-lite"
    lower = raw.lower()
    # Accept friendly aliases and normalize to full model IDs.
    aliases = {
        "gemma-3-27b": "models/gemma-3-27b-it",
        "gemma 3 27b": "models/gemma-3-27b-it",
        "gemma-3-27b-it": "models/gemma-3-27b-it",
        "gemini-2.0-flash-lite": "models/gemini-2.0-flash-lite",
    }
    if lower in aliases:
        return aliases[lower]
    if lower.startswith("models/"):
        return raw
    return f"models/{raw}"


def get_client() -> genai.Client | None:
    global _client
    _load_dotenv()
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return None
    if _client is None:
        _client = genai.Client(api_key=key)
    return _client


_load_dotenv()


def _optional_temperature() -> dict[str, float]:
    """Omit param unless user sets GEMINI_TEMPERATURE."""
    _load_dotenv()
    raw = (os.getenv("GEMINI_TEMPERATURE") or "").strip()
    if not raw:
        return {}
    try:
        return {"temperature": float(raw)}
    except ValueError:
        return {}


def _supports_system_instruction(model: str) -> bool:
    return not model.lower().startswith("models/gemma")


def _compose_contents(system: str, user: str) -> str:
    return f"System instructions:\n{system}\n\nUser message:\n{user}"


def _json_from_text(raw: str) -> dict[str, Any]:
    s = (raw or "").strip()
    if not s:
        raise ValueError("empty model response")
    try:
        val = json.loads(s)
        if isinstance(val, dict):
            return val
    except Exception:
        pass
    # Fallback: extract first JSON object block from mixed text.
    match = re.search(r"\{.*\}", s, flags=re.DOTALL)
    if not match:
        raise ValueError("no JSON object found")
    val = json.loads(match.group(0))
    if not isinstance(val, dict):
        raise ValueError("JSON is not an object")
    return val


async def chat_json(system: str, user: str) -> dict:
    """Call Gemini; response must be a JSON object."""
    client = get_client()
    if not client:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = get_gemini_model()

    def _call() -> dict[str, Any]:
        cfg_kwargs: dict[str, Any] = {**_optional_temperature()}
        if _supports_system_instruction(model):
            cfg_kwargs["response_mime_type"] = "application/json"
            cfg_kwargs["system_instruction"] = system
            contents = user
        else:
            # Gemma does not support JSON mode; force JSON via prompt.
            contents = (
                _compose_contents(system, user)
                + "\n\nReturn ONLY a valid JSON object (no prose, no markdown fences)."
            )
        cfg = types.GenerateContentConfig(**cfg_kwargs)
        out = client.models.generate_content(model=model, contents=contents, config=cfg)
        raw = (out.text or "").strip() or "{}"
        return _json_from_text(raw)

    return await asyncio.to_thread(_call)


async def chat_text(system: str, user: str, *, max_tokens: int = 400) -> str:
    """Plain-text chat completion (Gemini)."""
    client = get_client()
    if not client:
        raise RuntimeError("GEMINI_API_KEY is not set")
    model = get_gemini_model()

    def _call() -> str:
        cfg_kwargs: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            **_optional_temperature(),
        }
        if _supports_system_instruction(model):
            cfg_kwargs["system_instruction"] = system
            contents = user
        else:
            contents = _compose_contents(system, user)
        cfg = types.GenerateContentConfig(**cfg_kwargs)
        out = client.models.generate_content(model=model, contents=contents, config=cfg)
        return (out.text or "").strip()

    return await asyncio.to_thread(_call)
