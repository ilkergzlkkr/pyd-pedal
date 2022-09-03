from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import re
import time
import traceback
import typer
from typing import (
    TYPE_CHECKING,
    Dict,
    Any,
    Optional,
    Tuple,
)

import youtube_dl
import requests

from pysndfx import AudioEffectsChain

from pedalboard.io import ReadableAudioFile, WriteableAudioFile

from pypedal import __file__ as pypedal_path
from pypedal.pedal.modes import (
    EQProcessMode,
    ResampleProcessMode,
    SlowedReverbProcessMode,
    EQTYPES,
    get_board,
)
from pypedal.pedal.models import PartialYoutubeVideo, YoutubeVideo

if TYPE_CHECKING:
    from numpy import ndarray, dtype, float32

    AudioType = ndarray[Any, dtype[float32]]

if __name__ == "__main__":
    log = logging.getLogger("equalizer")
else:
    log = logging.getLogger(__name__)


class Options:
    def __init__(self, f: str | pathlib.Path = "") -> None:
        if not f:
            f = pathlib.Path(pypedal_path).resolve().parent
            # lib path
            f = f.parent / "temp" / "assets"
            # projects temp path

        self.FOLDER = pathlib.Path(f)
        self.PROCESSED_FOLDER = pathlib.Path(f) / "processed"
        log.info(f"Using {self.FOLDER!r} as temp path")


options = Options()
YoutubeUrlRegex = re.compile(
    r"""(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/ ]{11})"""
)
YoutubeIdRegex = re.compile(r"""([^"&?\/ ]{11})""")
BoardType = Tuple[EQProcessMode, EQTYPES]


class YoutubeDLError(Exception):
    ...


class Equalizer:
    def __init__(
        self,
        *,
        # file: AudioFile | None = None,
        video: PartialYoutubeVideo | None = None,
        audio: "AudioType | None" = None,
        samplerate: float | None = None,
        done: Dict[BoardType, "AudioType"] | None = None,  # classvar ? (global cache)
    ):
        # self.file = file
        self.video = video

        self.audio = audio
        self.samplerate = samplerate

        self.done = done or {}

    @classmethod
    def read_file(
        cls,
        video: PartialYoutubeVideo | None = None,
        *,
        file_name: str | None = None,
        extension: str = "mp3",
        path: pathlib.Path | None = None,
    ):
        if not path:
            path = options.FOLDER
        if not video:
            if not file_name:
                raise Exception("file_name is required")
        else:
            file_name = video.file_name
            extension = video.ext

        # TODO: async-method
        # The duration in seconds 10 == frames(441_000) / samplerate(44,100hz)
        log.info(f"reading {file_name=} {extension=}")
        file = ReadableAudioFile(f"{path}/{file_name}.{extension}")
        with file as f:
            audio = f.read_raw(f.frames * 2)
            samplerate = f.samplerate

        return cls(
            # file=file,
            video=video,
            audio=audio,
            samplerate=samplerate,
        )

    def write_file(
        self,
        video: PartialYoutubeVideo | None = None,
        board_name: BoardType[EQTYPES] = (
            EQProcessMode.SlowedReverb,
            SlowedReverbProcessMode.Mid,
        ),
        *,
        title: str | None = None,
        extension: str = "mp3",
        path: pathlib.Path | None = None,
    ):
        def wrapper(
            video: PartialYoutubeVideo | None,
            board_name: BoardType[EQTYPES],
            title: str | None,
            extension: str,
            path: pathlib.Path | None,
        ):
            if not path:
                path = options.PROCESSED_FOLDER

            if not video:
                if not title:
                    raise Exception("title is required")
            else:
                title = video.safe_title
                extension = video.ext

            file_name = f"{title}-{board_name[1]}"
            if (audio := self.done.get(board_name)) is None:
                raise Exception("please run first")

            assert isinstance(self.samplerate, float)
            file = path / f"{file_name}.{extension}"
            file.parent.mkdir(parents=True, exist_ok=True)
            with WriteableAudioFile(
                str(file),
                self.samplerate,
                audio.shape[0],
            ) as f:
                f.write(audio)

            return file_name

        return asyncio.get_event_loop().run_in_executor(
            None, wrapper, video, board_name, title, extension, path
        )

    async def save_local(
        self,
        video: PartialYoutubeVideo,
        board_name: BoardType[EQTYPES],
        *,
        number_of_tries: int = 4,
    ):

        for tries in range(number_of_tries):
            log.info(f"saving {video=} {board_name=} {tries=}")
            # Write the audio back as a wav file:
            try:
                return await self.write_file(video, board_name)
            except Exception as e:
                if "Unable to open" in str(e):
                    log.critical(f"Close the {video}= for write operation")
                log.info(e)
                traceback.print_exc()
                await asyncio.sleep(5)

    def run(
        self,
        *,
        board_name: BoardType[EQTYPES] = (
            EQProcessMode.SlowedReverb,
            SlowedReverbProcessMode.Mid,
        ),
        run_once: bool = True,
        args: tuple | None = None,
    ):
        def wrapper(
            video: PartialYoutubeVideo | None,
            board_name: BoardType[EQTYPES],
            run_once: bool,
            args: tuple | None,
        ):
            done_before = self.done.get(board_name)
            if not done_before and video is not None:
                file = (
                    options.PROCESSED_FOLDER
                    / f"{video.safe_title}-{board_name[1]}.{video.ext}"
                )
                if file.exists():
                    log.info(f"{file} exists, setting done_before")
                    with ReadableAudioFile(str(file)) as f:
                        self.done[board_name] = done_before = f.read(f.frames)

            if done_before is not None and run_once:
                return done_before
                # TODO: skip writing afterwards

            if self.audio is None or self.samplerate is None:
                raise Exception("please run first")

            board = get_board(board_name[0], board_name[1])
            if board is None:
                raise Exception("Board not found")

            log.info(f"proccessing with {board_name=}")
            if isinstance(board, AudioEffectsChain):
                self.done[board_name] = board(self.audio)  # type: ignore

            else:
                self.done[board_name] = board(self.audio, self.samplerate)

            return self.done[board_name]

        loop = asyncio.get_event_loop()
        return loop.run_in_executor(
            None, wrapper, self.video, board_name, run_once, args
        )


