#!/usr/bin/env python3
"""Extract an original RE4 GameCube one-shot sound cue to a mono WAV.

The source DRS and extracted audio remain private. This converter contains no
game data; it translates the archive's DSP-ADPCM wavetable using the layout
implemented by the matching GameCube sound driver in src/game/snd_iss3.cpp.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
import sys
import wave
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPOSITORY_ROOT / "tools"))

import drs  # noqa: E402


SIT_SIZE = 0x18
WTINST_SIZE = 0x100
WTREGION_SIZE = 0x18
WTSAMPLE_SIZE = 0x10
WTADPCM_SIZE = 0x2E


def be_u16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">H", data, offset)[0]


def be_s16(data: bytes, offset: int) -> int:
    return struct.unpack_from(">h", data, offset)[0]


def be_u32(data: bytes, offset: int) -> int:
    return struct.unpack_from(">I", data, offset)[0]


def checked_slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(
            f"{label} is outside its source: offset={offset:#x} "
            f"size={size:#x} source={len(data):#x}"
        )
    return data[offset : offset + size]


def decode_dsp_adpcm(
    encoded: bytes,
    sample_count: int,
    coefficients: tuple[int, ...],
    history_1: int = 0,
    history_2: int = 0,
) -> list[int]:
    """Decode Nintendo DSP ADPCM frames as programmed by RE4's AX driver."""
    if len(coefficients) != 16:
        raise ValueError("DSP ADPCM needs exactly 16 coefficients")
    samples: list[int] = []
    cursor = 0
    while len(samples) < sample_count:
        if cursor + 8 > len(encoded):
            raise ValueError("DSP ADPCM data ends before the declared sample count")
        header = encoded[cursor]
        cursor += 1
        predictor = (header >> 4) & 7
        scale = 1 << (header & 0x0F)
        coefficient_1 = coefficients[predictor * 2]
        coefficient_2 = coefficients[predictor * 2 + 1]
        frame = encoded[cursor : cursor + 7]
        cursor += 7
        for value in frame:
            for shift in (4, 0):
                nibble = (value >> shift) & 0x0F
                if nibble >= 8:
                    nibble -= 16
                decoded = (
                    ((nibble * scale) << 11)
                    + 1024
                    + coefficient_1 * history_1
                    + coefficient_2 * history_2
                ) >> 11
                decoded = max(-32768, min(32767, decoded))
                samples.append(decoded)
                history_2 = history_1
                history_1 = decoded
                if len(samples) == sample_count:
                    break
            if len(samples) == sample_count:
                break
    return samples


def sound_records(path: Path) -> tuple[bytes, bytes, int, int]:
    archive = drs.Drs(path.read_bytes())
    if archive.snd is None:
        raise ValueError(f"{path} has no embedded sound bank")
    records = {kind: (p0, p1, blob) for kind, p0, p1, blob in archive.snd.records}
    if 1 not in records or 2 not in records:
        raise ValueError("sound bank must contain type 1 metadata and type 2 samples")
    metadata_p0, metadata_p1, metadata = records[1]
    samples_p0, samples_p1, samples = records[2]
    if (metadata_p0, metadata_p1) != (samples_p0, samples_p1):
        raise ValueError("sound metadata and sample bank parameters do not agree")
    return metadata, samples, metadata_p0, metadata_p1


