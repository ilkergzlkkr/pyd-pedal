from __future__ import annotations

import enum
from typing import Literal, Mapping, Type, TypeVar, overload

from pysndfx import AudioEffectsChain

from pedalboard import Delay, LowpassFilter, PitchShift, Reverb, Resample  # type: ignore
from pedalboard.pedalboard import Pedalboard


class SlowedReverbProcessMode(str, enum.Enum):
    # TODO: manually add the values ?
    Low = "085"
    Mid = "08"
    High = "07"


class PitchShiftProcessMode(str, enum.Enum):
    Low = "35_08"
    Mid = "45_08"
    High = "55_08"


class ResampleProcessMode(str, enum.Enum):
    Down = "4000"
    Up = "16000"


EQTYPES = TypeVar(
    "EQTYPES", SlowedReverbProcessMode, ResampleProcessMode, PitchShiftProcessMode
)
PEDALEQTYPES = TypeVar("PEDALEQTYPES", ResampleProcessMode, PitchShiftProcessMode)
# AUDIOFXCHAINTYPES = TypeVar("AUDIOFXCHAINTYPES", SlowedReverbProcessMode)

# fmt: off
class EQProcessMode(str, enum.Enum):
    SlowedReverb = "slowed_reverb"
    PitchShift   = "pitch_shift"
    Resample     = "resample"
# fmt: on

# fmt: off
@overload
def get_mode(mode: Literal[EQProcessMode.SlowedReverb]) -> Type[SlowedReverbProcessMode]:...
@overload
def get_mode(mode: Literal[EQProcessMode.Resample]) -> Type[ResampleProcessMode]:...
@overload
def get_mode(mode: Literal[EQProcessMode.PitchShift]) -> Type[PitchShiftProcessMode]:...
@overload
def get_mode(mode: EQProcessMode) -> Type[SlowedReverbProcessMode] | Type[ResampleProcessMode] | Type[PitchShiftProcessMode]:...
# fmt: on
def get_mode(mode: EQProcessMode):
    if mode == EQProcessMode.SlowedReverb:
        return SlowedReverbProcessMode
    elif mode == EQProcessMode.Resample:
        return ResampleProcessMode
    elif mode == EQProcessMode.PitchShift:
        return PitchShiftProcessMode
    else:
        raise ValueError(f"Unknown mode {mode}")


# fmt: off
@overload
def get_board(mode: EQProcessMode, type: SlowedReverbProcessMode) -> AudioEffectsChain:...
@overload
def get_board(mode: EQProcessMode, type: PEDALEQTYPES) -> Pedalboard:...
@overload
def get_board(mode: EQProcessMode, type: EQTYPES) -> Pedalboard | AudioEffectsChain:...
# fmt: on
def get_board(mode: EQProcessMode, type: EQTYPES) -> Pedalboard | AudioEffectsChain:
    """
    Returns a pedalboard for the given mode and type
    """
    boards: Mapping = {
        EQProcessMode.Resample: {
            ResampleProcessMode.Down: Pedalboard([Resample(target_sample_rate=41.100)]),
            ResampleProcessMode.Up: Pedalboard([Resample(target_sample_rate=16000)]),
        },
        EQProcessMode.PitchShift: {
            PitchShiftProcessMode.Low: Pedalboard(
                [
                    Delay(delay_seconds=0.25, mix=1.0),
                    PitchShift(semitones=-3.5),
                    Reverb(width=0.8),
                ]
            ),
            PitchShiftProcessMode.Mid: Pedalboard(
                [
                    Delay(delay_seconds=0.25, mix=1.0),
                    PitchShift(semitones=-4.5),
                    Reverb(width=0.8),
                ]
            ),
            PitchShiftProcessMode.High: Pedalboard(
                [
                    Delay(delay_seconds=0.25, mix=1.0),
                    PitchShift(semitones=-5.5),
                    Reverb(width=0.8),
                ]
            ),
        },
        EQProcessMode.SlowedReverb: {
            SlowedReverbProcessMode.Low: AudioEffectsChain().speed(0.85).reverb(),
            SlowedReverbProcessMode.Mid: AudioEffectsChain().speed(0.8).reverb(),
            SlowedReverbProcessMode.High: AudioEffectsChain().speed(0.7).reverb(),
        },
    }
    board = boards.get(mode)
    if board is None:
        raise Exception("Board not found")
    board = board.get(type)  # type: ignore
    if not board:
        raise ValueError(f"Invalid {mode=} + {type=}")
    return board
