"""Unit tests for audio/speech_features/f0.py"""

import io
import os
import sys
import tempfile
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'speech_features'))
from f0 import load_wave_file, get_f0_and_voiced, detect_turns

try:
    import numba  # noqa: F401
    _NUMBA_AVAILABLE = True
except ImportError:
    _NUMBA_AVAILABLE = False

requires_numba = pytest.mark.skipif(
    not _NUMBA_AVAILABLE,
    reason="numba not available (NumPy version incompatibility)"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_temp_wav(samples: np.ndarray, sample_rate: int = 16000, num_channels: int = 1) -> str:
    """Write a numpy int16 array to a temp WAV file; caller must unlink."""
    f = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    with wave.open(f, 'wb') as wf:
        wf.setnchannels(num_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(samples.astype(np.int16).tobytes())
    f.close()
    return f.name


# ---------------------------------------------------------------------------
# load_wave_file
# ---------------------------------------------------------------------------

class TestLoadWaveFile:
    def test_mono_normalized(self):
        samples = np.array([0, 16384, -16384, 32767], dtype=np.int16)
        path = _write_temp_wav(samples)
        try:
            audio, sr = load_wave_file(path)
            assert sr == 16000
            assert len(audio) == 4
            assert np.max(np.abs(audio)) == pytest.approx(1.0, abs=1e-4)
        finally:
            os.unlink(path)

    def test_stereo_takes_left_channel(self):
        left = np.array([10000, -10000, 10000, -10000], dtype=np.int16)
        right = np.zeros(4, dtype=np.int16)
        interleaved = np.empty(8, dtype=np.int16)
        interleaved[0::2] = left
        interleaved[1::2] = right
        path = _write_temp_wav(interleaved, num_channels=2)
        try:
            audio, sr = load_wave_file(path)
            assert len(audio) == 4
            assert np.max(np.abs(audio)) == pytest.approx(1.0, abs=1e-4)
        finally:
            os.unlink(path)

    def test_sample_rate_preserved(self):
        samples = np.zeros(100, dtype=np.int16)
        path = _write_temp_wav(samples, sample_rate=44100)
        try:
            _, sr = load_wave_file(path)
            assert sr == 44100
        finally:
            os.unlink(path)

    def test_silent_audio_no_nan_or_inf(self):
        samples = np.zeros(100, dtype=np.int16)
        path = _write_temp_wav(samples)
        try:
            audio, _ = load_wave_file(path)
            assert not np.any(np.isnan(audio))
            assert not np.any(np.isinf(audio))
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# get_f0_and_voiced
# ---------------------------------------------------------------------------

class TestGetF0AndVoiced:
    @requires_numba
    def test_output_lengths_consistent(self):
        sr = 22050
        audio = (np.random.randn(sr) * 0.01).astype(np.float32)
        f0, times, voiced = get_f0_and_voiced(audio, sr)
        assert len(f0) == len(times) == len(voiced)

    @requires_numba
    def test_sine_wave_detects_approximate_f0(self):
        sr = 22050
        freq = 220.0  # Hz — within pyin's F3–E5 window
        t = np.linspace(0, 1.0, sr, endpoint=False)
        audio = (np.sin(2 * np.pi * freq * t) * 0.8).astype(np.float32)
        f0, times, voiced = get_f0_and_voiced(audio, sr)
        voiced_f0 = f0[voiced > 0.5]
        assert len(voiced_f0) > 0, "pyin should mark frames as voiced for a pure sine"
        # Allow ±30 Hz after median filtering
        assert np.median(voiced_f0) == pytest.approx(freq, abs=30)

    @requires_numba
    def test_silence_has_no_voiced_frames(self):
        sr = 22050
        audio = np.zeros(sr, dtype=np.float32)
        f0, times, voiced = get_f0_and_voiced(audio, sr)
        assert np.sum(voiced > 0.5) == 0


# ---------------------------------------------------------------------------
# detect_turns
# ---------------------------------------------------------------------------

class TestDetectTurns:
    def test_single_turn(self):
        voiced = np.array([0.0] * 5 + [0.9] * 20 + [0.0] * 5)
        turns = detect_turns(voiced, min_turn_frames=12)
        assert turns == [(5, 25)]

    def test_turn_below_min_length_dropped(self):
        voiced = np.array([0.0] * 5 + [0.9] * 11 + [0.0] * 5)
        turns = detect_turns(voiced, min_turn_frames=12)
        assert turns == []

    def test_turn_exactly_at_min_length_kept(self):
        voiced = np.array([0.0] * 5 + [0.9] * 12 + [0.0] * 5)
        turns = detect_turns(voiced, min_turn_frames=12)
        assert turns == [(5, 17)]

    def test_two_turns_separated_by_silence(self):
        voiced = np.array([0.9] * 15 + [0.0] * 10 + [0.9] * 15)
        turns = detect_turns(voiced, min_turn_frames=12)
        assert turns == [(0, 15), (25, 40)]

    def test_all_silence_returns_empty(self):
        voiced = np.zeros(50)
        assert detect_turns(voiced) == []

    def test_all_voiced_returns_one_turn(self):
        voiced = np.ones(50)
        turns = detect_turns(voiced, min_turn_frames=12)
        assert turns == [(0, 50)]

    def test_voiced_threshold_boundary(self):
        # Exactly 0.65 should NOT be treated as speech (is_speech = voiced_flag > 0.65)
        voiced = np.array([0.65] * 20)
        turns = detect_turns(voiced, min_turn_frames=12)
        assert turns == []

        # Just above threshold should be speech
        voiced2 = np.array([0.66] * 20)
        turns2 = detect_turns(voiced2, min_turn_frames=12)
        assert len(turns2) == 1
