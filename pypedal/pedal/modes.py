import enum
from typing import Mapping, TypeVar


class SlowedReverbProcessMode(str, enum.Enum):
    Low = "35_08"
    Mid = "45_08"
    High = "55_08"


class ResampleProcessMode(str, enum.Enum):
    Down = "4000"
    Up = "16000"


EQTYPES = TypeVar("EQTYPES", SlowedReverbProcessMode, ResampleProcessMode)


class EQProcessMode(str, enum.Enum):
    SlowedReverb = "slowed_reverb"
    Resample = "resample"


EQProcessModeMapping: Mapping = {
    EQProcessMode.SlowedReverb: SlowedReverbProcessMode,
    EQProcessMode.Resample: ResampleProcessMode,
}
