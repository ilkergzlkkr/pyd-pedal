import pytest

from pypedal.server.models import STATUSSendPayload, EQStatus
from pypedal.pedal.models import PartialYoutubeVideo


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
        

def test_status_validations():
    # OK
    STATUSSendPayload(url="", state="STARTED")
    STATUSSendPayload(url="", state="IN_PROGRESS", status=EQStatus(stage="downloading"))
    # FAIL
    with pytest.raises(ValueError):
        STATUSSendPayload(url="", state="STARTED", cancelled=True)
    with pytest.raises(ValueError):
        STATUSSendPayload(url="", state="DONE", cancelled=True, failed=True)
    with pytest.raises(ValueError):
        STATUSSendPayload(
            url="",
            state="IN_PROGRESS",
            status=EQStatus(stage="downloading"),
            cancelled=True,  # fails
        )
    with pytest.raises(ValueError):
        STATUSSendPayload(
            url="",
            state="IN_PROGRESS",
            # fails due to no status
        )
