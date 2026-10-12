"""SQLAlchemy 2.0 models. They must match migrations/ (tests/test_migrations.py checks)."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    def to_dict(self) -> dict[str, Any]:
        """JSON-ready column values (timestamps as ISO 8601)."""
        values = {c.key: getattr(self, c.key) for c in self.__table__.columns}
        return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in values.items()}


class Survey(Base):
    __tablename__ = "surveys"
    __table_args__ = (CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="surveys_title_check"),)

    id: Mapped[int] = mapped_column(Integer, Identity(always=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        CheckConstraint("char_length(respondent) BETWEEN 1 AND 200", name="responses_respondent_check"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="responses_rating_check"),
        CheckConstraint("char_length(comment) <= 2000", name="responses_comment_check"),
        # Serves GET /v1/responses?survey_id=N (filter on survey_id, ordered by id) and the foreign key.
        Index("idx_responses_survey_id_id", "survey_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    survey_id: Mapped[int] = mapped_column(Integer, ForeignKey("surveys.id"))
    respondent: Mapped[str] = mapped_column(Text)
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
