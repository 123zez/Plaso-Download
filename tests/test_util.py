from plaso_dl.util import format_duration_hms


def test_format_duration_hms_basic() -> None:
    assert format_duration_hms(None) == ""
    assert format_duration_hms(0) == "00:00:00"
    assert format_duration_hms(105) == "00:01:45"
    assert format_duration_hms(15568) == "04:19:28"
