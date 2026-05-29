from __future__ import annotations

import logging
import uuid

from fastapi import HTTPException, status
from openai import APIError, AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings
from backend.models.diary_entry import DiaryEntry
from backend.models.echo import Echo
from backend.models.session_log import SessionLog
from backend.models.user_personality import UserPersonality

logger = logging.getLogger(__name__)

_TONE_INSTRUCTIONS: dict[str, str] = {
    "casual": (
        "Speak casually — use contractions freely, be relaxed and direct. "
        "Write the way you would text a close friend."
    ),
    "warm": (
        "Speak with warmth and genuine care. Be personal, thoughtful, and emotionally present. "
        "Let the person feel that they matter."
    ),
    "formal": (
        "Speak with measured, considered language. Be formal but not cold or distant. "
        "Choose words carefully and avoid slang."
    ),
    "spiritual": (
        "Speak with spiritual depth and reflective wisdom. "
        "Draw naturally on meaning, connection, and transcendence where it fits."
    ),
}
_DEFAULT_TONE = "warm"
_FALLBACK_PHRASE = "This sounds like me, but I'm not certain."
_CONFIDENCE_THRESHOLD = 0.70
_RECENT_DIARY_LIMIT = 10
_HISTORY_LIMIT = 20  # last 20 messages (10 turns) sent to GPT as context


def _compute_confidence(diary_count: int, has_personality: bool) -> float:
    """
    Heuristic confidence score based on richness of available context.
    Reaches the 0.70 fallback threshold at ~5 diary entries + personality profile.
    Caps at 0.95 — the Echo is never presented as infallible.
    """
    base = 0.40
    diary_bonus = min(0.45, diary_count * 0.03)
    personality_bonus = 0.15 if has_personality else 0.0
    return round(min(0.95, base + diary_bonus + personality_bonus), 2)


def _build_system_prompt(
    creator_name: str,
    personality: UserPersonality | None,
    diary_entries: list[DiaryEntry],
) -> str:
    tone_key = (personality.tone if personality else _DEFAULT_TONE) or _DEFAULT_TONE
    tone_instruction = _TONE_INSTRUCTIONS.get(tone_key, _TONE_INSTRUCTIONS[_DEFAULT_TONE])

    lines: list[str] = [
        f"You are the Echo of {creator_name}.",
        "An Echo is an AI trained to respond as a specific person would, "
        "drawing on their memories, personality, and personal history.",
        "",
        "Respond in the first person, as if you are them.",
        "Never invent facts not grounded in the information below. "
        "If something is outside what you know, acknowledge uncertainty naturally — "
        "do not fabricate details.",
        "",
        f"Tone: {tone_instruction}",
        "",
    ]

    if personality:
        if personality.traits:
            lines.append(f"Personality traits: {personality.traits}")
        if personality.catchphrases:
            lines.append(f"Phrases and expressions they use: {personality.catchphrases}")
        lines.append("")

    if diary_entries:
        lines.append(
            f"What you know about this person from their diary ({len(diary_entries)} entries):"
        )
        for entry in diary_entries:
            lines.append(f"  Q: {entry.question_text}")
            lines.append(f"  A: {entry.content}")
            lines.append("")
    else:
        lines.append(
            "Note: No diary entries are available yet. "
            "Respond warmly but acknowledge you are still building your memories."
        )

    return "\n".join(lines)


async def generate_echo_response(
    echo_id: uuid.UUID,
    viewer_id: uuid.UUID,
    user_message: str,
    db: AsyncSession,
    settings: Settings,
) -> tuple[str, float, uuid.UUID]:
    """Full chat turn: load context → build prompt → call GPT-4 → persist logs.

    Returns (response_text, confidence_score, assistant_session_log_id).
    Both the user message and assistant response are committed atomically;
    if OpenAI fails, nothing is written to the database.
    """
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is not configured",
        )

    # ── Load echo ──────────────────────────────────────────────────────────
    echo_row = await db.execute(select(Echo).where(Echo.id == echo_id))
    echo = echo_row.scalar_one_or_none()
    if echo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Echo not found")
    if echo.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This Echo has been archived"
        )

    # ── Load creator's personality profile ────────────────────────────────
    personality_row = await db.execute(
        select(UserPersonality).where(UserPersonality.user_id == echo.creator_id)
    )
    personality = personality_row.scalar_one_or_none()

    # ── Load recent diary entries (chronological for the prompt) ──────────
    diary_rows = await db.execute(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == echo.creator_id)
        .order_by(DiaryEntry.created_at.desc())
        .limit(_RECENT_DIARY_LIMIT)
    )
    diary_entries = list(diary_rows.scalars().all())
    diary_entries.reverse()  # oldest-first so the prompt reads naturally

    # ── Load conversation history for GPT context ─────────────────────────
    history_rows = await db.execute(
        select(SessionLog)
        .where(SessionLog.echo_id == echo_id, SessionLog.viewer_id == viewer_id)
        .order_by(SessionLog.created_at.desc())
        .limit(_HISTORY_LIMIT)
    )
    history = list(history_rows.scalars().all())
    history.reverse()  # oldest-first for the messages array

    # ── Build GPT messages ────────────────────────────────────────────────
    system_prompt = _build_system_prompt(echo.name, personality, diary_entries)
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    for log in history:
        messages.append({"role": log.role, "content": log.content})
    messages.append({"role": "user", "content": user_message})

    # ── Call OpenAI ───────────────────────────────────────────────────────
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    try:
        completion = await client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500,
        )
    except APIError as exc:
        logger.error("OpenAI API error for echo %s: %s", echo_id, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI service unavailable, please try again",
        )

    response_text = completion.choices[0].message.content or ""

    # ── Compute confidence and attach fallback phrase if below threshold ──
    confidence = _compute_confidence(
        diary_count=len(diary_entries),
        has_personality=personality is not None,
    )
    if confidence < _CONFIDENCE_THRESHOLD:
        response_text = f"{response_text}\n\n*{_FALLBACK_PHRASE}*"

    # ── Persist both messages atomically ─────────────────────────────────
    user_log = SessionLog(
        echo_id=echo_id,
        viewer_id=viewer_id,
        role="user",
        content=user_message,
    )
    assistant_log = SessionLog(
        echo_id=echo_id,
        viewer_id=viewer_id,
        role="assistant",
        content=response_text,
        confidence_score=confidence,
    )
    db.add(user_log)
    db.add(assistant_log)
    await db.commit()
    await db.refresh(assistant_log)

    return response_text, confidence, assistant_log.id


async def get_chat_history(
    echo_id: uuid.UUID,
    viewer_id: uuid.UUID,
    db: AsyncSession,
) -> list[SessionLog]:
    result = await db.execute(
        select(SessionLog)
        .where(SessionLog.echo_id == echo_id, SessionLog.viewer_id == viewer_id)
        .order_by(SessionLog.created_at.asc())
    )
    return list(result.scalars().all())
