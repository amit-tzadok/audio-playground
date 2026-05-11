"""
File: Amit Tzadok - Speaker Diarization via Speaker Embeddings
Author: Amit Tzadok <amit.tzadok@icloud.com>
Description: Turn-based speaker separation using resemblyzer d-vector embeddings.
"""

import wave
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from sklearn.cluster import SpectralClustering
from scipy.ndimage import median_filter
from resemblyzer import VoiceEncoder, preprocess_wav
import time
import signal
import subprocess
from pathlib import Path


def load_wave_file(wave_fname):
    """Load WAV file as mono normalized float32"""
    with wave.open(wave_fname, 'rb') as wav_file:
        sample_rate = wav_file.getframerate()
        num_channels = wav_file.getnchannels()
        raw_data = wav_file.readframes(wav_file.getnframes())
        audio = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32)
        if num_channels == 2:
            audio = audio.reshape(-1, 2)[:, 0]
        audio /= (np.max(np.abs(audio)) + 1e-8)
        return audio, sample_rate


def main():
    script_dir = Path(__file__).parent
    file_path = script_dir.parent / "tests" / "recordings" / "mika_and_amit.wav"

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    # Load original audio for display
    audio_array, sample_rate = load_wave_file(str(file_path))
    total_duration = len(audio_array) / sample_rate
    print(f"Loaded: {len(audio_array)} samples @ {sample_rate} Hz ({total_duration:.1f}s)")

    # resemblyzer: preprocess (resamples to 16kHz internally) + compute embeddings
    print("Computing speaker embeddings...")
    encoder = VoiceEncoder()
    wav16 = preprocess_wav(str(file_path))  # float32 at 16kHz

    # rate=32 → one embedding every ~31ms; finer resolution
    _, embeds, wav_splits = encoder.embed_utterance(wav16, return_partials=True, rate=32)
    print(f"Got {len(embeds)} embeddings")

    # Center time (in seconds) for each embedding window
    embed_times = np.array([(s.start + s.stop) / 2 / 16000 for s in wav_splits])

    # Cosine similarity matrix (embeds are L2-normalised so dot product = cosine sim)
    similarity = np.dot(embeds, embeds.T).clip(0, 1)

    # Spectral clustering — handles non-spherical clusters, standard for diarization
    clustering = SpectralClustering(n_clusters=2, affinity='precomputed',
                                    random_state=42, n_init=20)
    embed_labels = clustering.fit_predict(similarity)

    # Temporal smoothing — suppress isolated one-frame speaker flips
    embed_labels = median_filter(embed_labels, size=9).astype(int)
    print(f"Label distribution: Speaker 0 = {np.sum(embed_labels==0)}, Speaker 1 = {np.sum(embed_labels==1)}")

    # Map embedding labels onto the full audio sample axis via nearest-neighbor
    time_axis = np.linspace(0, total_duration, len(audio_array))
    indices = np.searchsorted(embed_times, time_axis)
    indices = np.clip(indices, 0, len(embed_times) - 1)
    # Pick the closer of left/right embedding
    left = np.clip(indices - 1, 0, len(embed_times) - 1)
    left_dist = np.abs(time_axis - embed_times[left])
    right_dist = np.abs(time_axis - embed_times[indices])
    nearest = np.where(left_dist < right_dist, left, indices)
    sample_labels = embed_labels[nearest]

    # Print timeline
    colors = {0: 'steelblue', 1: 'darkorange'}
    print("\n=== SPEAKER TIMELINE ===")
    prev = sample_labels[0]
    seg_start_t = 0.0
    for i in range(1, len(sample_labels)):
        t = time_axis[i]
        if sample_labels[i] != prev:
            print(f"{seg_start_t:.2f}s – {t:.2f}s → Speaker {prev}")
            seg_start_t = t
            prev = sample_labels[i]
    print(f"{seg_start_t:.2f}s – {total_duration:.2f}s → Speaker {prev}")

    # ── Visualization ──────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True,
                                   gridspec_kw={'height_ratios': [2, 1]})

    # Top: waveform colored by speaker
    chunk = 256
    i = 0
    n_chunks = len(audio_array) // chunk
    for c in range(n_chunks):
        start = c * chunk
        end = start + chunk
        sp = sample_labels[start]
        ax1.plot(time_axis[start:end], audio_array[start:end],
                 color=colors[sp], linewidth=0.8, alpha=0.9)

    ax1.set_title(
        'Speaker Diarization via Embeddings  —  '
        'Blue = Speaker 0   Orange = Speaker 1\n'
        'Press Space to play/pause',
        fontsize=11
    )
    ax1.set_ylabel('Amplitude')
    ax1.grid(True, alpha=0.4)

    # Bottom: per-embedding speaker confidence using mean cluster embeddings
    center0 = np.mean(embeds[embed_labels == 0], axis=0)
    center1 = np.mean(embeds[embed_labels == 1], axis=0)
    center0 /= np.linalg.norm(center0) + 1e-8
    center1 /= np.linalg.norm(center1) + 1e-8

    conf = np.dot(embeds, center0) - np.dot(embeds, center1)
    ax2.fill_between(embed_times, 0, conf, where=conf > 0,
                     color='steelblue', alpha=0.6, label='Speaker 0')
    ax2.fill_between(embed_times, conf, 0, where=conf < 0,
                     color='darkorange', alpha=0.6, label='Speaker 1')
    ax2.axhline(0, color='gray', linewidth=0.8)
    ax2.set_ylabel('Embedding confidence\n(+ = Spk 0, − = Spk 1)')
    ax2.set_xlabel('Time (seconds)')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.4)

    # Playback cursors
    cursor1 = ax1.axvline(x=0, color='red', linewidth=1.5, alpha=0.85, zorder=5)
    cursor2 = ax2.axvline(x=0, color='red', linewidth=1.5, alpha=0.85, zorder=5)

    plt.tight_layout()

    # ── Playback ───────────────────────────────────────────────────────────────
    state = {'playing': True, 'start_wall': time.time(),
             'start_pos': 0.0, 'paused_at': 0.0}
    proc = subprocess.Popen(['afplay', str(file_path)])

    def toggle_playback(event):
        if event.key != ' ':
            return
        if state['playing']:
            proc.send_signal(signal.SIGSTOP)
            elapsed = time.time() - state['start_wall']
            state['paused_at'] = min(state['start_pos'] + elapsed, total_duration)
            state['playing'] = False
        else:
            proc.send_signal(signal.SIGCONT)
            state['start_wall'] = time.time()
            state['start_pos'] = state['paused_at']
            state['playing'] = True

    fig.canvas.mpl_connect('key_press_event', toggle_playback)

    def update(_frame):
        if state['playing']:
            elapsed = time.time() - state['start_wall']
            pos = state['start_pos'] + elapsed
            if pos >= total_duration:
                state['playing'] = False
                state['paused_at'] = 0.0
                pos = total_duration
        else:
            pos = state['paused_at']
        cursor1.set_xdata([pos, pos])
        cursor2.set_xdata([pos, pos])
        fig.canvas.draw_idle()

    ani = animation.FuncAnimation(  # noqa: F841 — must stay referenced
        fig, update, interval=40, blit=False, cache_frame_data=False
    )
    plt.show()
    proc.terminate()


if __name__ == "__main__":
    main()
