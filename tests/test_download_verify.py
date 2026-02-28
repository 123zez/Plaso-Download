from plaso_dl.download import is_duration_within_tolerance


def test_is_duration_within_tolerance() -> None:
    assert is_duration_within_tolerance(expected_s=9513, actual_s=9500, tolerance_s=60)
    assert is_duration_within_tolerance(expected_s=9513, actual_s=9453, tolerance_s=60)
    assert not is_duration_within_tolerance(
        expected_s=9513, actual_s=9300, tolerance_s=60
    )
    assert is_duration_within_tolerance(expected_s=None, actual_s=9300, tolerance_s=60)
    assert is_duration_within_tolerance(expected_s=9513, actual_s=None, tolerance_s=60)
