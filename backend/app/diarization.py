import os
from pathlib import Path

import numpy as np
import soundfile as sf
from pyannote.audio import Pipeline

_pipeline = None

# Segments shorter than this, sandwiched between two same-speaker turns from
# someone else, are almost always boundary misattributions rather than real
# speaker switches — merge them into the surrounding turn.
MIN_BLIP_DURATION = 1.0


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=os.environ["HF_TOKEN"],
        )
    return _pipeline


def seconds_to_timestamp(seconds):
    """Convert float seconds to 'HH:MM:SS,mmm' format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"


def remove_blips(segments, min_duration=MIN_BLIP_DURATION):
    """Merge short segments sandwiched between two same-speaker turns from a
    different speaker into a single turn for that surrounding speaker.

    e.g. [A 0-10, B 10-10.4, A 10.4-20] -> [A 0-20] when B's turn is < min_duration.
    """
    segments = [dict(s) for s in sorted(segments, key=lambda s: s["start_seconds"])]
    merged = True
    while merged:
        merged = False
        for i in range(1, len(segments) - 1):
            prev_seg, seg, next_seg = segments[i - 1], segments[i], segments[i + 1]
            duration = seg["end_seconds"] - seg["start_seconds"]
            if duration < min_duration and prev_seg["speaker"] == next_seg["speaker"] != seg["speaker"]:
                prev_seg["end_seconds"] = next_seg["end_seconds"]
                prev_seg["end"] = next_seg["end"]
                del segments[i:i + 2]
                merged = True
                break
    return segments


def diarize(path, num_speakers=None):
    """Run speaker diarization on an audio file.

    Returns a list of {"speaker", "start", "end"} segments, with start/end
    as both raw seconds and "HH:MM:SS,mmm" timestamps.
    """
    pipeline = get_pipeline()
    kwargs = {"num_speakers": num_speakers} if num_speakers else {}
    diarization = pipeline(path, **kwargs)

    segments = [
        {
            "speaker": speaker,
            "start_seconds": turn.start,
            "end_seconds": turn.end,
            "start": seconds_to_timestamp(turn.start),
            "end": seconds_to_timestamp(turn.end),
        }
        for turn, _, speaker in diarization.exclusive_speaker_diarization.itertracks(yield_label=True)
    ]
    return remove_blips(segments)


def extract_speaker_tracks(path, segments, dest_dir):
    """Cut the source audio at each diarized turn and concatenate every
    speaker's turns into their own WAV file.

    Returns {speaker_label: output_path}.
    """
    audio, sr = sf.read(path, always_2d=True)
    stem = Path(path).stem

    chunks_by_speaker = {}
    for seg in segments:
        start = int(seg["start_seconds"] * sr)
        end = int(seg["end_seconds"] * sr)
        chunks_by_speaker.setdefault(seg["speaker"], []).append(audio[start:end])

    out_paths = {}
    for speaker, chunks in chunks_by_speaker.items():
        out_path = Path(dest_dir) / f"{stem}_{speaker}.wav"
        sf.write(str(out_path), np.concatenate(chunks, axis=0), sr)
        out_paths[speaker] = str(out_path)
    return out_paths
