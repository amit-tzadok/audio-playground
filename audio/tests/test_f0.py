"""Unit tests for audio/speech_features/f0.py"""

import json
import os
import sys
import tempfile
import wave

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'speech_features'))
from f0 import load_wave_file, seconds_to_timestamp, export_segments_json


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
# seconds_to_timestamp
# ---------------------------------------------------------------------------

class TestSecondsToTimestamp:
    def test_zero(self):
        assert seconds_to_timestamp(0) == "00:00:00,000"

    def test_sub_minute_with_millis(self):
        assert seconds_to_timestamp(5.25) == "00:00:05,250"

    def test_minutes_and_hours(self):
        assert seconds_to_timestamp(3725.5) == "01:02:05,500"

    def test_rounds_milliseconds(self):
        assert seconds_to_timestamp(0.1234) == "00:00:00,123"


# ---------------------------------------------------------------------------
# export_segments_json
# ---------------------------------------------------------------------------

class TestExportSegmentsJson:
    def test_writes_expected_structure(self):
        segments = [
            (0.0, 1.5, "SPEAKER_00"),
            (1.5, 3.0, "SPEAKER_01"),
        ]
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            export_segments_json(segments, path)
            with open(path) as f:
                data = json.load(f)
            assert data == {
                "segments": [
                    {"speaker": "SPEAKER_00", "start": "00:00:00,000", "end": "00:00:01,500"},
                    {"speaker": "SPEAKER_01", "start": "00:00:01,500", "end": "00:00:03,000"},
                ]
            }
        finally:
            os.unlink(path)

    def test_empty_segments(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            export_segments_json([], path)
            with open(path) as f:
                data = json.load(f)
            assert data == {"segments": []}
        finally:
            os.unlink(path)
