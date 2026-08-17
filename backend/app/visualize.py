import numpy as np
import soundfile as sf


def analyze_audio(path, target_waveform_points=1200, target_frames=300, target_bins=96):
    """Compute lightweight waveform peaks + a downsampled spectrogram for
    display — pure numpy/soundfile, no ML models, so this stays fast
    regardless of file length (unlike the diarization pipeline)."""
    audio, sr = sf.read(path, always_2d=True)
    mono = audio.mean(axis=1)
    duration = len(mono) / sr if sr else 0

    return {
        "duration": duration,
        "sample_rate": sr,
        "waveform": _downsample_peaks(mono, target_waveform_points),
        "spectrogram": _compute_spectrogram(mono, target_frames, target_bins),
    }


def _downsample_peaks(mono, target_points):
    n = len(mono)
    if n == 0:
        return []
    chunk = max(1, n // target_points)
    peaks = []
    for i in range(0, n, chunk):
        seg = mono[i:i + chunk]
        if len(seg):
            peaks.append(round(float(np.max(np.abs(seg))), 4))
    return peaks


def _compute_spectrogram(mono, target_frames, target_bins):
    n = len(mono)
    if n == 0:
        return []

    n_fft = 1024
    window = np.hanning(n_fft)
    hop = max(1, n // target_frames)

    frames = []
    for start in range(0, max(1, n), hop):
        seg = mono[start:start + n_fft]
        if len(seg) < n_fft:
            seg = np.pad(seg, (0, n_fft - len(seg)))
        frames.append(np.abs(np.fft.rfft(seg * window)))
        if len(frames) >= target_frames or start + n_fft >= n:
            break

    if not frames:
        return []

    mag = np.array(frames)
    mag_db = np.clip(20 * np.log10(mag + 1e-6), -80, 0)
    normalized = (mag_db + 80) / 80  # 0..1

    freq_bins = normalized.shape[1]
    if freq_bins > target_bins:
        edges = np.linspace(0, freq_bins, target_bins + 1).astype(int)
        grouped = np.zeros((normalized.shape[0], target_bins))
        for i in range(target_bins):
            lo, hi = edges[i], max(edges[i] + 1, edges[i + 1])
            grouped[:, i] = normalized[:, lo:hi].mean(axis=1)
        normalized = grouped

    return normalized.round(3).tolist()
