from .modes import *
from .models import *
from .equalizer import (
    BoardType,
    Options,
    Equalizer,
    YoutubeDLError,
    upload_local,
    upload_to_transferfilesh,
    parse_youtube_id,
    youtube_download,
    options,
    YoutubeIdRegex,
    YoutubeUrlRegex,
)

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .equalizer import AudioType
