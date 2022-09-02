from typing import Optional

from pydantic import BaseModel, validator


class PartialYoutubeVideo(BaseModel):
    id: str
    title: str
    url: str = None  # type: ignore
    file_name: str = None  # type: ignore
    safe_title: str = None  # type: ignore
    ext: str = "mp3"

    def __str__(self):
        return self.title

    def __repr__(self):
        return self.file_name

    def __eq__(self, other):
        if isinstance(other, PartialYoutubeVideo):
            return self.id == other.id
        if isinstance(other, str):
            return self.id == other
        raise NotImplementedError

    def __hash__(self):
        return hash(self.id)

    @validator("url", always=True)
    def define_url(cls, v, values):
        if isinstance(v, str):
            return v

        return f"https://www.youtube.com/watch?v={values['id']}"

    @validator("file_name", always=True)
    def define_file_name(cls, v, values):
        if isinstance(v, str):
            return v

        return f"{values['title']}-{values['id']}"

    @validator("safe_title", always=True)
    def define_safe_title(cls, v, values):
        if isinstance(v, str):
            return v

        return values["file_name"].rsplit(f"-{values['id']}", 1)[0]

    class Config:
        validate_assignment = True


class YoutubeVideo(PartialYoutubeVideo):
    alt_title: Optional[str] = None  # A secondary title of the video
    display_id: str  # An alternative identifier for the video
    uploader: str  # Full name of the video uploader
    license: Optional[str] = None  # License name the video is licensed under
    creator: Optional[str] = None  # The creator of the video
    release_date: Optional[
        str
    ] = None  # The date (YYYYMMDD) when the video was released
    timestamp: Optional[
        int
    ] = None  # UNIX timestamp of the moment the video became available
    upload_date: str  # Video upload date (YYYYMMDD)
    uploader_id: str  # Nickname or id of the video uploader
    channel: str  # Full name of the channel the video is uploaded on
    channel_id: str  # Id of the channel
    location: Optional[str] = None  # Physical location where the video was filmed
    duration: int  # Length of the video in seconds
    view_count: int  # How many users have watched the video on the platform
    like_count: int  # Number of positive ratings of the video
    dislike_count: Optional[int] = None  # Number of negative ratings of the video
    repost_count: Optional[int] = None  # Number of reposts of the video
    average_rating: Optional[
        int
    ]  # Average rating give by users, the scale used depends on the webpage
    comment_count: Optional[int] = None  # Number of comments on the video
    age_limit: int  # Age restriction for the video (years)
    is_live: Optional[
        bool
    ]  # Whether this video is a live stream or a fixed-length video
    start_time: Optional[
        int
    ] = None  # Time in seconds where the reproduction should start, as specified in the URL
    end_time: Optional[
        int
    ] = None  # Time in seconds where the reproduction should end, as specified in the URL
    format: str  # A human-readable description of the format
    format_id: str  # Format code specified by --format
    format_note: str  # Additional info about the format
    width: Optional[int]  # Width of the video
    height: Optional[int]  # Height of the video
    resolution: Optional[str] = None  # Textual description of width and height
    autonumber: Optional[int] = None

    @validator("file_name", always=True)
    def define_file_name(cls, v, values):
        if isinstance(v, str):
            return v

        return f"{values['title']}-{values['id']}"
