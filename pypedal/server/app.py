from __future__ import annotations
import json

import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Header
from fastapi.responses import HTMLResponse
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
async def websocket_endpoint(websocket: WebSocket):
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


# @app.websocket("/")
# async def eq_websocket(websocket: WebSocket, Authorization: str = Header(default="")):

#     id = await manager.connect(websocket)
#     try:
#         while True:
#             payload: Dict[str, Any] = await websocket.receive_json()
#             data = WebsocketPayload(id=payload.pop("id", id), **payload)
#             await manager.send_personal_message(f"You wrote: {data.message}", websocket)
#             await manager.broadcast(
#                 f"Client #{client_id} index #{data.id} says: {data.message}"
#             )
#     except WebSocketDisconnect:
#         await manager.disconnect(websocket)
#         await manager.broadcast(f"Client #{client_id} left the chat")


@app.post("/youtube/download", response_model=models.STATUSSendPayload)
async def download(data: models.INITRecievePayload):
    # check if its already download(ing|ed)
    # if data.url in manager.youtube_tasks:
    #     status = manager.youtube_tasks[data.url].status
    #     if status and status.percentage == 100:
    #         return manager.youtube_tasks[data.url]
    #     else:
    #         # wait for the download asyncio.Event to be set
    #         # and return the status
    #         pass
    payload = models.WebsocketRecievePayload(op="INIT", data=data)
    models.WebsocketSendPayload(
        op="STATUS", data=models.STATUSSendPayload(url=data.url, state="STARTED")
    )
    await youtube_download(payload.data.url)
    # in parralel thread (download actually done in background)
    # but we simulate it here
    models.WebsocketSendPayload(
        op="STATUS",
        data=models.STATUSSendPayload(
            url=data.url,
            state="IN_PROGRESS",
            status=models.EQStatus(stage="downloading"),
        ),
    )
    # then the thread is done
    status = models.WebsocketSendPayload(
        op="STATUS",
        data=models.STATUSSendPayload(
            url=data.url,
            state="IN_PROGRESS",
            status=models.EQStatus(stage="downloading", percentage=100),
        ),
    )
    # manager.youtube_tasks[id] = status.data
    return status.data


@app.post(f"/eqs/{EQProcessMode.SlowedReverb}")
async def test_run_save(mode: SlowedReverbProcessMode, title: str, file_name: str):
    # only require yt.id not file-name with title wtf
    board_name = (EQProcessMode.SlowedReverb, mode)
    eq = Equalizer.read_file(file_name=file_name)
    await eq.run(board_name=board_name)
    await eq.write_file(title=title, board_name=board_name)
    return {"upload_ready": True, "title": title}


@app.post("/youtube/upload")
async def upload(mode: SlowedReverbProcessMode, title: str):
    board_name = (EQProcessMode.SlowedReverb, mode)
    link = await upload_local(title=title, board_name=board_name)
    return {"link": link, "success": True}
