from plaso_dl.launcher import (
    INITIAL_MENU_TEXT,
    LOGGED_IN_MENU_TEXT,
    _build_capture_start_command,
    _infer_topic,
    _is_choose_all_token,
)


def test_build_capture_start_command_uses_empty_title() -> None:
    cmd = _build_capture_start_command(timeout_s=600)
    assert cmd[:3] == ["cmd", "/c", "start"]
    assert cmd[3] == ""
    assert cmd[4:6] == ["cmd", "/k"]
    assert "python -m plaso_dl auth auto-capture" in cmd[6]


def test_logged_in_menu_text_is_chinese() -> None:
    assert "课程目录" in LOGGED_IN_MENU_TEXT
    assert "班级" in LOGGED_IN_MENU_TEXT
    assert "设置" in LOGGED_IN_MENU_TEXT
    assert "退出" in LOGGED_IN_MENU_TEXT


def test_initial_menu_text_contains_login_settings_exit() -> None:
    assert "登录" in INITIAL_MENU_TEXT
    assert "设置" in INITIAL_MENU_TEXT
    assert "退出" in INITIAL_MENU_TEXT


def test_infer_topic_from_course_name() -> None:
    assert _infer_topic("AI-20251101-Python3-面向对象-1") == "AI"
    assert _infer_topic("SpringBoot 06") == "SpringBoot"


def test_is_choose_all_token() -> None:
    assert _is_choose_all_token("0")
    assert _is_choose_all_token("a")
    assert _is_choose_all_token("A")
    assert _is_choose_all_token("all")
    assert not _is_choose_all_token("1")