def parse_youtube_id(url: str):
    """
    Parse the youtube id from a url
    """
    match = YoutubeUrlRegex.search(url)
    match = match or YoutubeIdRegex.search(url)
    if match:
        return match.group(1)


def youtube_download(url: str, *, title_suffix: str = ""):
    # returns chunk of progress...
    """
    title suffix added for multi_process support \n
    returns YoutubeVideo
    """

    def wrapper(url: str, title_suffix: str):
        video_id = parse_youtube_id(url)

        if type(video_id) is not str:
            raise YoutubeDLError("Invalid youtube url")

        url = video_id
        youtube_log = logging.getLogger("ytdl")
        youtube_log.setLevel(logging.DEBUG)
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": f"{options.FOLDER}/%(title)s-%(id)s{title_suffix}.%(ext)s",
            "keepvideo": True,
            "logger": youtube_log,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }
        log.info(f"downloading {url=}")
        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            tries = 0
            while tries < 3:
                tries += 1
                try:
                    info = ydl.extract_info(url)
                    out = YoutubeVideo(**info)  # type: ignore
                except (youtube_dl.DownloadError, PermissionError) as e:
                    if "unable to rename file" in str(e) or isinstance(
                        e, PermissionError
                    ):
                        time.sleep(0.1)
                        continue  # parralel downloading happened, try re-extracting
                    if "unable to download" in str(e):
                        continue  # rate-limit ?
                    if "Unable to resume" in str(e):
                        raise  # youtube_dl tries to re-download with no reason
                    raise
                else:
                    break
            else:
                # tries done, no out
                raise YoutubeDLError("Unable to download")

            assert out.id == video_id

            # we need safely-generated filename from ydl for filesystem
            path = pathlib.Path(str(ydl.prepare_filename(info)))
            file = path.name
            file_name, _extension = file.rsplit(".", 1)
            out.file_name = file_name  # safe filename from ydl
            out.safe_title = file_name.rsplit(f"-{out.id}", 1)[0]
            out.ext = ydl_opts["postprocessors"][0]["preferredcodec"]
            # ydl gives us "webm", "m4a" ext from info for some reason :/

        return out

    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, wrapper, url, title_suffix)


def upload_to_transferfilesh(file: pathlib.Path, /, *, clipboard: bool = False):
    def wrapper(file: pathlib.Path, clipboard: bool):
        def get_size(file: pathlib.Path):
            """
            get file size, in megabytes
            :param file:
            :return: size of file
            """
            size_in_bytes = os.path.getsize(file)
            size_in_megabytes = size_in_bytes / 1_000_000
            return size_in_megabytes

        size_of_file = get_size(file)
        log.info(f"sending file: {os.path.basename(file)} ({size_of_file=} MB)")

        opened_file = open(file, "rb")
        response = requests.post("https://transfer.sh/", files={file.name: opened_file})
        opened_file.close()
        download_link = response.content.decode("utf-8").replace("\n", "")
        log.info(f"link to download file:\n{download_link}")

        if clipboard:
            import pyperclip

            pyperclip.copy(download_link)
        return download_link

    loop = asyncio.get_event_loop()
    return loop.run_in_executor(None, wrapper, file, clipboard)


