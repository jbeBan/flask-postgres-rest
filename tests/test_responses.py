import pytest
from flask.testing import FlaskClient

VALID = {"survey_id": 1, "respondent": "ada@example.com", "rating": 5, "comment": "great"}
URL = "/v1/responses"


def test_create_then_get_and_list(client: FlaskClient) -> None:
    created = client.post(URL, json=VALID)
    assert created.status_code == 201
    body = created.get_json()
    assert body["id"] == 1 and body["rating"] == 5
    assert created.headers["Location"] == f"{URL}/1"

    assert client.get(f"{URL}/1").get_json() == body
    page = client.get(URL).get_json()
    assert page == {"items": [body], "limit": 50, "offset": 0, "next_offset": None}


@pytest.mark.parametrize(
    ("payload", "bad_fields"),
    [
        ({**VALID, "rating": 6}, {"rating"}),
        ({"survey_id": 0, "respondent": "  "}, {"survey_id", "rating", "respondent"}),
        ({**VALID, "rating": "5"}, {"rating"}),
        ({**VALID, "rating": True}, {"rating"}),  # True == 1 in Python, but is not a rating
        ({**VALID, "id": 99}, {"id"}),  # unknown / server-owned field
        ({**VALID, "survey_id": 2**31}, {"survey_id"}),  # beyond the INTEGER column
    ],
)
def test_create_validation_failure_returns_400(
    client: FlaskClient, payload: dict[str, object], bad_fields: set[str]
) -> None:
    resp = client.post(URL, json=payload)
    assert resp.status_code == 400
    assert resp.mimetype == "application/problem+json"
    assert set(resp.get_json()["errors"]) == bad_fields
    assert client.get(URL).get_json()["items"] == []  # nothing was stored


def test_malformed_and_non_object_bodies_return_400(client: FlaskClient) -> None:
    assert client.post(URL, data="{nope", content_type="application/json").status_code == 400
    assert client.post(URL, json=[VALID]).status_code == 400


def test_get_missing_id_returns_404(client: FlaskClient) -> None:
    resp = client.get(f"{URL}/999")
    assert resp.status_code == 404
    assert resp.mimetype == "application/problem+json"
    assert "999" in resp.get_json()["detail"]


@pytest.mark.parametrize("response_id", ["0", "abc", str(2**63), "99999999999999999999"])
def test_ids_outside_the_valid_range_return_404_not_500(client: FlaskClient, response_id: str) -> None:
    assert client.get(f"{URL}/{response_id}").status_code == 404


def test_wrong_content_type_returns_415(client: FlaskClient) -> None:
    assert client.post(URL, data="survey_id=1", content_type="text/plain").status_code == 415


def test_response_for_unknown_survey_returns_422(client: FlaskClient) -> None:
    resp = client.post(URL, json={**VALID, "survey_id": 999})
    assert resp.status_code == 422
    assert "survey_id" in resp.get_json()["errors"]
    assert client.get(URL).get_json()["items"] == []


def test_boundary_ratings_are_accepted(client: FlaskClient) -> None:
    for rating in (1, 5):
        assert client.post(URL, json={**VALID, "rating": rating}).status_code == 201


def test_filter_and_paging(client: FlaskClient) -> None:
    for survey_id in (1, 1, 2, 2, 2):
        client.post(URL, json={**VALID, "survey_id": survey_id})

    only_2 = client.get(f"{URL}?survey_id=2").get_json()["items"]
    assert len(only_2) == 3 and {r["survey_id"] for r in only_2} == {2}

    # 5 rows total: page of 2 starting at offset 1 has more after it; the last page does not.
    page = client.get(f"{URL}?limit=2&offset=1").get_json()
    assert len(page["items"]) == 2 and page["next_offset"] == 3
    assert client.get(f"{URL}?limit=2&offset=4").get_json()["next_offset"] is None
    assert client.get(f"{URL}?survey_id=999").get_json()["items"] == []


@pytest.mark.parametrize(
    "query",
    [
        "limit=0",
        "limit=201",
        "offset=-1",
        f"offset={2**63}",
        "survey_id=abc",
        f"survey_id={2**40}",
        # int() would accept all of these; query parameters must be plain ASCII integers
        "limit=1_0",
        "limit=%2B5",
        "limit=%205%20",
        "limit=5%0A",
        "limit=%D9%A3",
        "offset=1_0",
        "survey_id=1_0",
    ],
)
def test_bad_query_parameters_return_400(client: FlaskClient, query: str) -> None:
    resp = client.get(f"{URL}?{query}")
    assert resp.status_code == 400
    assert resp.mimetype == "application/problem+json"
