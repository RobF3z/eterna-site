from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DiaryEntryCreate(BaseModel):
    question_index: int = Field(..., ge=0, le=24)
    content: str = Field(..., min_length=1, max_length=10_000)


class DiaryEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    question_index: int
    question_text: str
    content: str
    audio_path: str | None
    created_at: datetime
    updated_at: datetime


class DiaryPromptResponse(BaseModel):
    question_index: int
    question_text: str
