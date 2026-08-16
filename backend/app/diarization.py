import os
from pathlib import Path

import numpy as np
import soundfile as sf
from pyannote.audio import Pipeline

_pipeline = None
_vad_pipeline = None

MIN_TRIMMED_DURATION = 0.1

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


def get_vad_pipeline():
    global _vad_pipeline
    if _vad_pipeline is None:
        # The standalone "pyannote/voice-activity-detection" pretrained
        # pipeline is an older-format repo that's incompatible with the
        # current pyannote.audio (a huggingface_hub revision-handling
        # error). Build VAD from the same segmentation-3.0 model the
        # diarization pipeline already uses successfully instead.
        from pyannote.audio import Model
        from pyannote.audio.pipelines import VoiceActivityDetection
        model = Model.from_pretrained("pyannote/segmentation-3.0", token=os.environ["HF_TOKEN"])
        _vad_pipeline = VoiceActivityDetection(segmentation=model)
        _vad_pipeline.instantiate({"min_duration_on": 0.0, "min_duration_off": 0.0})
    return _vad_pipeline


def seconds_to_timestamp(seconds):
    """Convert float seconds to 'HH:MM:SS,mmm' format."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"


def merge_consecutive_same_speaker(segments):
    """Merge directly-adjacent segments that share the same speaker into one
    turn. pyannote's diarization can fragment what's really one continuous
    turn into several back-to-back entries for the same speaker (internal
    segmentation-window artifacts) — treating those as separate turns adds
    stretch/fade boundaries that don't correspond to any real speaker
    change.
    """
    segments = sorted(segments, key=lambda s: s["start_seconds"])
    merged = []
    for seg in segments:
        if merged and merged[-1]["speaker"] == seg["speaker"]:
            merged[-1]["end_seconds"] = seg["end_seconds"]
            merged[-1]["end"] = seg["end"]
        else:
            merged.append(dict(seg))
    return merged


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


def trim_to_speech(segments, path):
    """Tighten each segment's boundaries to the actual speech within it,
    using pyannote's voice-activity-detection model — a diarized turn's raw
    boundaries often include a bit of leading/trailing silence or breath
    noise, which otherwise gets stretched/faded along with real speech.

    Best-effort: if VAD fails for any reason (e.g. the HF token hasn't
    accepted that model's gated terms), segments are returned unchanged
    rather than blocking diarization over a refinement step.
    """
    try:
        from pyannote.core import Segment
        vad = get_vad_pipeline()
        speech_timeline = vad(path).get_timeline()
    except Exception as e:
        print(f"trim_to_speech: VAD unavailable, skipping ({e})")
        return segments

    trimmed = []
    for seg in segments:
        window = Segment(seg["start_seconds"], seg["end_seconds"])
        active = speech_timeline.crop(window)
        if active:
            new_start = max(active[0].start, seg["start_seconds"])
            new_end = min(active[-1].end, seg["end_seconds"])
            if new_end - new_start >= MIN_TRIMMED_DURATION:
                seg = dict(seg)
                seg["start_seconds"] = new_start
                seg["end_seconds"] = new_end
                seg["start"] = seconds_to_timestamp(new_start)
                seg["end"] = seconds_to_timestamp(new_end)
        trimmed.append(seg)
    return trimmed


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
    segments = merge_consecutive_same_speaker(segments)
    segments = remove_blips(segments)
    segments = trim_to_speech(segments, path)
    return segments


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
