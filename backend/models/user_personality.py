from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class UserPersonality(Base):
    __tablename__ = "user_personality"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # one profile per user
        index=True,
    )
    traits: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    tone: Mapped[str] = mapped_column(Text, nullable=False, server_default="warm")
    # "casual" | "warm" | "formal" | "spiritual"
    catchphrases: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
