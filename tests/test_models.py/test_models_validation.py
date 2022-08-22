from pypedal.server.models import STATUSSendPayload, EQStatus

import pytest


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
