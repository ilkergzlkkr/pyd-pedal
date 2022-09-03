from __future__ import annotations
import json

import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse, Response
from pydantic import ValidationError

from pypedal.pedal import (
    Equalizer,
    EQProcessMode,
    SlowedReverbProcessMode,
    youtube_download,
    upload_local,
)

from . import models
from . import managers

log = logging.getLogger(__name__)
app = FastAPI()

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <h2>Your ID: <span id="ws-id"></span></h2>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var client_id = Date.now()
            document.querySelector("#ws-id").textContent = client_id;
            var ws = new WebSocket(`ws://${window.location.host}/ws`);
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var item = document.createElement('li')
                var message = document.createElement('pre')
                var content = JSON.stringify(JSON.parse(event.data), undefined, 2)
                message.textContent = content
                item.appendChild(message)
                messages.appendChild(item)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                var msg = JSON.stringify({message: input.value})
                ws.send(msg)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


manager = managers.ConnectionManager()


@app.get("/")
async def get():
    return HTMLResponse(html)


@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, authorization: Optional[str] = Header(None)
):
    config: models.ProductionConfig = websocket.app.extra["config"]
    if config.PRODUCTION_KEY:
        # check for authorization header
        if config.PRODUCTION_KEY != authorization:
            return await websocket.close(reason="Unauthorized", code=401)

    id = await manager.connect(websocket)
    while True:
        try:
            payload = await websocket.receive_json()
            # blocking
            await manager.raw_recieve(websocket, payload)
        except (ValidationError, json.JSONDecodeError) as e:
            await manager.internal_error(websocket, str(e), 2)
        except WebSocketDisconnect:
            return await manager.cleanup(websocket)


@app.post("/youtube/download", response_model=models.STATUSSendPayload)
async def download(data: models.INITRecievePayload):
    return Response(content="HTTP NOT IMPLEMENTED", status_code=501)


@app.post(f"/eqs/{EQProcessMode.SlowedReverb}")
async def test_run_save(mode: SlowedReverbProcessMode, title: str, file_name: str):
    return Response(content="HTTP NOT IMPLEMENTED", status_code=501)


@app.post("/youtube/upload")
async def upload(mode: SlowedReverbProcessMode, title: str):
    return Response(content="HTTP NOT IMPLEMENTED", status_code=501)
