import asyncio
import os
from typing import List
from urllib.parse import quote

import pytest

from pypedal.pedal.equalizer import (
    Equalizer,
    options,
    upload_local,
    youtube_download,
)
from pypedal.pedal.modes import EQProcessMode, SlowedReverbProcessMode
from pypedal.pedal.models import PartialYoutubeVideo, YoutubeVideo


# skip this if not specifically testing file
# use it for every test
pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_ALL"), reason="Not testing long run"
)

DEFAULT_BOARD = (EQProcessMode.SlowedReverb, SlowedReverbProcessMode.Low)


@pytest.fixture(scope="session", autouse=True)
def file_options(tmp_path_factory: pytest.TempPathFactory):
    options.__init__("/".join(tmp_path_factory.getbasetemp().parts))
    yield options


@pytest.fixture
def youtube_videos():
    return [
        PartialYoutubeVideo(
            id="U5QKIISDaCg",
            title="Aykut Elmas - Salak salak konuşma be",
        ),
        PartialYoutubeVideo(
            id="tZ-pygsZbUs",
            title="Aykut elmas-Taka taka tak keser sapı",
        ),
        PartialYoutubeVideo(
            id="SuEv03nFPiE",
            title="Aykut Elmas Ağlama Hadi Oyna",
        ),
    ]


async def test_download(file_options, youtube_videos: List[PartialYoutubeVideo]):
    futures = [youtube_download(youtube_video.url) for youtube_video in youtube_videos]

    results: List[YoutubeVideo] = await asyncio.gather(*futures)

    for idx, video in enumerate(results):
        assert futures[idx].done()
        assert video == youtube_videos[idx]
        assert video.id == youtube_videos[idx].id  # same as above
        assert video.title == youtube_videos[idx].title
        assert video.file_name == youtube_videos[idx].file_name
        assert video.safe_title == video.file_name.rsplit(f"-{video.id}", 1)[0]


async def test_processing(file_options, youtube_videos: List[PartialYoutubeVideo]):
    eq_list = [Equalizer.read_file(youtube_video) for youtube_video in youtube_videos]

    futures = [eq.run(board_name=DEFAULT_BOARD) for eq in eq_list]
    await asyncio.gather(*futures)
    assert all(future.done() for future in futures)

    futures = [
        eq.write_file(youtube_videos[idx], board_name=DEFAULT_BOARD)
        for idx, eq in enumerate(eq_list)
    ]
    titles: List[str] = await asyncio.gather(*futures)

    for idx, title in enumerate(titles):
        assert futures[idx].done()
        assert title == f"{youtube_videos[idx].title}-{DEFAULT_BOARD[1]}"


async def test_upload(file_options, youtube_videos: List[PartialYoutubeVideo]):
    futures = [
        upload_local(
            youtube_video,
            board_name=DEFAULT_BOARD,
            copy_to_clipboard=True,
        )
        for youtube_video in youtube_videos
    ]

    links: List[str] = await asyncio.gather(*futures)

    for idx, link in enumerate(links):
        assert futures[idx].done()
        assert quote(youtube_videos[idx].title) in link


async def test_cancel(file_options):
    future = youtube_download("https://www.youtube.com/watch?v=U5QKIISDaCg")

    async def run():
        await future

    task = asyncio.create_task(run())
    await asyncio.sleep(0)  # wait for the task to start
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        future.result()