def upload_local(
    video: PartialYoutubeVideo | None = None,
    *,
    title: str | None = None,
    board_name: BoardType[EQTYPES],
    extension: str = "mp3",
    copy_to_clipboard: bool = False,  # debug purposes, remove later,
    delete_after=None,  # TODO: datetime for when to delete file, especially for pytest
):
    if video:
        title = video.safe_title
        extension = video.ext
    else:
        if not (title and extension):
            raise Exception(
                "cannot make full_qualified_name for given inputs to upload"
            )

    full_qualified_name = pathlib.Path(
        f"{options.PROCESSED_FOLDER}/{title}-{board_name[1]}.{extension}"
    )

    return upload_to_transferfilesh(full_qualified_name, clipboard=copy_to_clipboard)


app = typer.Typer()


@app.command()
def resample(
    youtube_link: Optional[str] = typer.Argument(
        None, help="youtube link, optional if you have already downloaded"
    ),
    video_id: Optional[str] = typer.Option(
        None, help="local video id if youtube_link is None (video downloaded before)"
    ),
    title: Optional[str] = None,
    mode_level: ResampleProcessMode = ResampleProcessMode.Down,
    run_once: bool = True,
    upload: bool = False,
):
    import colouredlogs

    colouredlogs.install(logging.DEBUG, reconfigure=False)

    loop = asyncio.get_event_loop()
    UPLOAD_FILE = upload
    YOUTUBE_LINK = youtube_link or ""
    ID, TITLE = (
        video_id or "bCxtVoZJV2I",
        title or "Jakuzi - 'Sana Göre Bir Şey Yok' (Official Audio)",
    )

    if not YOUTUBE_LINK:
        if not ID:
            raise RuntimeError("no youtube link or video id")

    if YOUTUBE_LINK:
        video = loop.run_until_complete(youtube_download(YOUTUBE_LINK))
    else:
        video = PartialYoutubeVideo(id=ID, title=TITLE)

    board_name = EQProcessMode.Resample, mode_level

    eq = Equalizer.read_file(video)
    loop.run_until_complete(eq.run(board_name=board_name, run_once=run_once))
    loop.run_until_complete(eq.save_local(video, board_name))
    if UPLOAD_FILE:
        loop.run_until_complete(
            upload_local(video, board_name=board_name, copy_to_clipboard=True)
        )


@app.command()
def slowed_reverb(
    youtube_link: Optional[str] = typer.Argument(
        None, help="youtube link, optional if you have already downloaded"
    ),
    video_id: Optional[str] = typer.Option(
        None, help="local video id if youtube_link is None (video downloaded before)"
    ),
    title: Optional[str] = None,
    mode_level: SlowedReverbProcessMode = SlowedReverbProcessMode.Mid,
    use_all_levels: bool = False,
    run_once: bool = True,
    upload: bool = False,
):
    import colouredlogs

    colouredlogs.install(logging.DEBUG, reconfigure=False)

    loop = asyncio.get_event_loop()
    UPLOAD_FILE = upload
    YOUTUBE_LINK = youtube_link or ""
    ID, TITLE = (
        video_id or "bCxtVoZJV2I",
        title or "Jakuzi - 'Sana Göre Bir Şey Yok' (Official Audio)",
    )

    if not YOUTUBE_LINK:
        if not ID:
            raise RuntimeError("no youtube link or video id")

    if YOUTUBE_LINK:
        video = loop.run_until_complete(youtube_download(YOUTUBE_LINK))
    else:
        video = PartialYoutubeVideo(id=ID, title=TITLE)

    if use_all_levels:
        eq_range = {
            0: (EQProcessMode.SlowedReverb, SlowedReverbProcessMode.Low),
            1: (EQProcessMode.SlowedReverb, SlowedReverbProcessMode.Mid),
            2: (EQProcessMode.SlowedReverb, SlowedReverbProcessMode.High),
        }
    else:
        eq_range = {
            0: (EQProcessMode.SlowedReverb, mode_level),
        }

    eq = Equalizer.read_file(video)
    for idx, board_name in eq_range.items():
        loop.run_until_complete(eq.run(board_name=board_name, run_once=run_once))
        loop.run_until_complete(eq.save_local(video, board_name))
        if UPLOAD_FILE:
            loop.run_until_complete(
                upload_local(video, board_name=board_name, copy_to_clipboard=True)
            )


if __name__ == "__main__":
    app()
