import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf


def _stretch_audio(chunk, sr, factor):
    """Time-stretch a numpy audio array by `factor` (>1 = faster/shorter,
    <1 = slower/longer), preserving pitch, via ffmpeg's rubberband filter.

    Rubber Band is a phase-vocoder-alternative built for this — its
    formant-preserving mode keeps voice timbre natural at stretch factors
    where ffmpeg's plain WSOLA-based atempo starts to sound robotic.
    """
    if abs(factor - 1.0) < 1e-6 or len(chunk) == 0:
        return chunk
    with tempfile.TemporaryDirectory() as tmp:
        in_path = Path(tmp) / "in.wav"
        out_path = Path(tmp) / "out.wav"
        sf.write(str(in_path), chunk, sr)
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(in_path),
                "-filter:a", f"rubberband=tempo={factor}:formant=preserved",
                str(out_path),
            ],
            check=True, capture_output=True,
        )
        stretched, _ = sf.read(str(out_path), always_2d=True)
        return stretched


def _fade(chunk, sr, fade_ms=8):
    """Short linear fade-in/out so a hard sample-domain cut — which almost
    never lands on a zero-crossing — doesn't produce an audible click."""
    n = int(sr * fade_ms / 1000)
    if n <= 0 or len(chunk) < 2 * n:
        return chunk
    chunk = chunk.copy()
    ramp = np.linspace(0.0, 1.0, n, dtype=chunk.dtype)[:, None]
    chunk[:n] *= ramp
    chunk[-n:] *= ramp[::-1]
    return chunk


def remix_conversation(path, segments, speaker_rates, dest_dir, progress_cb=None):
    """Rebuild the full conversation, time-stretching each speaker's turns
    by their given rate (>1 = faster, <1 = slower, 1 = unchanged) while
    preserving turn order and the original pause lengths between turns.

    speaker_rates: {speaker_label: rate}. Speakers not present default to 1.0.
    progress_cb is accepted for interface compatibility with the Celery task
    but unused — a handful of ffmpeg stretch calls complete in seconds, so
    there's nothing granular worth reporting.
    """
    audio, sr = sf.read(path, always_2d=True)
    segments = sorted(segments, key=lambda s: s["start_seconds"])

    by_speaker = {}
    for seg in segments:
        by_speaker.setdefault(seg["speaker"], []).append(seg)

    # Stretch each speaker's turns together (one ffmpeg call per speaker) so
    # their own natural cadence carries through, then slice the result back
    # into per-turn pieces proportional to each turn's share of that
    # speaker's total original duration.
    stretched_chunks = {}
    for speaker, segs in by_speaker.items():
        factor = speaker_rates.get(speaker, 1.0)
        raw_chunks = [
            _fade(audio[int(s["start_seconds"] * sr):int(s["end_seconds"] * sr)], sr)
            for s in segs
        ]
        concatenated = np.concatenate(raw_chunks, axis=0) if raw_chunks else np.zeros((0, audio.shape[1]))
        stretched = _stretch_audio(concatenated, sr, factor)

        durations = [s["end_seconds"] - s["start_seconds"] for s in segs]
        total = sum(durations) or 1.0
        pieces = []
        cursor = 0
        for d in durations:
            length = int(round(len(stretched) * (d / total)))
            pieces.append(stretched[cursor:cursor + length])
            cursor += length
        stretched_chunks[speaker] = pieces

    # Rebuild the timeline: each turn replaced by its (possibly stretched)
    # audio, with the pause before it scaled by the same factor as the
    # surrounding speakers. A pause is part of the conversation's rhythm —
    # preserving its absolute length while compressing the speech around it
    # makes a sped-up speaker sound like they're leaving dead air; scaling
    # it too keeps the pacing proportional instead.
    cursors = {speaker: 0 for speaker in by_speaker}
    output_pieces = []
    prev_end = 0.0
    prev_speaker = None
    for seg in segments:
        gap = max(seg["start_seconds"] - prev_end, 0.0)
        if gap > 0:
            neighbor_rates = [speaker_rates.get(seg["speaker"], 1.0)]
            if prev_speaker is not None:
                neighbor_rates.append(speaker_rates.get(prev_speaker, 1.0))
            gap_factor = sum(neighbor_rates) / len(neighbor_rates)
            gap = gap / gap_factor
            output_pieces.append(np.zeros((int(gap * sr), audio.shape[1]), dtype=audio.dtype))
        idx = cursors[seg["speaker"]]
        output_pieces.append(_fade(stretched_chunks[seg["speaker"]][idx], sr))
        cursors[seg["speaker"]] += 1
        prev_end = seg["end_seconds"]
        prev_speaker = seg["speaker"]

    output_audio = np.concatenate(output_pieces, axis=0) if output_pieces else audio
    stem = Path(path).stem
    out_path = Path(dest_dir) / f"{stem}_remixed.wav"
    sf.write(str(out_path), output_audio, sr)
    return str(out_path)
