from __future__ import annotations

# ── MUST come before any backend.* import ─────────────────────────────────────
# backend.db.session creates an engine at module-level via get_settings(), so
# these env vars must be present before that module is first imported.
import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost/eterna_test",
)
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-not-production!!")
os.environ.setdefault("OPENAI_API_KEY", "sk-test")

# ── Standard imports ──────────────────────────────────────────────────────────
import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from backend.db.base import Base
from backend.db.session import get_db
from backend.main import app

_TEST_ENGINE = create_async_engine(os.environ["DATABASE_URL"], echo=False)


# ── Schema lifecycle (once per session) ───────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def _db_schema() -> None:
    """Create all tables before the session; drop them after."""
    async def _up() -> None:
        async with _TEST_ENGINE.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def _down() -> None:
        async with _TEST_ENGINE.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await _TEST_ENGINE.dispose()

    asyncio.run(_up())
    yield
    asyncio.run(_down())


# ── Per-test DB session with SAVEPOINT isolation ───────────────────────────────

@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[AsyncSession, None]:
    """
    Wraps each test in an outer transaction.  Service-layer commit() calls
    become nested SAVEPOINTs rather than real commits.  The outer transaction
    is rolled back after the test, leaving the DB clean for the next one.
    """
    async with _TEST_ENGINE.connect() as conn:
        await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await conn.rollback()


# ── HTTP client wired to the test DB ─────────────────────────────────────────

@pytest_asyncio.fixture()
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient against the test app; get_db is overridden to use the
    per-test session so that service writes are visible within the same
    transaction."""
    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── OpenAI mock ───────────────────────────────────────────────────────────────

@pytest.fixture()
def mock_openai() -> AsyncMock:
    """Stub AsyncOpenAI so tests never touch the real API."""
    mock_msg = MagicMock()
    mock_msg.content = (
        "I remember sitting in the back garden, the smell of cut grass all around me."
    )
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock(message=mock_msg)]

    with patch("backend.services.gpt_engine.AsyncOpenAI") as mock_cls:
        instance = AsyncMock()
        instance.chat.completions.create = AsyncMock(return_value=mock_completion)
        mock_cls.return_value = instance
        yield instance
