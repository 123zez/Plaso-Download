from plaso_dl.api import (
    build_course_list_request,
    parse_course_list_from_list,
    parse_group_list,
)


def test_build_course_list_request_minimal() -> None:
    req = build_course_list_request(search="")
    assert req["method"] == "POST"
    assert "/liveclassgo/api/v1/history/listRecord" in req["url"]
    assert req["json"]["indexStart"] == 0
    assert req["json"]["pageSize"] == 200
    assert req["json"]["dateFrom"] < req["json"]["dateTo"]


def test_build_course_list_request_course_list_endpoint() -> None:
    req = build_course_list_request(search="", endpoint="course_list")
    assert req["method"] == "POST"
    assert "/course/api/v1/m/package/student/list" in req["url"]
    assert req["json"] == {"search": "", "pageNo": 1, "pageSize": 200}


def test_build_course_list_request_with_group_id() -> None:
    req = build_course_list_request(search="", endpoint="history", group_id=3599750)
    assert req["json"]["groupId"] == 3599750


def test_parse_course_list_from_obj_list_shape() -> None:
    rows = [
        {
            "_id": "1",
            "shortDesc": "Course A",
            "teacherName": "T",
            "duration": 120,
            "createTime": 1700000000000,
            "fileCommon": {"location": "12202/x", "locationPath": "liveclass"},
        }
    ]
    items = parse_course_list_from_list(rows)
    assert len(items) == 1
    assert items[0].id == "1"
    assert items[0].file_common.location == "12202/x"


def test_parse_group_list() -> None:
    groups = parse_group_list(
        [
            {
                "id": 1,
                "groupName": "蓝桥杯培训",
                "activeStartMs": 1,
                "activeEndMs": 2,
            }
        ]
    )
    assert len(groups) == 1
    assert groups[0].id == 1
    assert groups[0].name == "蓝桥杯培训"
