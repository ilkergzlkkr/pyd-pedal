import asyncio
import os
from typing import Any, Dict, List, Literal, Tuple
from urllib.parse import quote

import pytest

from pypedal.pedal.equalizer import (
    Equalizer,
    options,
    upload_local,
    youtube_download,
)
from pypedal.pedal.modes import EQProcessMode, SlowedReverbProcessMode

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


YoutubeVideo = Dict[Literal["id", "url", "title", "name"], Any]


@pytest.fixture
def youtube_videos():
    return [
        {
            "id": "U5QKIISDaCg",
            "url": "https://www.youtube.com/watch?v=U5QKIISDaCg",
            "title": "Aykut Elmas - Salak salak konuşma be",
            "name": "Aykut Elmas - Salak salak konuşma be-U5QKIISDaCg",
        },
        {
            "id": "tZ-pygsZbUs",
            "url": "https://www.youtube.com/watch?v=tZ-pygsZbUs",
            "title": "Aykut elmas-Taka taka tak keser sapı",
            "name": "Aykut elmas-Taka taka tak keser sapı-tZ-pygsZbUs",
        },
        {
            "id": "SuEv03nFPiE",
            "url": "https://www.youtube.com/watch?v=SuEv03nFPiE",
            "title": "Aykut Elmas Ağlama Hadi Oyna",
            "name": "Aykut Elmas Ağlama Hadi Oyna-SuEv03nFPiE",
        },
    ]


async def test_download(file_options, youtube_videos: List[YoutubeVideo]):
    futures = [
        youtube_download(youtube_video["url"]) for youtube_video in youtube_videos
    ]

    results: List[Tuple[str, str, str]] = await asyncio.gather(*futures)

    for idx, (id, title, file_name) in enumerate(results):
        assert futures[idx].done()
        assert id == youtube_videos[idx]["id"]
        assert title == youtube_videos[idx]["title"]
        assert file_name == youtube_videos[idx]["name"]


# @pytest.mark.depends(on=["test_download"])
async def test_processing(file_options, youtube_videos: List[YoutubeVideo]):
    eq_list = [
        Equalizer.read_file(youtube_video["name"]) for youtube_video in youtube_videos
    ]

    futures = [eq.run(board_name=DEFAULT_BOARD) for eq in eq_list]
    await asyncio.gather(*futures)
    assert all(future.done() for future in futures)

    futures = [
        eq.write_file(youtube_videos[idx]["title"], board_name=DEFAULT_BOARD)
        for idx, eq in enumerate(eq_list)
    ]
    titles: List[str] = await asyncio.gather(*futures)

    for idx, title in enumerate(titles):
        assert futures[idx].done()
        assert title == f"{youtube_videos[idx]['title']}-{DEFAULT_BOARD[1]}"


# @pytest.mark.depends(on=["test_processing"])
async def test_upload(file_options, youtube_videos: List[YoutubeVideo]):
    futures = [
        upload_local(
            file_name=youtube_video["title"],
            board_name=DEFAULT_BOARD,
            copy_to_clipboard=True,
        )
        for youtube_video in youtube_videos
    ]

    links: List[str] = await asyncio.gather(*futures)

    for idx, link in enumerate(links):
        assert futures[idx].done()
        assert quote(youtube_videos[idx]["title"]) in link
