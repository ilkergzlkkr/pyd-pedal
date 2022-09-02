from __future__ import annotations

import asyncio
import dataclasses
from typing import (
    Generic,
    List,
    Literal,
    Any,
    Dict,
    Optional,
    TypeVar,
)

from fastapi import WebSocket
from pydantic import BaseModel, validator, root_validator

from pypedal import pedal
from pypedal.pedal import PartialYoutubeVideo, YoutubeVideo


class EQStatus(BaseModel):
    # TODO: change name to EQProgress
    stage: Literal["downloading", "processing", "uploading"]
    percentage: Optional[int] = None
    # percentage is not supported currently


# client sends this to server
class RecievePayload(BaseModel, Generic[pedal.EQTYPES]):
    # youtube regex
    url: str
    board_name: pedal.BoardType[pedal.EQTYPES]

    @validator("url", allow_reuse=True)
    def validate_url(cls, v):
        id = pedal.parse_youtube_id(v)
        if not type(id) is str:
            raise ValueError("Invalid youtube url")
        return id


class INITRecievePayload(RecievePayload, Generic[pedal.EQTYPES]):
    pass


class STATUSRecievePayload(RecievePayload, Generic[pedal.EQTYPES]):
    pass


class CANCELRecievePayload(RecievePayload, Generic[pedal.EQTYPES]):
    pass


TypeRecieve = TypeVar(
    "TypeRecieve", INITRecievePayload, STATUSRecievePayload, CANCELRecievePayload
)

# server sends this to client
class SendPayload(BaseModel):
    pass


class STATUSSendPayload(SendPayload):
    url: str
    board_name: pedal.BoardType
    state: Literal["STARTED", "IN_PROGRESS", "DONE"]
    cancelled: bool = False
    failed: bool = False
    result: Optional[str] = None
    status: Optional[EQStatus] = None

    # TODO: ValueError if no result is set
    # if not cancelled and not failed

    @root_validator
    def check_failed_or_cancelled(cls, values):
        if values["failed"] is True and values["cancelled"] is True:
            raise ValueError(
                "both 'failed' and 'cancelled' values cannot be True at the same time"
            )
        return values

    @root_validator
    def check_status_if_in_progress(cls, values: Dict[str, Any]):
        if values.get("state") == "IN_PROGRESS":
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


T = TypeVar("T")


@dataclasses.dataclass
class FutureLinkedEvent(Generic[T]):
    future: asyncio.Future[T]
    event: asyncio.Event = dataclasses.field(default_factory=asyncio.Event)

    def __post_init__(self):
        self.future.add_done_callback(lambda result: self.event.set())


@dataclasses.dataclass
class SubProcessModel:
    ws: List[WebSocket]
    # status_payload: STATUSSendPayload
    processing: FutureLinkedEvent[Any] | None = None
    uploading: FutureLinkedEvent[str] | None = None
    background_task: asyncio.Task | None = None
    lock: asyncio.Lock = dataclasses.field(default_factory=asyncio.Lock)


@dataclasses.dataclass
class ProcessModel(Generic[pedal.EQTYPES]):
    url: str
    sub: Dict[pedal.BoardType[pedal.EQTYPES], SubProcessModel] = dataclasses.field(
        default_factory=dict
    )
    video: Optional[PartialYoutubeVideo] = None
    downloading: FutureLinkedEvent[YoutubeVideo] | None = None
    background_task: asyncio.Task | None = None
