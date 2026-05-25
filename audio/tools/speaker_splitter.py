"""
Script to separate audio by speaker using timestamp information from JSON.
Requires input WAV file and JSON file containing speaker segments.
Creates individual WAV files for each speaker with silence during other speakers' segments.

Based on approach by Michel-Marie MAUDET (michel.maudet@protonmail.com)
"""

import json
import sys
import argparse
from pydub import AudioSegment
from pathlib import Path

if sys.version_info < (3, 11):
    raise RuntimeError("This script requires Python 3.11 or higher")


def timestamp_to_milliseconds(time_str):
    """
    Convert time string in format "HH:MM:SS,mmm" to milliseconds.

    Args:
        time_str: String in format "HH:MM:SS,mmm"
    Returns:
        int: Time in milliseconds
    """
    time_str = time_str.replace(',', '.')
    try:
        hours, minutes, seconds = time_str.split(':')
        total_ms = int((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)
        return total_ms
    except Exception as e:
        print(f"Error parsing time string '{time_str}': {e}")
        return 0


def create_speaker_audio(input_audio_path, segments_data, speaker_id, output_path):
    """
    Create an audio file for a specific speaker with silence when others are speaking.

    Args:
        input_audio_path (str): Path to the input WAV file
        segments_data (dict): JSON data containing speech segments
        speaker_id (str): ID of the speaker to extract
        output_path (str): Path for the output WAV file
    """
    print(f"Loading audio file: {input_audio_path}")
    try:
        audio = AudioSegment.from_wav(input_audio_path)
    except FileNotFoundError:
        sys.exit(f"Error: Audio file '{input_audio_path}' not found")
    except Exception as e:
        sys.exit(f"Error loading audio file: {e}")

    total_duration = len(audio)
    silent_audio = AudioSegment.silent(duration=total_duration)

    print(f"Processing segments for {speaker_id}...")
    for segment in segments_data['segments']:
        if segment['speaker'] == speaker_id:
            start_ms = timestamp_to_milliseconds(segment['start'])
            end_ms = timestamp_to_milliseconds(segment['end'])
            segment_audio = audio[start_ms:end_ms]
            silent_audio = silent_audio.overlay(segment_audio, position=start_ms)

    print(f"Exporting: {output_path}")
    silent_audio.export(output_path, format="wav")


def process_audio(input_audio_path, json_path):
    """
    Process the audio and create one WAV file per speaker.

    Args:
        input_audio_path (str): Path to the input WAV file
        json_path (str): Path to the JSON file containing speaker segments
    """
    print("Starting audio separation process...")

    if not Path(input_audio_path).exists():
        sys.exit(f"Error: Input audio file '{input_audio_path}' not found")
    if not Path(json_path).exists():
        sys.exit(f"Error: JSON file '{json_path}' not found")

    print(f"Loading JSON data from: {json_path}")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            segments_data = json.load(f)
    except json.JSONDecodeError:
        sys.exit(f"Error: Invalid JSON format in '{json_path}'")
    except Exception as e:
        sys.exit(f"Error reading JSON file: {e}")

    speakers = set(seg['speaker'] for seg in segments_data.get('segments', []))
    if not speakers:
        sys.exit("Error: No speaker segments found in JSON file")

    print(f"Found {len(speakers)} unique speakers: {', '.join(sorted(speakers))}")

    for speaker in sorted(speakers):
        output_path = f"output-audio-{speaker}.wav"
        print(f"\nProcessing speaker: {speaker}")
        create_speaker_audio(input_audio_path, segments_data, speaker, output_path)
        print(f"Created: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Separate audio by speaker using diarization JSON.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Example usage:
  python speaker_splitter.py input.wav diarization.json

JSON format expected:
  {
    "segments": [
      {"speaker": "SPEAKER_0", "start": "00:00:01,234", "end": "00:00:05,678"},
      ...
    ]
  }

Output files will be named output-audio-<speaker_id>.wav in the current directory.
Use audio/speech_features/f0.py to generate the diarization JSON.
        '''
    )
    parser.add_argument('audio_file', help='Input WAV audio file')
    parser.add_argument('json_file', help='Input JSON file with speaker diarization data')
    args = parser.parse_args()

    process_audio(args.audio_file, args.json_file)
    print("\nDone.")


if __name__ == "__main__":
    print("Audio Speaker Separation Tool")
    print("-----------------------------")
    main()
