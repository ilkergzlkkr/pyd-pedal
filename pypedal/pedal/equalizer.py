from __future__ import annotations

import asyncio
import logging
import os
import pathlib
import re
import time
import traceback
from typing import TYPE_CHECKING, Any, Mapping, Tuple, TypeVar

import youtube_dl
import requests
from pedalboard import Delay, LowpassFilter, Pedalboard, PitchShift, Reverb, Resample  # type: ignore
from pedalboard.io import ReadableAudioFile, WriteableAudioFile

from .modes import EQProcessMode, ResampleProcessMode, SlowedReverbProcessMode, EQTYPES
from .models import PartialYoutubeVideo, YoutubeVideo

if TYPE_CHECKING:
    from numpy import ndarray, dtype, float32

log = logging.getLogger(__name__)


class Options:
    def __init__(self, f: str = "assets") -> None:
        self.FOLDER = f
        self.PROCESSED_FOLDER = f"{f}/processed"


options = Options()


def setup():
    # TODO: deprecate this
    # no need to setup
    os.makedirs(options.FOLDER, exist_ok=True)
    os.makedirs(options.PROCESSED_FOLDER, exist_ok=True)


if __name__ == "__main__":
    setup()

YoutubeUrlRegex = re.compile(
    r"""(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/ ]{11})"""
)
YoutubeIdRegex = re.compile(r"""([^"&?\/ ]{11})""")
AudioType = TypeVar("AudioType", bound="ndarray[Any, dtype[float32]]")
BoardType = Tuple[EQProcessMode, EQTYPES]


class YoutubeDLError(Exception):
    ...


class Equalizer:
    boards: Mapping[
        EQProcessMode, Mapping[SlowedReverbProcessMode | ResampleProcessMode, Any]
    ] = {
        EQProcessMode.Resample: {
            ResampleProcessMode.Down: Pedalboard([Resample(target_sample_rate=4000)]),
            ResampleProcessMode.Up: Pedalboard([Resample(target_sample_rate=16000)]),
        },
        EQProcessMode.SlowedReverb: {
            SlowedReverbProcessMode.Low: Pedalboard(
                [
                    Delay(delay_seconds=0.25, mix=1.0),
                    PitchShift(semitones=-3.5),
                    Reverb(width=0.8),
                ]
            ),
            SlowedReverbProcessMode.Mid: Pedalboard(
                [
                    Delay(delay_seconds=0.25, mix=1.0),
                    PitchShift(semitones=-4.5),
                    Reverb(width=0.8),
                ]
            ),
            SlowedReverbProcessMode.High: Pedalboard(
                [
                    Delay(delay_seconds=0.25, mix=1.0),
                    PitchShift(semitones=-5.5),
                    Reverb(width=0.8),
                ]
            ),
        },
    }

    def __init__(
        self,
        *,
        # file: AudioFile | None = None,
        audio: "AudioType | None" = None,
        samplerate: float | None = None,
        done: "AudioType | None" = None,
    ):
        # self.file = file

        self.audio = audio
        self.samplerate = samplerate

        self.done = done

    @classmethod
    def read_file(
        cls,
        video: PartialYoutubeVideo | None = None,
        *,
        file_name: str | None = None,
        extension: str = "mp3",
        path: str | None = None,
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
        log.info(f"reading {file_name=} {extension=}")
        file = ReadableAudioFile(f"{path}/{file_name}.{extension}")
        with file as f:
            audio = f.read(f.frames)
            samplerate = f.samplerate

        return cls(
            # file=file,
            audio=audio,
            samplerate=samplerate,
        )

    def write_file(
        self,
        video: PartialYoutubeVideo | None = None,
        board_name: BoardType = (
            EQProcessMode.SlowedReverb,
            SlowedReverbProcessMode.Mid,
        ),
        *,
        title: str | None = None,
        extension: str = "mp3",
        path: str | None = None,
    ):
        def wrapper(
            video: PartialYoutubeVideo | None,
            board_name: BoardType,
            title: str | None,
            extension: str,
            path: str | None,
        ):
            if not path:
                path = options.PROCESSED_FOLDER
            if self.done is None:
                raise Exception("please run first")

            if not video:
                if not title:
                    raise Exception("title is required")
            else:
                title = video.title
                extension = video.ext

            title = f"{title}-{board_name[1]}"
            assert isinstance(self.samplerate, float)
            file = pathlib.Path(f"{path}/{title}.{extension}")
            file.parent.mkdir(parents=True, exist_ok=True)
            with WriteableAudioFile(
                str(file),
                self.samplerate,
                self.done.shape[0],
            ) as f:
                f.write(self.done)

            return title

        return asyncio.get_event_loop().run_in_executor(
            None, wrapper, video, board_name, title, extension, path
        )

    async def save_local(
        self,
        video: PartialYoutubeVideo,
        board_name: BoardType,
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
        board_name: BoardType = (
            EQProcessMode.SlowedReverb,
            SlowedReverbProcessMode.Mid,
        ),
        run_once: bool = True,
    ):
        """
        set run_once to False to run the equalizer with multiple boards
        """

        def wrapper(board_name: BoardType, run_once: bool):
            if self.done is not None and run_once:
                return self.done

            if self.audio is not None and self.samplerate is not None:
                board = self.boards.get(EQProcessMode(board_name[0]))
                if board is None:
                    raise Exception("Board not found")
                board = board.get(board_name[1])
                if board is None:
                    raise Exception("Board not found")

                log.info(f"proccessing with {board_name=}")
                self.done = board(self.audio, self.samplerate)
                return self.done

            raise Exception("No file to process")

        loop = asyncio.get_event_loop()
        return loop.run_in_executor(None, wrapper, board_name, run_once)


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
    board_name: BoardType,
    extension: str = "mp3",
    copy_to_clipboard: bool = False,  # debug purposes, remove later,
    delete_after=None,  # TODO: datetime for when to delete file, especially for pytest
):
    if video:
        title = video.title
        extension = video.ext
    else:
        if not (title and extension):
            raise Exception(
                "cannot make full_qualified_name for given inputs to upload"
            )

    full_qualified_name = pathlib.Path(
        f"./{options.PROCESSED_FOLDER}/{title}-{board_name[1]}.{extension}"
    )

    return upload_to_transferfilesh(full_qualified_name, clipboard=copy_to_clipboard)


if __name__ == "__main__":
    import sys
    from typing import Dict

    loop = asyncio.get_event_loop()
    UPLOAD_FILE = False
    YOUTUBE_LINK = ""
    ID, TITLE = (
        "h7MYJghRWt0",
        "Die For You ft. Grabbitz _ Official Music Video _ VALORANT Champions 2021",
    )

    if len(sys.argv) > 1:
        if len(sys.argv) > 2:
            # arg 3 -> save
            UPLOAD_FILE = True
        YOUTUBE_LINK = str(sys.argv[1])

    if YOUTUBE_LINK:
        video = loop.run_until_complete(youtube_download(YOUTUBE_LINK))
    else:
        video = PartialYoutubeVideo(id=ID, title=TITLE)

    eq_range: Dict[int, BoardType] = {
        # 0: (EQProcessMode.SlowedReverb, "45_08"),
        1: (EQProcessMode.SlowedReverb, "35_08"),
        # 2: (EQProcessMode.SlowedReverb, "55_08"),
    }

    eq = Equalizer.read_file(video)
    for idx, board_name in eq_range.items():
        loop.run_until_complete(eq.run(board_name=board_name, run_once=False))
        loop.run_until_complete(eq.save_local(video, board_name))
        if UPLOAD_FILE:
            loop.run_until_complete(upload_local(video, board_name=board_name))
