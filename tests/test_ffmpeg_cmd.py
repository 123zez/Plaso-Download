import plaso_dl.ffmpeg as ffmpeg


def test_ffmpeg_hls_args_contains_input_and_copy(monkeypatch) -> None:
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda _: "ffmpeg")
    args = ffmpeg.build_ffmpeg_hls_args("https://example.com/a.m3u8", "out.mp4")
    assert "-i" in args
    assert "-c" in args and "copy" in args


def test_ffmpeg_hls_args_include_network_resilience_flags(monkeypatch) -> None:
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda _: "ffmpeg")
    args = ffmpeg.build_ffmpeg_hls_args("https://example.com/a.m3u8", "out.mp4")
    assert "-stats" not in args
    assert "-nostats" in args
    assert "-rw_timeout" in args
    assert "-reconnect" in args
    assert "-reconnect_streamed" in args
    assert "-reconnect_delay_max" in args


def test_build_ffmpeg_concat_args(monkeypatch) -> None:
    monkeypatch.setattr(ffmpeg.shutil, "which", lambda _: "ffmpeg")
    args = ffmpeg.build_ffmpeg_concat_args("parts.txt", "out.mp4")
    assert "-f" in args and "concat" in args
    assert "-safe" in args and "0" in args
    assert "-i" in args and "parts.txt" in args
