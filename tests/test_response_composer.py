from __future__ import annotations

import pytest

from app.state import empty_conversational_state
from app.utils.response_composer import COMPLETE_MESSAGE, generate_human_response


@pytest.mark.asyncio
async def test_generate_human_response_empty_question_returns_complete_message() -> None:
    st = empty_conversational_state()
    st["next_question"] = ""
    assert await generate_human_response(st, llm=None) == COMPLETE_MESSAGE


@pytest.mark.asyncio
async def test_generate_human_response_uses_injected_llm() -> None:
    st = empty_conversational_state()
    st["conversation"] = [{"role": "user", "content": "I fell at a store."}]
    st["next_question"] = "What date did this happen?"

    async def fake_llm(prompt: str) -> str:
        assert "What date did this happen?" in prompt
        assert "USER:" in prompt or "user" in prompt.lower()
        return "Sounds rough — hope you're okay.\n\nWhat date did this happen?"

    text = await generate_human_response(st, llm=fake_llm)
    assert "What date did this happen?" in text
    assert "Sounds rough" in text


@pytest.mark.asyncio
async def test_generate_human_response_fallback_on_llm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    st = empty_conversational_state()
    st["conversation"] = [{"role": "user", "content": "hi"}]
    st["next_question"] = "Where did it happen?"

    async def boom(_system: str, _user: str) -> str:
        raise RuntimeError("no api")

    monkeypatch.setattr("app.utils.response_composer.chat_text", boom)
    text = await generate_human_response(st, llm=None)
    assert "Where did it happen?" in text
    assert len(text) > 15
