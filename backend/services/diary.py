from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.diary_entry import DiaryEntry
from backend.schemas.diary import DiaryEntryCreate, DiaryPromptResponse

QUESTION_BANK: list[str] = [
    "What is your earliest memory, and why do you think it has stayed with you?",
    "Describe a moment when you felt truly proud of yourself.",
    "Who has had the greatest influence on your life, and what did they teach you?",
    "What is the best piece of advice you have ever received?",
    "Describe a place that has always felt like home to you.",
    "What challenge or hardship has shaped you the most?",
    "What is a lesson you learned the hard way?",
    "What is a tradition or ritual that matters to you, and where did it come from?",
    "Describe a moment in your life when everything seemed to change.",
    "What is something you believe strongly that most people around you disagree with?",
    "What does a perfect ordinary day look like to you?",
    "Is there something you wish you had said to someone but never did?",
    "Describe the bravest thing you have ever done.",
    "What has loss taught you about what matters most?",
    "What is a small, everyday thing that brings you genuine joy?",
    "If you could give your younger self one piece of advice, what would it be?",
    "What is the most important thing you want the people you love to know about you?",
    "Describe a time when you changed your mind about something you once held firmly.",
    "What are you most afraid of, and how have you learned to live with that fear?",
    "What is a story from your life that you have told so many times it has become part of you?",
    "What does love mean to you?",
    "How is the person you have become different from the person you thought you would be?",
    "What is something in your life that feels unfinished or unresolved?",
    "What do you hope people will remember about you?",
    "What brings you the most peace?",
]

assert len(QUESTION_BANK) == 25, "Question bank must contain exactly 25 questions"


async def get_next_prompt(user_id: uuid.UUID, db: AsyncSession) -> DiaryPromptResponse:
    """Return the next question in sequence for this user, cycling without immediate repeats."""
    result = await db.execute(
        select(DiaryEntry.question_index)
        .where(DiaryEntry.user_id == user_id)
        .order_by(DiaryEntry.created_at.desc())
        .limit(1)
    )
    last_index = result.scalar_one_or_none()
    next_index = 0 if last_index is None else (last_index + 1) % 25
    return DiaryPromptResponse(
        question_index=next_index,
        question_text=QUESTION_BANK[next_index],
    )


async def create_entry(
    user_id: uuid.UUID,
    payload: DiaryEntryCreate,
    db: AsyncSession,
) -> DiaryEntry:
    entry = DiaryEntry(
        user_id=user_id,
        question_index=payload.question_index,
        question_text=QUESTION_BANK[payload.question_index],
        content=payload.content.strip(),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def list_entries(user_id: uuid.UUID, db: AsyncSession) -> list[DiaryEntry]:
    result = await db.execute(
        select(DiaryEntry)
        .where(DiaryEntry.user_id == user_id)
        .order_by(DiaryEntry.created_at.desc())
    )
    return list(result.scalars().all())
