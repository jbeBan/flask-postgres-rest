import psycopg.errors
from flask import Blueprint, Response, jsonify
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import INT32_MAX, INT64_MAX
from app.db import session
from app.errors import problem
from app.http import created, page_response, pagination_args, parse_body, parse_int_arg
from app.models import Response as ResponseModel
from app.schemas import NewResponse

bp = Blueprint("responses", __name__, url_prefix="/v1/responses")


@bp.post("")
def create_response() -> Response:
    response = ResponseModel(**parse_body(NewResponse).model_dump())
    db = session()
    db.add(response)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, psycopg.errors.ForeignKeyViolation):
            # Well-formed body that points at a survey that does not exist.
            return problem(422, "Unprocessable Content", errors={"survey_id": "survey does not exist"})
        raise
    return created(response, bp.url_prefix or "")


@bp.get("")
def list_responses() -> Response:
    errors: dict[str, str] = {}
    survey_id = parse_int_arg("survey_id", errors, minimum=1, maximum=INT32_MAX)
    limit, offset = pagination_args(errors)
    if errors:
        return problem(400, "Invalid query parameters", errors=errors)

    stmt = select(ResponseModel).order_by(ResponseModel.id).limit(limit + 1).offset(offset)
    if survey_id is not None:
        stmt = stmt.where(ResponseModel.survey_id == survey_id)
    return page_response(session().scalars(stmt).all(), limit, offset)


# max=...: ids beyond the column's range can't exist, so the router answers 404 instead of Postgres erroring.
@bp.get(f"/<int(min=1, max={INT64_MAX}):response_id>")
def get_response(response_id: int) -> Response:
    response = session().get(ResponseModel, response_id)
    if response is None:
        return problem(404, "Not Found", detail=f"response {response_id} not found")
    return jsonify(response.to_dict())
