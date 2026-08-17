import numpy as np
import soundfile as sf


def estimate_f0(path, target_frames=400, frame_size=2048, fmin=60, fmax=500):
    """Track the fundamental frequency (pitch contour) via per-frame
    autocorrelation — no ML model needed. Frame count is fixed regardless
    of file length (like visualize.py's spectrogram) so this stays fast:
    FFT-based autocorrelation per frame instead of numpy's O(n^2)
    np.correlate, and a bounded number of frames instead of one per hop.
    """
    audio, sr = sf.read(path, always_2d=True)
    mono = audio.mean(axis=1)
    n = len(mono)
    duration = n / sr if sr else 0

    hop = max(1, n // target_frames)
    window = np.hanning(frame_size)

    times = []
    freqs = []
    for start in range(0, max(1, n), hop):
        frame = mono[start:start + frame_size]
        if len(frame) < frame_size:
            frame = np.pad(frame, (0, frame_size - len(frame)))
        frame = (frame - np.mean(frame)) * window

        f0 = _pick_pitch(_autocorrelation(frame), sr, fmin, fmax)
        times.append(round(start / sr, 3))
        freqs.append(round(f0, 1) if f0 else None)

        if len(times) >= target_frames:
            break

    voiced = [f for f in freqs if f]
    return {
        "duration": duration,
        "sample_rate": sr,
        "times": times,
        "f0": freqs,
        "mean_f0": round(sum(voiced) / len(voiced), 1) if voiced else None,
        "min_f0": round(min(voiced), 1) if voiced else None,
        "max_f0": round(max(voiced), 1) if voiced else None,
    }


def _autocorrelation(frame):
    n = len(frame)
    size = 1
    while size < 2 * n:
        size *= 2
    spectrum = np.fft.rfft(frame, size)
    power = spectrum * np.conj(spectrum)
    return np.fft.irfft(power)[:n].real


def _pick_pitch(ac, sr, fmin, fmax):
    if ac[0] <= 0:
        return None
    min_lag = int(sr / fmax)
    max_lag = min(int(sr / fmin), len(ac) - 1)
    if min_lag >= max_lag:
        return None
    segment = ac[min_lag:max_lag]
    if len(segment) == 0:
        return None
    peak_lag = min_lag + int(np.argmax(segment))
    strength = ac[peak_lag] / ac[0]
    if strength < 0.35 or peak_lag == 0:
        return None
    return sr / peak_lag
