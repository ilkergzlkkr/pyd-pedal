from pydantic import BaseModel

from pypedal.pedal import YoutubeVideo, PartialYoutubeVideo


class HashModel(BaseModel):
    a: str
    b: str = "213123123"

    def __eq__(self, other) -> bool:
        return self.a == other.a

    def __hash__(self) -> int:
        return hash(self.a)


def test_hash():
    mapping = {}
    mapping[HashModel(a="1")] = "first"
    mapping[HashModel(a="2", b="123123123")] = "second"
    # mapping uses __eq__ and __hash__ to determine if a key is already in the mapping
    # this is not the case for pydantic.BaseModel, its about Cpython's dict implementation

    assert mapping[HashModel(a="2")] == "second"


def test_youtube_hash():
    mapping = {}
    mapping[YoutubeVideo.construct(id="test1")] = "first"
    mapping[YoutubeVideo.construct(id="test2")] = "second"

    assert mapping[PartialYoutubeVideo(id="test2", title="")] == "second"
