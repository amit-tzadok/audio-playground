from pathlib import Path

import noisereduce as nr
import soundfile as sf


def denoise_file(path, dest_dir):
    """Reduce steady background noise (hiss, hum, room tone) via spectral
    gating, before the audio is used for diarization/playback/remixing.

    Default full-strength settings (prop_decrease=1.0) chewed noticeably
    into speech clarity/quality on top of the Demucs vocal separation
    already applied upstream — gentler settings knock down residual noise
    without the muffling.
    """
    audio, sr = sf.read(path, always_2d=True)
    reduced = nr.reduce_noise(
        y=audio.T, sr=sr,
        prop_decrease=0.6,
        stationary=True,
        freq_mask_smooth_hz=200,
        time_mask_smooth_ms=100,
    ).T
    stem = Path(path).stem
    out_path = Path(dest_dir) / f"{stem}_denoised.wav"
    sf.write(str(out_path), reduced, sr)
    return str(out_path)
