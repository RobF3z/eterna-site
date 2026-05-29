from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.security import get_current_user
from backend.db.session import get_db
from backend.schemas.diary import DiaryEntryCreate, DiaryEntryResponse, DiaryPromptResponse
from backend.services import diary as diary_service

router = APIRouter(prefix="/diary", tags=["diary"])

CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


@router.get("/prompt", response_model=DiaryPromptResponse, status_code=status.HTTP_200_OK)
async def get_prompt(current_user: CurrentUser, db: DB) -> DiaryPromptResponse:
    return await diary_service.get_next_prompt(current_user, db)


@router.post("", response_model=DiaryEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_diary_entry(
    payload: DiaryEntryCreate,
    current_user: CurrentUser,
    db: DB,
) -> DiaryEntryResponse:
    return await diary_service.create_entry(current_user, payload, db)


@router.get("", response_model=list[DiaryEntryResponse], status_code=status.HTTP_200_OK)
async def list_diary_entries(current_user: CurrentUser, db: DB) -> list[DiaryEntryResponse]:
    return await diary_service.list_entries(current_user, db)
