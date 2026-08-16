import io
import os
import subprocess
import tempfile
from math import gcd
from pathlib import Path

import numpy as np
import requests
import soundfile as sf
from scipy.signal import resample_poly

TTS_URL = os.environ.get("TTS_URL", "http://tts:8200")
TTS_TIMEOUT = 300
REFERENCE_CLIP_SECONDS = 15
MIN_TARGET_DURATION = 0.3


def _stretch_audio(chunk, sr, factor):
    """Time-stretch a numpy audio array by `factor` (>1 = faster/shorter,
    <1 = slower/longer), preserving pitch, via ffmpeg's rubberband filter.
    Used as a fallback when TTS regeneration isn't available for a turn
    (empty transcription, or a service failure)."""
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


def _resample(audio, from_sr, to_sr):
    if from_sr == to_sr:
        return audio
    g = gcd(from_sr, to_sr)
    return resample_poly(audio, to_sr // g, from_sr // g, axis=0)


def _build_reference_clip(audio, segs, sr, max_seconds=REFERENCE_CLIP_SECONDS):
    """Concatenate this speaker's turns (in order) up to max_seconds, for
    use as the XTTS voice-cloning reference."""
    max_samples = int(max_seconds * sr)
    pieces = []
    total = 0
    for s in segs:
        piece = audio[int(s["start_seconds"] * sr):int(s["end_seconds"] * sr)]
        pieces.append(piece)
        total += len(piece)
        if total >= max_samples:
            break
    if not pieces:
        return np.zeros((0, audio.shape[1]), dtype=audio.dtype)
    return np.concatenate(pieces, axis=0)[:max_samples]


def _transcribe(chunk, sr):
    buf = io.BytesIO()
    sf.write(buf, chunk, sr, format="WAV")
    buf.seek(0)
    resp = requests.post(
        f"{TTS_URL}/transcribe",
        files={"file": ("chunk.wav", buf, "audio/wav")},
        timeout=TTS_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["text"].strip(), data.get("language") or "en"


def _clone_speak(reference_bytes, text, language, target_duration, sr, channels):
    resp = requests.post(
        f"{TTS_URL}/clone_speak",
        files={"reference": ("ref.wav", io.BytesIO(reference_bytes), "audio/wav")},
        data={
            "text": text,
            "language": language,
            "target_duration": max(target_duration, MIN_TARGET_DURATION),
        },
        timeout=TTS_TIMEOUT,
    )
    resp.raise_for_status()
    synthesized, synth_sr = sf.read(io.BytesIO(resp.content), always_2d=True)
    synthesized = _resample(synthesized, synth_sr, sr)
    if synthesized.shape[1] != channels:
        # XTTS outputs mono; duplicate to match the original channel count.
        synthesized = np.repeat(synthesized[:, :1], channels, axis=1)
    return synthesized


def remix_conversation(path, segments, speaker_rates, dest_dir, progress_cb=None):
    """Rebuild the full conversation. For each speaker whose rate != 1.0,
    every one of their turns is transcribed and resynthesized in their
    cloned voice at a calibrated speed (via the isolated tts service) —
    this regenerates the performance rather than mechanically stretching
    the recording, which is what actually makes a sped-up/slowed-down
    speaker sound natural instead of warbly. Turns where transcription
    comes back empty (non-verbal sounds) or the tts service fails fall
    back to a plain pitch-preserving time-stretch. Unchanged speakers
    (rate == 1.0) keep their original audio untouched — no ASR/TTS cost.

    Turn order and the original pause lengths between turns are preserved
    throughout, with pauses scaled by the surrounding speakers' rates so
    pacing stays proportional rather than leaving disproportionate dead air.

    speaker_rates: {speaker_label: rate}. Speakers not present default to 1.0.
    progress_cb(done, total), if given, is called as each turn needing
    regeneration completes — that's the dominant cost, so it's the only
    useful progress signal.
    """
    audio, sr = sf.read(path, always_2d=True)
    channels = audio.shape[1]
    segments = sorted(segments, key=lambda s: s["start_seconds"])

    by_speaker = {}
    for idx, seg in enumerate(segments):
        by_speaker.setdefault(seg["speaker"], []).append((idx, seg))

    total_turns = sum(
        len(segs) for speaker, segs in by_speaker.items()
        if abs(speaker_rates.get(speaker, 1.0) - 1.0) >= 1e-6
    )
    done_turns = 0

    def report():
        if progress_cb and total_turns > 0:
            progress_cb(done_turns, total_turns)

    report()

    pieces = [None] * len(segments)

    for speaker, indexed_segs in by_speaker.items():
        factor = speaker_rates.get(speaker, 1.0)

        if abs(factor - 1.0) < 1e-6:
            for idx, s in indexed_segs:
                pieces[idx] = audio[int(s["start_seconds"] * sr):int(s["end_seconds"] * sr)]
            continue

        reference_clip = _build_reference_clip(audio, [s for _, s in indexed_segs], sr)
        ref_buf = io.BytesIO()
        sf.write(ref_buf, reference_clip, sr, format="WAV")
        reference_bytes = ref_buf.getvalue()
        language = None

        for idx, s in indexed_segs:
            original_chunk = audio[int(s["start_seconds"] * sr):int(s["end_seconds"] * sr)]
            target_duration = (s["end_seconds"] - s["start_seconds"]) / factor

            piece = None
            try:
                text, detected_lang = _transcribe(original_chunk, sr)
                if language is None:
                    language = detected_lang
                if text:
                    piece = _clone_speak(reference_bytes, text, language, target_duration, sr, channels)
            except Exception as e:
                print(f"tts: regeneration failed for a turn, falling back to stretch ({e})")

            if piece is None or len(piece) == 0:
                piece = _stretch_audio(original_chunk, sr, factor)

            pieces[idx] = _fade(piece, sr)
            done_turns += 1
            report()

    # Rebuild the timeline: original gaps scaled by the surrounding
    # speakers' rates (see docstring), each turn replaced by its
    # regenerated/stretched/original audio.
    output_pieces = []
    prev_end = 0.0
    prev_speaker = None
    for idx, seg in enumerate(segments):
        gap = max(seg["start_seconds"] - prev_end, 0.0)
        if gap > 0:
            neighbor_rates = [speaker_rates.get(seg["speaker"], 1.0)]
            if prev_speaker is not None:
                neighbor_rates.append(speaker_rates.get(prev_speaker, 1.0))
            gap_factor = sum(neighbor_rates) / len(neighbor_rates)
            gap = gap / gap_factor
            output_pieces.append(np.zeros((int(gap * sr), channels), dtype=audio.dtype))
        output_pieces.append(pieces[idx])
        prev_end = seg["end_seconds"]
        prev_speaker = seg["speaker"]

    output_audio = np.concatenate(output_pieces, axis=0) if output_pieces else audio
    stem = Path(path).stem
    out_path = Path(dest_dir) / f"{stem}_remixed.wav"
    sf.write(str(out_path), output_audio, sr)
    return str(out_path)
