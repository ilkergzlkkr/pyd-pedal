import pytest

from pypedal.server.models import STATUSSendPayload, EQStatus
from pypedal.pedal.models import PartialYoutubeVideo
from pypedal.pedal.equalizer import EQProcessMode, SlowedReverbProcessMode


def test_youtube_video():
    video = PartialYoutubeVideo(
        id="U5QKIISDaCg", title="Aykut Elmas - Salak salak konuşma be"
    )
    assert "U5QKIISDaCg" in video.url
    assert "U5QKIISDaCg" in video.file_name
    assert video.file_name.endswith(video.id)

    assert video == "U5QKIISDaCg"
    assert video != "anyid31"
    assert video == PartialYoutubeVideo(id="U5QKIISDaCg", title="")
    assert video != PartialYoutubeVideo(id="31", title="")

    with pytest.raises(NotImplementedError):
        _ = video == 31
    with pytest.raises(NotImplementedError):
        _ = video != 31


def test_status_parsing():
    STATUSSendPayload(
        **{
            "url": "",
            "state": "STARTED",
            "board_name": ("slowed_reverb", "35_08"),
        }
    )
    with pytest.raises(ValueError):
        STATUSSendPayload(
            **{
                "url": "",
                "state": "STARTED",
                # "board_name": ("slowed_reverb", "35_08"),
            }  # type: ignore
        )


def test_status_validations():
    board_name = (EQProcessMode.SlowedReverb, SlowedReverbProcessMode.Low)
    # OK
    STATUSSendPayload(url="", state="STARTED", board_name=board_name)
    STATUSSendPayload(
        url="",
        state="IN_PROGRESS",
        status=EQStatus(stage="downloading"),
        board_name=board_name,
    )
    # FAIL
    with pytest.raises(ValueError):
        STATUSSendPayload(url="", state="STARTED", cancelled=True)  # type: ignore no boar_name
    with pytest.raises(ValueError):
        STATUSSendPayload(
            url="", state="STARTED", cancelled=True, board_name=board_name
        )
    with pytest.raises(ValueError):
        STATUSSendPayload(
            url="",
            state="STARTED",
            status=EQStatus(stage="downloading"),
            board_name=board_name,
        )
    with pytest.raises(ValueError):
        STATUSSendPayload(
            url="", state="DONE", cancelled=True, failed=True, board_name=board_name
        )
    with pytest.raises(ValueError):
        STATUSSendPayload(
            url="",
            state="IN_PROGRESS",
            status=EQStatus(stage="downloading"),
            board_name=board_name,
            cancelled=True,  # fails
        )
    with pytest.raises(ValueError):
        STATUSSendPayload(
            url="",
            state="IN_PROGRESS",
            board_name=board_name,
            # fails due to no status
        )
