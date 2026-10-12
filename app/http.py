"""Request/response helpers shared by the resource blueprints."""

import re
from typing import Any, TypeVar

from flask import Response, jsonify, request
from pydantic import BaseModel, ValidationError

from app.config import INT32_MAX
from app.errors import ProblemError
from app.models import Base

DEFAULT_LIMIT = 50
MAX_LIMIT = 200
# int() also accepts "1_0", "+5", " 5 " and non-ASCII digits; query parameters must be plain ASCII integers.
PLAIN_INT = re.compile(r"-?[0-9]+")


M = TypeVar("M", bound=BaseModel)


def parse_body(model: type[M]) -> M:
    """The request's JSON body as a validated `model`; raises ProblemError (415 or 400) otherwise."""
    if not request.is_json:
        raise ProblemError(415, "Unsupported Media Type", detail="Content-Type must be application/json")
    try:
        return model.model_validate(request.get_json(silent=True))
    except ValidationError as e:
        raise ProblemError(400, "Validation failed", errors=validation_errors(e)) from e


def created(obj: Base, collection_path: str) -> Response:
    """201 with the new object as JSON and a Location header pointing at it."""
    data = obj.to_dict()
    resp = jsonify(data)
    resp.status_code = 201
    resp.headers["Location"] = f"{collection_path}/{data['id']}"
    return resp


def validation_errors(exc: ValidationError) -> dict[str, str]:
    """{field: message}; errors about the body as a whole are keyed "body"."""
    return {".".join(str(p) for p in e["loc"]) or "body": e["msg"] for e in exc.errors()}


def parse_int_arg(
    name: str,
    errors: dict[str, str],
    minimum: int,
    maximum: int,
    default: int | None = None,
) -> int | None:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw) if PLAIN_INT.fullmatch(raw) else None
    except ValueError:  # int() refuses absurdly long digit strings
        value = None
    if value is None:
        errors[name] = "must be an integer"
        return default
    if not minimum <= value <= maximum:
        errors[name] = f"must be between {minimum} and {maximum}"
        return default
    return value


def pagination_args(errors: dict[str, str]) -> tuple[int, int]:
    limit = parse_int_arg("limit", errors, minimum=1, maximum=MAX_LIMIT, default=DEFAULT_LIMIT)
    offset = parse_int_arg("offset", errors, minimum=0, maximum=INT32_MAX, default=0)
    assert limit is not None and offset is not None  # defaults are set
    return limit, offset


def page_response(rows: list[Base] | Any, limit: int, offset: int) -> Response:
    """rows must hold up to limit + 1 models; the extra one tells us whether there is a next page."""
    has_more = len(rows) > limit
    return jsonify(
        items=[r.to_dict() for r in rows[:limit]],
        limit=limit,
        offset=offset,
        next_offset=offset + limit if has_more else None,
    )
