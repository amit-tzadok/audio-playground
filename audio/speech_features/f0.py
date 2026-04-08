"""
File: Amit Tzadok - Speaker Detection by Pitch (Improved Turn-Based)
Author: Amit Tzadok <amit.tzadok@icloud.com>
Description: Clean turn-based speaker detection for two girls speaking in turns.
"""

import wave
import numpy as np
import matplotlib.pyplot as plt
from scipy.ndimage import median_filter
import librosa
from sklearn.cluster import KMeans


def load_wave_file(wave_fname):
    """Load WAV file as mono normalized audio"""
    with wave.open(wave_fname, 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        num_channels = wav_file.getnchannels()
        raw_data = wav_file.readframes(wav_file.getnframes())
        audio_array = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
        if num_channels == 2:
            audio_array = audio_array.reshape(-1, 2)[:, 0]
        audio_array /= (np.max(np.abs(audio_array)) + 1e-8)
        return audio_array, sample_rate


def get_f0_and_voiced(audio_array, sample_rate, hop_length=256):
    """Get F0 using pyin"""
    f0, voiced_flag, _ = librosa.pyin(
        y=audio_array,
        fmin=librosa.note_to_hz('F3'),   # ~174 Hz
        fmax=librosa.note_to_hz('E5'),   # ~659 Hz
        sr=sample_rate,
        hop_length=hop_length,
        frame_length=2048,
        fill_na=0.0
    )
    f0 = median_filter(f0, size=7)
    times = librosa.frames_to_time(np.arange(len(f0)), sr=sample_rate, hop_length=hop_length)
    return f0, times, voiced_flag


def detect_turns(voiced_flag, min_turn_frames=12):
    """Detect contiguous speech turns"""
    is_speech = voiced_flag > 0.65
    turns = []
    i = 0
    n = len(is_speech)
    while i < n:
        if not is_speech[i]:
            i += 1
            continue
        start = i
        while i < n and is_speech[i]:
            i += 1
        if (i - start) >= min_turn_frames:
            turns.append((start, i))
    return turns


def main():
    from pathlib import Path
    script_dir = Path(__file__).parent
    recordings_folder = script_dir.parent / "tests" / "recordings"
    file_path = recordings_folder / "mika_and_amit.wav"

    if not file_path.exists():
        print(f"File not found: {file_path}")
        print("Please make sure the file is in the correct folder or update the path.")
        return

    audio_array, sample_rate = load_wave_file(str(file_path))
    print(f"Loaded: {len(audio_array)} samples @ {sample_rate} Hz")

    # Get F0
    f0_array, times, voiced_flag = get_f0_and_voiced(audio_array, sample_rate)

    # Global clustering to find the two pitch centers
    reliable_mask = (f0_array > 170) & (f0_array < 380) & (voiced_flag > 0.6)
    if np.sum(reliable_mask) < 50:
        print("Not enough voiced data to detect two speakers.")
        return

    kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
    kmeans.fit(f0_array[reliable_mask].reshape(-1, 1))
    centers = np.sort(kmeans.cluster_centers_.flatten())

    print(f"\nDetected pitch centers:")
    print(f"Speaker 0 (lower) ≈ {centers[0]:.0f} Hz")
    print(f"Speaker 1 (higher) ≈ {centers[1]:.0f} Hz")

    # Detect turns
    turns = detect_turns(voiced_flag, min_turn_frames=12)
    print(f"Detected {len(turns)} speech turns")

    # Assign speaker to each entire turn
    speaker_array = np.full(len(f0_array), -1, dtype=int)
    for start, end in turns:
        segment_f0 = f0_array[start:end]
        valid_f0 = segment_f0[(segment_f0 > 170) & (segment_f0 < 380)]
        if len(valid_f0) < 8:
            continue
        median_f0 = np.median(valid_f0)
        # Assign to closest center
        sp = 0 if abs(median_f0 - centers[0]) < abs(median_f0 - centers[1]) else 1
        speaker_array[start:end] = sp

    # Visualization
    time_axis = np.linspace(0, len(audio_array)/sample_rate, len(audio_array))
    colors = {-1: 'lightgray', 0: 'blue', 1: 'orange'}
    hop_size = 256

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    # Waveform colored by speaker
    i = 0
    while i < len(speaker_array):
        j = i + 1
        while j < len(speaker_array) and speaker_array[j] == speaker_array[i]:
            j += 1
        start_sample = i * hop_size
        end_sample = min(j * hop_size, len(audio_array))
        ax1.plot(time_axis[start_sample:end_sample], audio_array[start_sample:end_sample],
                 color=colors[speaker_array[i]], linewidth=1.0, alpha=0.85)
        i = j

    ax1.set_title('Two Speakers by Pitch - Turn-Based (Blue = Lower Pitch Girl, Orange = Higher Pitch Girl)')
    ax1.set_ylabel('Amplitude')
    ax1.grid(True)

    # F0 plot
    ax2.plot(times, f0_array, color='gray', alpha=0.4, label='F0 contour')
    for sp in [0, 1]:
        mask = speaker_array == sp
        if np.any(mask):
            avg_f0 = np.mean(f0_array[mask])
            ax2.scatter(times[mask], f0_array[mask], color=colors[sp], s=12,
                        label=f'Speaker {sp} (avg {avg_f0:.0f} Hz)')
    ax2.set_xlabel('Time (seconds)')
    ax2.set_ylabel('F0 (Hz)')
    ax2.legend()
    ax2.grid(True)

    plt.tight_layout()
    plt.show()

    # Print timeline
    print("\n=== SPEAKER TIMELINE ===")
    current_sp = speaker_array[0]
    seg_start = 0
    for i in range(1, len(speaker_array)):
        if speaker_array[i] != current_sp:
            if current_sp != -1:
                valid_f0 = f0_array[seg_start:i]
                valid_f0 = valid_f0[valid_f0 > 0]
                if len(valid_f0) > 0:
                    print(f"{times[seg_start]:.2f} – {times[i]:.2f} s → Speaker {current_sp} (avg {np.mean(valid_f0):.0f} Hz)")
            seg_start = i
            current_sp = speaker_array[i]
    # Final segment
    if current_sp != -1:
        valid_f0 = f0_array[seg_start:]
        valid_f0 = valid_f0[valid_f0 > 0]
        if len(valid_f0) > 0:
            print(f"{times[seg_start]:.2f} – {times[-1]:.2f} s → Speaker {current_sp} (avg {np.mean(valid_f0):.0f} Hz)")


if __name__ == "__main__":
    main()