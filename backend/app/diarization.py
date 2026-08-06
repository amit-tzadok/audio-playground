import os

from pyannote.audio import Pipeline

_pipeline = None


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


def diarize(path, num_speakers=None):
    """Run speaker diarization on an audio file.

    Returns a list of {"speaker", "start", "end"} segments, with start/end
    as both raw seconds and "HH:MM:SS,mmm" timestamps.
    """
    pipeline = get_pipeline()
    kwargs = {"num_speakers": num_speakers} if num_speakers else {}
    diarization = pipeline(path, **kwargs)

    return [
        {
            "speaker": speaker,
            "start_seconds": turn.start,
            "end_seconds": turn.end,
            "start": seconds_to_timestamp(turn.start),
            "end": seconds_to_timestamp(turn.end),
        }
        for turn, _, speaker in diarization.exclusive_speaker_diarization.itertracks(yield_label=True)
    ]
