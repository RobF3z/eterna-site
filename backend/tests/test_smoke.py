from __future__ import annotations

"""
Smoke test: full user journey from registration through to a chat response.

Steps that have HTTP routes go via the client; Echo and UserPersonality are
inserted directly because those creation routes have not been built yet.
Replace the direct-DB blocks with HTTP calls once the routes exist.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.echo import Echo
from backend.models.user_personality import UserPersonality


async def test_register_login_diary_chat(
    client: AsyncClient,
    db: AsyncSession,
    mock_openai,
) -> None:
    # ── 1. Register ───────────────────────────────────────────────────────
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": "alice@example.com", "password": "password123", "full_name": "Alice Test"},
    )
    assert r.status_code == 201, r.text
    user_id = uuid.UUID(r.json()["id"])

    # ── 2. Login ──────────────────────────────────────────────────────────
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "password123"},
    )
    assert r.status_code == 200, r.text
    auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # ── 3. /me round-trip ─────────────────────────────────────────────────
    r = await client.get("/api/v1/auth/me", headers=auth)
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"

    # ── 4. Get daily prompt ───────────────────────────────────────────────
    r = await client.get("/api/v1/diary/prompt", headers=auth)
    assert r.status_code == 200
    prompt = r.json()
    assert prompt["question_index"] == 0  # first-ever prompt starts at 0
    assert prompt["question_text"] != ""

    # ── 5. Submit diary entry ─────────────────────────────────────────────
    r = await client.post(
        "/api/v1/diary",
        json={"question_index": 0, "content": "Playing in the garden — the smell of cut grass."},
        headers=auth,
    )
    assert r.status_code == 201, r.text
    entry = r.json()
    assert entry["question_index"] == 0
    assert entry["content"] == "Playing in the garden — the smell of cut grass."

    # ── 6. Next prompt advances to index 1 ───────────────────────────────
    r = await client.get("/api/v1/diary/prompt", headers=auth)
    assert r.json()["question_index"] == 1

    # ── 7. Create Echo (direct DB — replace with HTTP once route is built) ─
    echo = Echo(creator_id=user_id, name="Alice", status="active")
    db.add(echo)
    await db.flush()  # assigns echo.id within the transaction

    # ── 8. Set personality profile (direct DB — same) ────────────────────
    personality = UserPersonality(
        user_id=user_id,
        traits="warm, curious, direct",
        tone="warm",
        catchphrases="absolutely, that's the thing isn't it",
    )
    db.add(personality)
    await db.commit()  # SAVEPOINT commit — visible to subsequent queries

    # ── 9. Chat ───────────────────────────────────────────────────────────
    r = await client.post(
        f"/api/v1/chat/{echo.id}",
        json={"message": "What is your earliest memory?"},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    chat = r.json()

    assert "id" in chat
    assert "response" in chat
    assert "confidence_score" in chat

    # 1 diary entry + personality → 0.40 + 0.03 + 0.15 = 0.58
    assert chat["confidence_score"] == pytest.approx(0.58, abs=0.01)
    assert 0.0 < chat["confidence_score"] < 1.0

    # Confidence < 0.70 → fallback phrase appended
    assert "not certain" in chat["response"].lower()

    # OpenAI was called exactly once
    mock_openai.chat.completions.create.assert_awaited_once()
    call_messages = mock_openai.chat.completions.create.call_args.kwargs["messages"]
    assert call_messages[0]["role"] == "system"
    assert "Alice" in call_messages[0]["content"]
    assert call_messages[-1]["role"] == "user"
    assert call_messages[-1]["content"] == "What is your earliest memory?"

    # ── 10. History ───────────────────────────────────────────────────────
    r = await client.get(f"/api/v1/chat/{echo.id}/history", headers=auth)
    assert r.status_code == 200, r.text
    history = r.json()

    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "What is your earliest memory?"
    assert history[0]["confidence_score"] is None  # only set on assistant turns

    assert history[1]["role"] == "assistant"
    assert history[1]["confidence_score"] == pytest.approx(0.58, abs=0.01)
    assert history[1]["confidence_score"] < 0.70
