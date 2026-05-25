"""
File: Amit Tzadok - Speaker Diarization via pyannote-audio
Author: Amit Tzadok <amit.tzadok@icloud.com>
Description: Turn-based speaker separation using pyannote speaker-diarization-3.1.
"""

import json
import wave
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from pyannote.audio import Pipeline
from pathlib import Path
import time
import signal
import subprocess


COLORS = ['steelblue', 'darkorange', 'green', 'red']


def seconds_to_timestamp(seconds):
    """Convert float seconds to 'HH:MM:SS,mmm' format expected by speaker_splitter."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    ms = int(round((s - int(s)) * 1000))
    return f"{h:02d}:{m:02d}:{int(s):02d},{ms:03d}"


def export_segments_json(segments, output_path):
    """
    Write diarization segments to JSON compatible with speaker_splitter.py.

    Args:
        segments: list of (start, end, speaker_label) tuples
        output_path: str or Path
    """
    data = {
        "segments": [
            {
                "speaker": label,
                "start": seconds_to_timestamp(start),
                "end": seconds_to_timestamp(end),
            }
            for start, end, label in segments
        ]
    }
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    print(f"Diarization JSON written to: {output_path}")


def load_wave_file(wave_fname):
    """Load WAV file as mono normalized float32."""
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
    file_path = script_dir.parent / "tests" / "recordings" / "podcast_segment.wav"

    if not file_path.exists():
        print(f"File not found: {file_path}")
        return

    audio_array, sample_rate = load_wave_file(str(file_path))
    total_duration = len(audio_array) / sample_rate
    print(f"Loaded: {len(audio_array)} samples @ {sample_rate} Hz ({total_duration:.1f}s)")

    # Run pyannote diarization
    print("Loading pyannote pipeline...")
    from huggingface_hub import get_token
    pipeline = Pipeline.from_pretrained("pyannote/speaker-diarization-3.1",
                                        token=get_token())

    print("Running diarization...")
    diarization = pipeline(str(file_path), num_speakers=2)

    # Collect segments
    segments = [
        (turn.start, turn.end, speaker)
        for turn, _, speaker in diarization.exclusive_speaker_diarization.itertracks(yield_label=True)
    ]
    print(f"Got {len(segments)} segments")

    # Print timeline
    print("\n=== SPEAKER TIMELINE ===")
    for start, end, speaker in segments:
        print(f"{start:.2f}s – {end:.2f}s → {speaker}")

    # Export JSON for speaker_splitter.py
    json_out = file_path.with_suffix('.diarization.json')
    export_segments_json(segments, json_out)

    # Map segments to sample-level labels for waveform coloring
    speakers = sorted(set(s for _, _, s in segments))
    speaker_to_idx = {s: i for i, s in enumerate(speakers)}

    time_axis = np.linspace(0, total_duration, len(audio_array))
    sample_labels = np.full(len(audio_array), -1, dtype=int)
    for start, end, speaker in segments:
        start_idx = np.searchsorted(time_axis, start)
        end_idx = np.searchsorted(time_axis, end)
        sample_labels[start_idx:end_idx] = speaker_to_idx[speaker]

    # Visualization
    fig, ax = plt.subplots(figsize=(14, 5))

    chunk = 256
    n_chunks = len(audio_array) // chunk
    for c in range(n_chunks):
        s = c * chunk
        e = s + chunk
        idx = sample_labels[s]
        color = COLORS[idx % len(COLORS)] if idx >= 0 else 'lightgray'
        ax.plot(time_axis[s:e], audio_array[s:e], color=color, linewidth=0.8, alpha=0.9)

    legend_str = '   '.join(f'{COLORS[i]} = {spk}' for i, spk in enumerate(speakers))
    ax.set_title(f'Speaker Diarization (pyannote-3.1) — {legend_str}\nPress Space to play/pause',
                 fontsize=11)
    ax.set_ylabel('Amplitude')
    ax.set_xlabel('Time (seconds)')
    ax.grid(True, alpha=0.4)

    cursor = ax.axvline(x=0, color='red', linewidth=1.5, alpha=0.85, zorder=5)
    plt.tight_layout()

    # Playback
    state = {'playing': True, 'start_wall': time.time(), 'start_pos': 0.0, 'paused_at': 0.0}
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
        cursor.set_xdata([pos, pos])
        fig.canvas.draw_idle()

    ani = animation.FuncAnimation(  # noqa: F841
        fig, update, interval=40, blit=False, cache_frame_data=False
    )
    plt.show()
    proc.terminate()


if __name__ == "__main__":
    main()
