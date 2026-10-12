from flask.testing import FlaskClient

URL = "/v1/surveys"


def test_create_get_and_list(client: FlaskClient) -> None:
    created = client.post(URL, json={"title": "  Q4 pulse  "})
    assert created.status_code == 201
    survey = created.get_json()
    assert survey["id"] == 3 and survey["title"] == "Q4 pulse"  # whitespace trimmed
    assert created.headers["Location"] == f"{URL}/3"
    assert client.get(f"{URL}/3").get_json() == survey
    assert [s["id"] for s in client.get(URL).get_json()["items"]] == [1, 2, 3]


def test_validation_and_not_found(client: FlaskClient) -> None:
    assert client.get(f"{URL}/999").status_code == 404
    assert client.get(f"{URL}/{2**31}").status_code == 404
    assert client.post(URL, json={"title": ""}).status_code == 400
    assert client.post(URL, json={"title": "x", "extra": 1}).status_code == 400
    assert client.post(URL, data="title=x", content_type="text/plain").status_code == 415


def test_pagination_parameters_are_strict_here_too(client: FlaskClient) -> None:
    assert client.get(f"{URL}?limit=1_0").status_code == 400
    assert client.get(f"{URL}?offset=%2B1").status_code == 400
    assert client.get(f"{URL}?limit=2&offset=0").status_code == 200
