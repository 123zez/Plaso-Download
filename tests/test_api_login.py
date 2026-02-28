from plaso_dl.api import extract_access_token_from_login_response


def test_extract_access_token_from_login_response() -> None:
    data = {"code": 0, "obj": {"access_token": "tok-1"}}
    assert extract_access_token_from_login_response(data) == "tok-1"


def test_extract_access_token_from_login_response_invalid() -> None:
    assert extract_access_token_from_login_response({"code": 1, "obj": {}}) is None
