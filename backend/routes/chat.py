from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings, get_settings
from backend.core.security import get_current_user
from backend.db.session import get_db
from backend.schemas.chat import ChatRequest, ChatResponse, SessionLogResponse
from backend.services import gpt_engine

router = APIRouter(prefix="/chat", tags=["chat"])

CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post(
    "/{echo_id}",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat(
    echo_id: uuid.UUID,
    payload: ChatRequest,
    current_user: CurrentUser,
    db: DB,
    settings: SettingsDep,
) -> ChatResponse:
    response_text, confidence, log_id = await gpt_engine.generate_echo_response(
        echo_id=echo_id,
        viewer_id=current_user,
        user_message=payload.message,
        db=db,
        settings=settings,
    )
    return ChatResponse(id=log_id, response=response_text, confidence_score=confidence)


@router.get(
    "/{echo_id}/history",
    response_model=list[SessionLogResponse],
    status_code=status.HTTP_200_OK,
)
async def get_history(
    echo_id: uuid.UUID,
    current_user: CurrentUser,
    db: DB,
) -> list[SessionLogResponse]:
    return await gpt_engine.get_chat_history(
        echo_id=echo_id,
        viewer_id=current_user,
        db=db,
    )
