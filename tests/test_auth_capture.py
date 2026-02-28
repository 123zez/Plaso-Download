from plaso_dl.auth_capture import (
    _is_course_api_url,
    extract_access_token,
    extract_token_from_event,
)


def test_extract_access_token_case_insensitive() -> None:
    headers = {
        "Accept": "*/*",
        "Access-Token": "abc123",
    }
    assert extract_access_token(headers) == "abc123"


def test_extract_access_token_missing() -> None:
    headers = {
        "Authorization": "Bearer x",
    }
    assert extract_access_token(headers) is None


def test_extract_token_from_request_will_be_sent() -> None:
    evt = {
        "method": "Network.requestWillBeSent",
        "params": {
            "request": {
                "headers": {
                    "access-token": "tok-1",
                }
            }
        },
    }
    assert extract_token_from_event(evt) == "tok-1"


def test_extract_token_from_extra_info() -> None:
    evt = {
        "method": "Network.requestWillBeSentExtraInfo",
        "params": {
            "headers": {
                "Access-Token": "tok-2",
            }
        },
    }
    assert extract_token_from_event(evt) == "tok-2"


def test_is_course_api_url() -> None:
    assert _is_course_api_url(
        "https://www.plaso.cn/course/api/v1/m/package/student/list/quit"
    )
    assert _is_course_api_url(
        "https://www.plaso.cn/liveclassgo/api/v1/history/listRecord"
    )
    assert not _is_course_api_url(
        "https://www.plaso.cn/yxt/servlet/antiScreenRecord/nct/getScreenRecordList"
    )
