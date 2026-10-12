"""Request body models. Strict mode: no coercion ("5" is not a rating, True is not 1)."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StringConstraints

from app.config import INT32_MAX

TrimmedText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class NewSurvey(Strict):
    title: TrimmedText


class NewResponse(Strict):
    survey_id: Annotated[StrictInt, Field(ge=1, le=INT32_MAX)]
    respondent: TrimmedText
    rating: Annotated[StrictInt, Field(ge=1, le=5)]
    comment: str | None = Field(default=None, max_length=2000)
