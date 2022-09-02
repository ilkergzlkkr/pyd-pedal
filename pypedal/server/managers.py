from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Tuple

from pydantic import BaseModel
from fastapi import WebSocket

from pypedal import pedal
from pypedal.pedal.equalizer import BoardType, upload_local, youtube_download

from .models import (
    CANCELRecievePayload,
    EQStatus,
    FutureLinkedEvent,
    INITRecievePayload,
    STATUSRecievePayload,
    STATUSSendPayload,
    INTERNAL_ERROR_Payload,
    SubProcessModel,
    TypeRecieve,
    WebsocketSendPayload,
    WebsocketRecievePayload,
    ProcessModel,
)

log = logging.getLogger(__name__)


class ProcessManager:
    """serves youtube-ids as a queue for equalizer processes"""

    processes: Dict[str, ProcessModel] = {}

    _status: Dict[Tuple[str, BoardType], STATUSSendPayload | None] = {}

    def get(self, id: str, /):
        return self.processes.get(id)

    def get_subprocess(self, id: str, /, board_name: BoardType):
        proc = self.get(id)
        return proc and proc.sub.get(board_name)

    def get_video(self, id: str, /):
        proc = self.get(id)
        return proc and proc.video

    def get_status(self, id: str, board_name: BoardType, /):
        return self._status.get((id, board_name))

    def get_eq_progress(self, id: str, board_name: BoardType, /):
        """
        if pedal status is "IN_PROGRESS"
        return eq_status
        """
        s = self.get_status(id, board_name)
        if s and s.state == "IN_PROGRESS":
            return s.status

    async def init(
        self, ws: WebSocket, recieve: WebsocketRecievePayload[INITRecievePayload]
    ):
        """
        Return True if created a new process
        or False if already exists
        """
        id = recieve.data.url
        board_name = recieve.data.board_name

        if id not in self.processes:
            # create new process
            sub = SubProcessModel(ws=[ws])
            self.processes[id] = proc = ProcessModel(url=id, sub={board_name: sub})
            # download video
            proc.background_task = asyncio.create_task(
                self.background_process(proc, board_name)
            )
            # process video and upload
            sub.background_task = asyncio.create_task(
                self.background_subprocess(proc, board_name)
            )
            return True

        if sub := self.get_subprocess(id, board_name):
            # already exists
            if ws not in sub.ws:
                sub.ws.append(ws)
                # TODO: send status update to newest client
            # if cancelled, restart
            proc = self.get(id)
            s = self.get_status(id, board_name)
            if proc and s and s.state == "CANCELLED":
                sub.background_task = asyncio.create_task(
                    self.background_subprocess(proc, board_name)
                )
                return True
            return False

        # process already exists, but not sub_process
        proc = self.processes[id]
        proc.sub[board_name] = sub = SubProcessModel(ws=[ws])
        fut = proc.downloading and proc.downloading.future
        if fut and fut.done():
            if fut.cancelled() or fut.exception():
                # download failed or canceled
                return False
                # sending status afterwards
        # process video and upload
        sub.background_task = asyncio.create_task(
            self.background_subprocess(proc, board_name)
        )
        return True

    async def cancel(
        self, ws: WebSocket, payload: WebsocketRecievePayload[CANCELRecievePayload]
    ):
        id = payload.data.url
        board_name = payload.data.board_name
        proc = self.get(id)
        sub = self.get_subprocess(id, board_name)
        if not proc or not sub:
            return
        if ws in sub.ws:
            if len(sub.ws) == 1:
                # cancel process
                if sub.background_task:
                    sub.background_task.cancel()
                # if proc.background_task:
                #     proc.background_task.cancel()
                return

    async def background_subprocess(
        self, proc: ProcessModel, board_name: pedal.BoardType, /
    ):
        log.debug(
            f"starting background subprocess, {proc.url=}, {proc.sub.keys()=}, {board_name=}"
        )
        sub = proc.sub[board_name]
        cm = ConnectionManager
        payload = self.get_status(proc.url, board_name)
        assert payload

        try:
            tries = 0
            while not proc.downloading:
                if tries > 3:
                    raise Exception("background_process not initalized")
                await asyncio.sleep(0.1)
                tries += 1
            if not proc.downloading.event.is_set():
                # download in progress or failed or canceled
                fut = proc.downloading.future
                if fut.done():
                    # download failed or canceled
                    # parent process will send status update
                    return
            await proc.downloading.event.wait()
            video = proc.downloading.future.result()
            await asyncio.sleep(
                0
            )  # yield (parent process will send status update `done` before us)
            log.debug(f"got downloaded event for {video=}")

            async with sub.lock:
                payload.status = EQStatus(stage="processing")
                await cm.broadcast_model(sub.ws, payload)
            eq = pedal.Equalizer.read_file(video)
            sub.processing = FutureLinkedEvent(eq.run(board_name=board_name))
            await sub.processing.future
            await eq.write_file(video, board_name=board_name)
            async with sub.lock:
                payload.status.percentage = 100
                await cm.broadcast_model(sub.ws, payload)

                payload.status = EQStatus(stage="uploading")
                await cm.broadcast_model(sub.ws, payload)

            sub.uploading = FutureLinkedEvent(
                upload_local(video, board_name=board_name)
            )
            result = await sub.uploading.future
            async with sub.lock:
                payload.status.percentage = 100
                await cm.broadcast_model(sub.ws, payload)
                self._status[(proc.url, board_name)] = payload = STATUSSendPayload(
                    url=proc.url,
                    board_name=board_name,
                    state="DONE",
                    result=result,
                )
                await cm.broadcast_model(sub.ws, payload)
        except Exception as e:
            failed, cancelled = True, False
            if isinstance(e, asyncio.CancelledError):
                failed, cancelled = False, True
            else:
                log.exception(f"background_subprocess {e=}")

            async with sub.lock:
                self._status[(proc.url, board_name)] = payload = STATUSSendPayload(
                    url=proc.url,
                    board_name=board_name,
                    state="DONE",
                    failed=failed,
                    cancelled=cancelled,
                )
                await cm.broadcast_model(sub.ws, payload)
        except asyncio.CancelledError as e:
            pass

        # kill background notify process

    async def background_process(self, proc: ProcessModel, board_name: BoardType, /):
        """
        Process youtube-id in background, sends status updates to client
        with interval of given second(s)
        """

        log.debug(f"starting background process {proc.url=}, {board_name=}")
        sub = proc.sub[board_name]
        cm = ConnectionManager
        async with sub.lock:
            if payload := self.get_status(proc.url, board_name):
                if payload.state == "DONE":
                    return
            self._status[(proc.url, board_name)] = payload = STATUSSendPayload(
                url=proc.url,
                board_name=board_name,
                state="STARTED",
            )
            await cm.broadcast_model(sub.ws, payload)

        # async def send_status_with_interval(proc: ProcessModel, interval: int):
        #     while True:
        #         if (
        #             proc.status_payload.state == "DONE"
        #             or proc.ws not in cm.active_connections
        #         ):
        #             break

        #         async with proc.lock:
        #             await cm.broadcast_model(proc.ws, proc.status_payload)

        #         await asyncio.sleep(interval)

        proc.downloading = FutureLinkedEvent(youtube_download(proc.url))

        async with sub.lock:
            payload.state = "IN_PROGRESS"
            payload.status = EQStatus(stage="downloading")
            await cm.broadcast_model(sub.ws, payload)
        try:
            proc.video = await proc.downloading.future
            # NOTE: subprocesses are already started when download is complete
            log.debug(f"download complete for {proc.video.id}")
            async with sub.lock:
                payload.status.percentage = 100
                await cm.broadcast_model(
                    sub.ws, payload
                )  # may conflict with subprocess
            assert proc.video is not None
            assert proc.downloading.event.is_set()
        except Exception as e:
            failed, cancelled = True, False
            if isinstance(e, asyncio.CancelledError):
                failed, cancelled = False, True
            else:
                log.exception(f"background_process {e=}")

            async with sub.lock:
                self._status[(proc.url, board_name)] = payload = STATUSSendPayload(
                    url=proc.url,
                    board_name=board_name,
                    state="DONE",
                    failed=failed,
                    cancelled=cancelled,
                )
                ws: List[WebSocket] = []
                for sub in proc.sub.values():
                    # to send every sub-process client
                    # for parent process event
                    ws.extend(sub.ws)
                await cm.broadcast_model(ws, payload)
        # kill background notify process


