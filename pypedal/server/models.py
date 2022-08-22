from __future__ import annotations

import asyncio
from typing import Generic, Literal, Any, Dict, Optional, TypeVar, Union

from pypedal import pedal
from pydantic import BaseModel, validator, root_validator


class EQStatus(BaseModel):
    stage: Literal["downloading", "processing", "uploading"]
    percentage: Optional[int] = None
    # percentage is not supported currently


# client sends this to server
class RecievePayload(BaseModel):
    # youtube regex
    url: str

    @validator("url", allow_reuse=True)
    def validate_url(cls, v):
        id = pedal.parse_youtube_id(v)
        if not type(id) is str:
            raise ValueError("Invalid youtube url")
        return id


class INITRecievePayload(RecievePayload):
    pass


class STATUSRecievePayload(RecievePayload):
    pass


class CANCELRecievePayload(RecievePayload):
    pass


TypeRecieve = TypeVar(
    "TypeRecieve", INITRecievePayload, STATUSRecievePayload, CANCELRecievePayload
)

# server sends this to client
class SendPayload(BaseModel):
    url: Optional[str] = None


class STATUSSendPayload(SendPayload):
    # state: Literal["STARTED", "IN_PROGRESS","CANCELLED", "FAILED", "DONE"]
    state: Literal["STARTED", "IN_PROGRESS", "DONE"]
    cancelled: bool = False
    failed: bool = False
    status: Optional[EQStatus] = None

    @root_validator
    def check_failed_or_cancelled(cls, values):
        if values["failed"] is True and values["cancelled"] is True:
            raise ValueError(
                "both 'failed' and 'cancelled' values cannot be True at the same time"
            )
        return values

    @root_validator
    def check_status_if_in_progress(cls, values: Dict[str, Any]):
        if values["state"] == "IN_PROGRESS":
            if values["status"] is None:
                raise ValueError(
                    "'status' value cannot be None if state == IN_PROGRESS"
                )
        else:
            assert (
                values["status"] is None
            ), "'status' should not be included if state != IN_PROGRESS"
        return values

    @validator("failed", "cancelled")
    def check_done_if_failed_or_cancelled(cls, v: bool, values: Dict[str, Any]):
        # this could be undesired if op CANCEL payload had
        # approached and the state is IN_PROGRESS
        # but... anyways
        if values["state"] != "DONE":
            if v is True:
                raise ValueError(
                    "'failed' or 'cancelled' values cannot be True if state != DONE"
                )
        return v


class INTERNAL_ERROR_Payload(SendPayload):
    """
    ## Internal Error
    ### code 1: `Unknown error`
    ### code 2: `Validation error`
    """

    message: str
    code: int
    disconnected: bool = False


TypeSend = TypeVar("TypeSend", STATUSSendPayload, INTERNAL_ERROR_Payload)


class WebsocketRecievePayload(BaseModel, Generic[TypeRecieve]):
    op: Literal["INIT", "STATUS", "CANCEL"]
    # INIT: send only
    # when server recieves, initializes eq process

    # STATUS: send, recieve
    # when server recieves, sends status update to client

    # CANCEL: send only
    # when server recieves, cancels the eq process
    data: TypeRecieve


class WebsocketSendPayload(BaseModel, Generic[TypeSend]):
    op: Literal["STATUS", "INTERNAL_ERROR"]
    # STATUS: send, recieve
    # informs the clients

    # INTERNAL_ERROR: recieve only
    # when client recieves, raises an internal error
    # server may disconnect the client
    data: TypeSend


# class ProcessModel(BaseModel):
#     lock: asyncio.Lock = asyncio.Lock()
#     status_payload: Optional[STATUSSendPayload] = None
