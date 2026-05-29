from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    id: uuid.UUID
    response: str
    confidence_score: float


class SessionLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    echo_id: uuid.UUID
    viewer_id: uuid.UUID | None
    role: str
    content: str
    confidence_score: float | None
    created_at: datetime