class ConnectionManager:
    # manager has unique Map[youtube-video-id, asyncio.Future]
    # every connection has asyncio.Lock that is acquired when the recieve and send methods are running
    # (do not wait() for acquire -cancel immediately- for not re-running the recieve and send methods)
    # gives the ability to not mix up the message queue and lock between state changes

    # TODO: connection manager functions
    # queue class ? (for more, check "process" dict variable down below)

    active_connections: List[WebSocket] = []
    pm = ProcessManager()

    def index(self, ws: WebSocket):
        return self.active_connections.index(ws)

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active_connections.append(ws)
        return self.active_connections.index(ws)

    async def disconnect(self, ws: WebSocket):
        await ws.close(reason="disconnect")
        self.active_connections.remove(ws)

    async def disconnect_everyone(self):
        await asyncio.gather(
            *[self.disconnect(connection) for connection in self.active_connections]
        )

    @staticmethod
    async def send_model(ws: WebSocket, model: BaseModel):
        """or send_payload idk"""
        if isinstance(model, STATUSSendPayload):
            return await ws.send_json(
                WebsocketSendPayload(op="STATUS", data=model).dict()
            )
        if isinstance(model, INTERNAL_ERROR_Payload):
            return await ws.send_json(
                WebsocketSendPayload(op="INTERNAL_ERROR", data=model).dict()
            )
        await ws.send_json(model.dict())

    async def raw_recieve(self, ws: WebSocket, data: Any):
        payload = WebsocketRecievePayload(**data)  # type: ignore
        log.info(f"{self.index(ws)} received {payload.op}")
        return await self.recieve(ws, payload)

    async def recieve(
        self,
        ws: WebSocket,
        payload: WebsocketRecievePayload[TypeRecieve],
    ):
        op, data = payload.op, payload.data
        data.url

        if op == "INIT" and isinstance(data, INITRecievePayload):
            if await self.pm.init(ws, payload):  # type: ignore
                # init successful
                # start a background task that will send status updates to client
                return

            # process initialized before, check background_task
            sub = self.pm.get_subprocess(data.url, data.board_name)
            if not sub:
                return
            async with sub.lock:
                if status := self.pm.get_status(data.url, data.board_name):
                    await self.send_model(ws, status)
        elif op == "STATUS" and isinstance(data, STATUSRecievePayload):
            # send status to connection every 5 seconds interval
            if status := self.pm.get_status(data.url, data.board_name):
                await self.send_model(ws, status)
        elif op == "CANCEL" and isinstance(data, CANCELRecievePayload):
            return await self.pm.cancel(ws, payload)  # type: ignore
        else:
            return await self.internal_error(ws, f"unknown op: {op}", code=400)

    async def broadcast(self, message: WebsocketSendPayload):
        await asyncio.gather(
            *[
                connection.send_json(message.dict())
                for connection in self.active_connections
            ]
        )

    @staticmethod
    async def broadcast_model(ws_list: List[WebSocket], model: BaseModel):
        await asyncio.gather(
            *[ConnectionManager.send_model(ws, model) for ws in ws_list]
        )

    async def internal_error(
        self,
        ws: WebSocket,
        message: str,
        code: int,
        *,
        disconnected: bool = False,
    ):
        payload = INTERNAL_ERROR_Payload(
            message=message, code=code, disconnected=disconnected
        )
        await self.send_model(ws, payload)
        if disconnected:
            await self.disconnect(ws)


processes = {
    "music_id": {
        "started_time": 124124124,
        "process_done_in_seconds": 104.5,
    }
}

# gif support
# youtube oauth2 upload ?
