from flask import Blueprint, Response, jsonify
from sqlalchemy import select

from app.config import INT32_MAX
from app.db import session
from app.errors import problem
from app.http import created, page_response, pagination_args, parse_body
from app.models import Survey
from app.schemas import NewSurvey

bp = Blueprint("surveys", __name__, url_prefix="/v1/surveys")


@bp.post("")
def create_survey() -> Response:
    survey = Survey(title=parse_body(NewSurvey).title)
    db = session()
    db.add(survey)
    db.commit()  # the INSERT ... RETURNING fills in id and created_at
    return created(survey, bp.url_prefix or "")


@bp.get("")
def list_surveys() -> Response:
    errors: dict[str, str] = {}
    limit, offset = pagination_args(errors)
    if errors:
        return problem(400, "Invalid query parameters", errors=errors)
    rows = session().scalars(select(Survey).order_by(Survey.id).limit(limit + 1).offset(offset)).all()
    return page_response(rows, limit, offset)


# max=...: ids beyond the column's range can't exist, so the router answers 404 instead of Postgres erroring.
@bp.get(f"/<int(min=1, max={INT32_MAX}):survey_id>")
def get_survey(survey_id: int) -> Response:
    survey = session().get(Survey, survey_id)
    if survey is None:
        return problem(404, "Not Found", detail=f"survey {survey_id} not found")
    return jsonify(survey.to_dict())