def cue_info(metadata: bytes, samples: bytes, cue: int) -> dict[str, object]:
    block_offset = be_u32(metadata, 0)
    checked_slice(metadata, block_offset, 16, "ISS block header")
    cue_count, wavetable_offset, sit_offset, sequence_offset = struct.unpack_from(
        ">4I", metadata, block_offset
    )
    if cue < 0 or cue >= cue_count:
        raise ValueError(f"cue {cue} is outside the bank's 0..{cue_count - 1} range")

    wavetable = block_offset + wavetable_offset
    sit = block_offset + sit_offset + cue * SIT_SIZE
    checked_slice(metadata, sit, SIT_SIZE, f"SIT cue {cue}")
    program = be_u16(metadata, sit)
    flags = be_u16(metadata, sit + 0x16)
    if flags & 0x8000:
        raise ValueError(f"cue {cue} is a dummy entry")
    if flags & 0x0004:
        raise ValueError(f"cue {cue} is a sequence, not a one-shot sample")

    checked_slice(metadata, wavetable, 24, "wavetable header")
    _, instrument_offset, region_offset, _, sample_offset, adpcm_offset = struct.unpack_from(
        ">6I", metadata, wavetable
    )
    instrument = wavetable + instrument_offset + (program >> 8) * WTINST_SIZE
    note = program & 0xFF
    region_index = be_u16(metadata, instrument + note * 2)
    region = wavetable + region_offset + region_index * WTREGION_SIZE
    checked_slice(metadata, region, WTREGION_SIZE, "wavetable region")
    (
        unity_note,
        _key_group,
        fine_tune,
        _attenuation,
        loop_start,
        loop_length,
        _articulation_index,
        sample_index,
    ) = struct.unpack_from(">BBhiiIII", metadata, region)
    if loop_length:
        raise ValueError(f"cue {cue} loops; the Dreamcast demo extractor supports one-shots")

    sample = wavetable + sample_offset + sample_index * WTSAMPLE_SIZE
    checked_slice(metadata, sample, WTSAMPLE_SIZE, "wavetable sample")
    sample_format, sample_rate, nibble_offset, sample_count, adpcm_index = struct.unpack_from(
        ">HHIIH", metadata, sample
    )
    if sample_format != 0:
        raise ValueError(f"cue {cue} uses unsupported sample format {sample_format}")

    adpcm = wavetable + adpcm_offset + adpcm_index * WTADPCM_SIZE
    checked_slice(metadata, adpcm, WTADPCM_SIZE, "ADPCM coefficients")
    values = struct.unpack_from(">23h", metadata, adpcm)
    coefficients = tuple(values[:16])
    history_1 = values[18]
    history_2 = values[19]

    byte_offset = nibble_offset // 2
    encoded_bytes = math.ceil(sample_count / 14) * 8
    encoded = checked_slice(samples, byte_offset, encoded_bytes, "ADPCM sample")
    pitch_cents = (note - unity_note) * 100 + fine_tune
    output_rate = round(sample_rate * math.pow(2.0, pitch_cents / 1200.0))
    return {
        "cue": cue,
        "cue_count": cue_count,
        "program": program,
        "flags": flags,
        "sequence_offset": sequence_offset,
        "region_index": region_index,
        "sample_index": sample_index,
        "sample_rate": sample_rate,
        "pitch_cents": pitch_cents,
        "output_rate": output_rate,
        "sample_count": sample_count,
        "duration_seconds": sample_count / output_rate,
        "nibble_offset": nibble_offset,
        "loop_start": loop_start,
        "loop_length": loop_length,
        "coefficients": coefficients,
        "history_1": history_1,
        "history_2": history_2,
        "encoded": encoded,
    }


def write_wav(path: Path, info: dict[str, object]) -> None:
    decoded = decode_dsp_adpcm(
        info["encoded"],
        info["sample_count"],
        info["coefficients"],
        info["history_1"],
        info["history_2"],
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(info["output_rate"])
        output.writeframes(struct.pack(f"<{len(decoded)}h", *decoded))


def report(info: dict[str, object], source: Path, output: Path, bank: tuple[int, int]) -> dict[str, object]:
    public = {key: value for key, value in info.items() if key not in {"encoded", "coefficients"}}
    public.update(
        {
            "source": str(source),
            "output": str(output),
            "bank_parameters": list(bank),
            "format": "mono-pcm16-wav",
        }
    )
    return public


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="private original RE4 GameCube DRS archive")
    parser.add_argument("cue", type=lambda value: int(value, 0), help="SndCall cue number")
    parser.add_argument("output", type=Path, help="output mono PCM16 WAV")
    args = parser.parse_args()

    metadata, samples, bank_p0, bank_p1 = sound_records(args.source)
    info = cue_info(metadata, samples, args.cue)
    write_wav(args.output, info)
    print(json.dumps(report(info, args.source, args.output, (bank_p0, bank_p1)), indent=2))


if __name__ == "__main__":
    main()
