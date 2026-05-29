from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings, get_settings
from backend.core.security import get_current_user
from backend.db.session import get_db
from backend.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from backend.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[uuid.UUID, Depends(get_current_user)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DB) -> UserResponse:
    return await auth_service.register(payload, db)


@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(payload: LoginRequest, db: DB, settings: SettingsDep) -> TokenResponse:
    return await auth_service.login(payload, db, settings)


@router.post("/refresh", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def refresh(payload: RefreshRequest, settings: SettingsDep) -> TokenResponse:
    return await auth_service.refresh_tokens(payload.refresh_token, settings)


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def me(current_user: CurrentUser, db: DB) -> UserResponse:
    return await auth_service.get_by_id(current_user, db)
