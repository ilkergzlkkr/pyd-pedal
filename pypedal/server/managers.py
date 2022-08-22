from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel
from fastapi import WebSocket

from .models import (
    EQStatus,
    INITRecievePayload,
    STATUSSendPayload,
    INTERNAL_ERROR_Payload,
    WebsocketSendPayload,
    WebsocketRecievePayload,
    # ProcessModel,
)

# class YTInfo(BaseModel):
#     id: str
#     title: str
#     file_name: str

# class ProcessManager:
#     """serves youtube-ids as a queue for equalizer processes"""
#     prcoesses: Dict[str, ProcessModel] = {}

#     def get_status(self, id: str, /):
#         proc = self.prcoesses.get(id)
#         return proc and proc.status_payload


class ConnectionManager:
    # manager has unique Map[youtube-video-id, asyncio.Future]
    # every connection has asyncio.Lock that is acquired when the recieve and send methods are running
    # (do not wait() for acquire -cancel immediately- for not re-running the recieve and send methods)
    # gives the ability to not mix up the message queue and lock between state changes

    # TODO: connection manager functions
    # queue class ? (for more, check "process" dict variable down below)

    active_connections: List[WebSocket] = []
    # pm = ProcessManager()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        return self.active_connections.index(websocket)

    async def disconnect(self, websocket: WebSocket):
        await websocket.close(reason="disconnect")
        self.active_connections.remove(websocket)

    async def disconnect_everyone(self):
        await asyncio.gather(
            *[self.disconnect(connection) for connection in self.active_connections]
        )

    async def send_model(self, websocket: WebSocket, model: BaseModel):
        await websocket.send_json(model.dict())

    async def broadcast(self, message: WebsocketSendPayload):
        await asyncio.gather(
            *[
                connection.send_json(message.dict())
                for connection in self.active_connections
            ]
        )

    async def internal_error(
        self,
        websocket: WebSocket,
        message: str,
        code: int,
        *,
        disconnected: bool = False,
    ):
        payload = WebsocketSendPayload(
            op="INTERNAL_ERROR",
            data=INTERNAL_ERROR_Payload(
                message=message, code=code, disconnected=disconnected
            ),
        )
        await self.send_model(websocket, payload)
        if disconnected:
            await self.disconnect(websocket)


prcoesses = {
    "music_id": {
        "lock": "asyncio.Lock",
        "title": "(Optional) make sure that locking music is safe bc ",
        "file_name": "(Optional bc tilte is unknown) eq.readfile",
        "extension": None,
        # instead of this giant title, file_name and extension
        # we can use model for this
        "guild_ids": [  # for client
            "multiple guilds waiting on same music allowed",
            "just like that",
        ],
        "futures": [
            "first index is download",
            "second index is processing",
            "third index is upload",
        ],
        # all futures has done or errored or cancelled method
        "status": "if done or errored -> notice for another guilds (may-be append to guild_ids)",
        # status is likely to be a EQStatus model
        "spotify_uri": "could be came from another planet ??",  # for client
        "started_time": 124124124,
        "process_done_in_seconds": 104.5,
    }
}

response_payload = {
    # "guild_id": "spesific to a guild", -cancelled
    "music_id": "spesific to a video",
    "status": "done.(yes,no), errored.(yes,no) phase.(downloading, uploading, processing)",
    "download.percentage": "15",
    "server_response": "errored.yes, check logs if disconnected",
}

# gif support
# youtube oauth2 upload ?
