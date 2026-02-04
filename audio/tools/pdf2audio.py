#!/usr/bin/env python3
"""
PDF to Audio Converter
Extracts text from PDF files and converts it to speech audio.
"""

import argparse
import sys
from pathlib import Path
from typing import Optional
import tempfile
import os
import subprocess
import re
import time
import shutil
import platform
import wave
import contextlib
import random

try:
    import PyPDF2
except ImportError:
    print("PyPDF2 not installed. Install with: pip install PyPDF2")
    sys.exit(1)

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

try:
    from pydub import AudioSegment
except Exception:
    AudioSegment = None


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as a string
    """
    text = ""
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            num_pages = len(pdf_reader.pages)
            
            print(f"Processing {num_pages} pages...")
            
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text() or ""
                text += page_text + "\n"
                print(f"Extracted page {page_num + 1}/{num_pages}", flush=True)
                
    except Exception as e:
        print(f"Error reading PDF: {e}")
        sys.exit(1)
        
    return text.strip()

def preprocess_text(text: str, style: str = 'default') -> str:
    """
    Light text cleanup to improve TTS naturalness.
    - Removes hyphenation line breaks
    - Normalizes whitespace and paragraphs
    - Expands a few common abbreviations
    - Replaces URLs/emails with simple spoken forms
    """
    # De-hyphenate wrapped words
    text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

    # Normalize line endings
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # Collapse multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)

    # Replace URLs/emails with short placeholders to avoid robotic spelling
    text = re.sub(r'https?://\S+', ' link ', text)
    text = re.sub(r'\b[\w\.-]+@[\w\.-]+\.\w+\b', ' email address ', text)

    # Expand a few common abbreviations
    replacements = {
        r'\bMr\.': 'Mister',
        r'\bMrs\.': 'Missus',
        r'\bMs\.': 'Mizz',
        r'\bDr\.': 'Doctor',
        r'\bSt\.': 'Saint',
        r'\be\.g\.': 'for example',
        r'\bi\.e\.': 'that is',
        r'\betc\.': 'et cetera',
        r'\bvs\.': 'versus',
    }
    for pattern, repl in replacements.items():
        text = re.sub(pattern, repl, text)

    # Preserve paragraph breaks; collapse single newlines to spaces
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    paragraphs = [re.sub(r'\n', ' ', p) for p in paragraphs]
    text = '\n\n'.join(paragraphs)

    # Slightly increase punctuation for narrative styles
    if style in ('narration', 'story'):
        text = re.sub(r'\s+([,;:])', r'\1', text)
        text = re.sub(r'([,;:])(\S)', r'\1 \2', text)

    return text.strip()

def text_to_speech_pyttsx3(text: str, output_path: str, rate: int = 150, volume: float = 1.0,
                           voice: Optional[str] = None, pause_ms: int = 300, style: str = 'default'):
    """
    Convert text to speech using pyttsx3 (offline).
    
    Args:
        text: Text to convert
        output_path: Path to save the audio file
        rate: Speech rate (words per minute)
        volume: Volume level (0.0 to 1.0)
    """
    if pyttsx3 is None:
        print("pyttsx3 not installed. Install with: pip install pyttsx3")
        sys.exit(1)

    # If using narration/story styles, chunk by sentence and add pauses
    def chunk_sentences(s: str, max_chars: int = 3000):
        sentences = re.split(r'(?<=[.!?])\s+', s)
        chunks = []
        current = []
        current_len = 0
        for sent in sentences:
            if current_len + len(sent) + 1 <= max_chars:
                current.append(sent)
                current_len += len(sent) + 1
            else:
                if current:
                    chunks.append(' '.join(current))
                if len(sent) > max_chars:
                    for i in range(0, len(sent), max_chars):
                        chunks.append(sent[i:i+max_chars])
                    current = []
                    current_len = 0
                else:
                    current = [sent]
                    current_len = len(sent) + 1
        if current:
            chunks.append(' '.join(current))
        return chunks

    print("Converting text to speech (offline)...", flush=True)

    use_chunks = style in ('narration', 'story')
    if not use_chunks:
        # simple single-file save
        engine = pyttsx3.init()
        if voice:
            try:
                engine.setProperty('voice', voice)
            except Exception:
                pass
        engine.setProperty('rate', rate)
        engine.setProperty('volume', volume)
        engine.save_to_file(text, output_path)
        engine.runAndWait()
        print(f"Audio saved to: {output_path}", flush=True)
        return

    chunks = chunk_sentences(text)
    tmpdir = tempfile.mkdtemp(prefix='pyttsx3_chunks_')
    part_files = []
    try:
        rng = random.Random(0)
        for i, ch in enumerate(chunks, start=1):
            part_path = os.path.join(tmpdir, f"part_{i:03d}.wav")
            engine = pyttsx3.init()
            if voice:
                try:
                    engine.setProperty('voice', voice)
                except Exception:
                    pass
            # Add subtle rate variation to reduce robotic cadence
            jitter = rng.randint(-6, 6)
            engine.setProperty('rate', max(80, rate + jitter))
            engine.setProperty('volume', volume)
            engine.save_to_file(ch, part_path)
            engine.runAndWait()
            part_files.append(part_path)

        # Concatenate WAV parts, inserting silence between parts
        if AudioSegment is not None:
            combined = None
            silence = AudioSegment.silent(duration=pause_ms)
            for f in part_files:
                seg = AudioSegment.from_file(f)
                if combined is None:
                    combined = seg
                else:
                    combined += silence + seg
            # Export to desired format
            out_ext = Path(output_path).suffix.lower().lstrip('.')
            if out_ext == 'wav' or out_ext == '':
                combined.export(output_path, format='wav')
            else:
                combined.export(output_path, format=out_ext)
            print(f"Audio saved to: {output_path}", flush=True)
            return

        # Wave-based concatenation fallback (no pydub)
        # Ensure all WAVs have same params
        params = None
        frames = []
        for f in part_files:
            with wave.open(f, 'rb') as w:
                if params is None:
                    params = w.getparams()
                else:
                    if w.getparams().nchannels != params.nchannels or w.getparams().sampwidth != params.sampwidth or w.getparams().framerate != params.framerate:
                        print('Incompatible WAV params; please install pydub/ffmpeg for robust concatenation.', flush=True)
                        _fallback_to_local_tts(text, output_path, rate=rate, volume=volume)
                        return
                frames.append(w.readframes(w.getnframes()))

        silence_frames = b''
        if params:
            n_silence_frames = int(params.framerate * (pause_ms / 1000.0))
            silence_frames = (b'\x00' * params.sampwidth * params.nchannels) * n_silence_frames

        # Write combined WAV
        out_wav = output_path
        if not out_wav.lower().endswith('.wav'):
            out_wav = os.path.splitext(output_path)[0] + '.wav'

        with wave.open(out_wav, 'wb') as out_f:
            out_f.setnchannels(params.nchannels)
            out_f.setsampwidth(params.sampwidth)
            out_f.setframerate(params.framerate)
            for i, fr in enumerate(frames):
                out_f.writeframes(fr)
                if i < len(frames) - 1:
                    out_f.writeframes(silence_frames)

        # If user wanted mp3, try to convert
        if output_path.lower().endswith('.mp3'):
            if AudioSegment is not None:
                AudioSegment.from_file(out_wav).export(output_path, format='mp3')
                print(f"Audio saved to: {output_path}", flush=True)
                return
            else:
                try:
                    subprocess.run(['ffmpeg', '-y', '-i', out_wav, output_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"Audio saved to: {output_path}", flush=True)
                    return
                except Exception:
                    print(f"Wrote WAV to {out_wav}; could not convert to mp3 (ffmpeg/pydub missing).", flush=True)
                    return

        print(f"Audio saved to: {out_wav}", flush=True)
        return
    finally:
        # keep tmpdir for debugging
        pass


def _fallback_to_local_tts(text: str, output_path: str, rate: int = 150, volume: float = 1.0):
    """Attempt to produce audio locally via pyttsx3 or macOS `say`.
    This function will try `pyttsx3` first, then `say`. It will attempt
    basic conversions to the requested output format using pydub or ffmpeg.
    """
    tmpdir = tempfile.mkdtemp(prefix='pdf2audio_fallback_')
    try:
        if pyttsx3 is not None:
            temp_wav = os.path.join(tmpdir, 'fallback.wav')
            try:
                engine = pyttsx3.init()
                engine.setProperty('rate', rate)
                engine.setProperty('volume', volume)
                engine.save_to_file(text, temp_wav)
                engine.runAndWait()
                # Convert if necessary
                if output_path.lower().endswith('.mp3'):
                    if AudioSegment is not None:
                        AudioSegment.from_file(temp_wav).export(output_path, format='mp3')
                        print(f"Audio saved to: {output_path}", flush=True)
                        return True
                    else:
                        try:
                            subprocess.run(['ffmpeg', '-y', '-i', temp_wav, output_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            print(f"Audio saved to: {output_path}", flush=True)
                            return True
                        except Exception:
                            pass
                else:
                    os.replace(temp_wav, output_path)
                    print(f"Audio saved to: {output_path}", flush=True)
                    return True
            except Exception as e:
                print('pyttsx3 fallback failed:', e, flush=True)

        # Try macOS `say` as a final local fallback
        if shutil.which('say'):
            temp_aiff = os.path.join(tmpdir, 'fallback.aiff')
            try:
                cmd = ['say', '-o', temp_aiff, '-v', 'Samantha', text]
                subprocess.run(cmd, check=True)
                if output_path.lower().endswith('.mp3'):
                    if AudioSegment is not None:
                        AudioSegment.from_file(temp_aiff).export(output_path, format='mp3')
                        print(f"Audio saved to: {output_path}", flush=True)
                        return True
                    else:
                        try:
                            subprocess.run(['ffmpeg', '-y', '-i', temp_aiff, output_path], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                            print(f"Audio saved to: {output_path}", flush=True)
                            return True
                        except Exception:
                            pass
                else:
                    os.replace(temp_aiff, output_path)
                    print(f"Audio saved to: {output_path}", flush=True)
                    return True
            except Exception as e:
                print('say fallback failed:', e, flush=True)

        print('No local TTS available (pyttsx3 or say) or conversion failed.', flush=True)
        return False
    finally:
        # Keep tmpdir for debugging; do not delete automatically.
        pass


def text_to_speech_say(text: str, output_path: str, rate: int = 170, voice: Optional[str] = None,
                       pause_ms: int = 350, style: str = 'default'):
    """
    Convert text to speech using macOS `say`.
    Produces AIFF and converts to requested format when possible.
    """
    if not shutil.which('say'):
        print("macOS 'say' not available on this system.", flush=True)
        sys.exit(1)

    # Split by paragraphs for more natural pacing
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    def chunk_paragraphs(parts, max_chars: int = 1200):
        chunks = []
        cur = []
        cur_len = 0
        for p in parts:
            if cur_len + len(p) + 1 <= max_chars:
                cur.append(p)
                cur_len += len(p) + 1
            else:
                if cur:
                    chunks.append('\n\n'.join(cur))
                if len(p) > max_chars:
                    for i in range(0, len(p), max_chars):
                        chunks.append(p[i:i+max_chars])
                    cur = []
                    cur_len = 0
                else:
                    cur = [p]
                    cur_len = len(p) + 1
        if cur:
            chunks.append('\n\n'.join(cur))
        return chunks

    chunks = chunk_paragraphs(paragraphs)

    # Add explicit pauses for narration/story
    if style in ('narration', 'story'):
        slnc = f" [[slnc {int(pause_ms)}]] "
        def add_pause(s: str) -> str:
            return re.sub(r'([.!?])\s+', r'\1' + slnc, s)
        chunks = [add_pause(c) for c in chunks]

    tmpdir = tempfile.mkdtemp(prefix='say_chunks_')
    part_files = []
    try:
        for i, ch in enumerate(chunks, start=1):
            part_path = os.path.join(tmpdir, f"part_{i:03d}.aiff")
            cmd = ['say', '-o', part_path]
            if voice:
                cmd += ['-v', voice]
            else:
                if style in ('narration', 'story'):
                    cmd += ['-v', 'Samantha']
            if rate:
                cmd += ['-r', str(rate)]
            cmd.append(ch)
            subprocess.run(cmd, check=True)
            part_files.append(part_path)

        # If single part, convert or move directly
        if len(part_files) == 1:
            _convert_audio_file(part_files[0], output_path)
            print(f"Audio saved to: {output_path}", flush=True)
            return

        # Concatenate parts
        if AudioSegment is not None:
            combined = None
            silence = AudioSegment.silent(duration=pause_ms)
            for f in part_files:
                seg = AudioSegment.from_file(f)
                if combined is None:
                    combined = seg
                else:
                    combined += silence + seg
            out_format = Path(output_path).suffix.lstrip('.') or 'wav'
            combined.export(output_path, format=out_format)
            print(f"Audio saved to: {output_path}", flush=True)
            return

        # Fallback to ffmpeg concat
        list_file = os.path.join(tmpdir, 'files.txt')
        with open(list_file, 'w') as fh:
            for f in part_files:
                fh.write(f"file '{f}'\n")
        ffmpeg_cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file, output_path]
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(f"Audio saved to: {output_path}", flush=True)
        return
    finally:
        # Keep tmpdir for debugging; do not delete automatically.
        pass


def _convert_audio_file(input_path: str, output_path: str):
    """Convert input audio to requested output format when needed."""
    in_ext = Path(input_path).suffix.lower()
    out_ext = Path(output_path).suffix.lower()
    if not out_ext or out_ext == in_ext:
        os.replace(input_path, output_path)
        return
    if AudioSegment is not None:
        fmt = out_ext.lstrip('.')
        AudioSegment.from_file(input_path).export(output_path, format=fmt)
        return
    try:
        subprocess.run(['ffmpeg', '-y', '-i', input_path, output_path],
                       check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return
    except Exception:
        # As a last resort, keep the original file
        os.replace(input_path, output_path)


def text_to_speech_gtts(text: str, output_path: str, lang: str = 'en', slow: bool = False, rate: int = 150, volume: float = 1.0, pause_ms: int = 300, style: str = 'default'):
    """
    Convert text to speech using Google Text-to-Speech (requires internet).
    
    Args:
        text: Text to convert
        output_path: Path to save the audio file
        lang: Language code (default: 'en')
        slow: Slower speech speed if True
    """
    if gTTS is None:
        print("gTTS not installed. Install with: pip install gTTS")
        sys.exit(1)

    print("Converting text to speech using Google TTS...", flush=True)

    # gTTS has length limits and long payloads can hang; chunk the text.
    def chunk_text(s: str, max_chars: int = 4000):
        # Split on sentence boundaries but keep under max_chars
        sentences = re.split(r'(?<=[.!?])\s+', s)
        chunks = []
        current = []
        current_len = 0
        for sent in sentences:
            if current_len + len(sent) + 1 <= max_chars:
                current.append(sent)
                current_len += len(sent) + 1
            else:
                if current:
                    chunks.append(' '.join(current))
                # If single sentence too long, force-split
                if len(sent) > max_chars:
                    for i in range(0, len(sent), max_chars):
                        chunks.append(sent[i:i+max_chars])
                    current = []
                    current_len = 0
                else:
                    current = [sent]
                    current_len = len(sent) + 1
        if current:
            chunks.append(' '.join(current))
        return chunks

    chunks = chunk_text(text)
    print(f"Text split into {len(chunks)} chunk(s)", flush=True)

    tmpdir = tempfile.mkdtemp(prefix='pdf2audio_')
    chunk_files = []
    max_retries = 3
    backoff_factor = 1.5
    try:
        for i, ch in enumerate(chunks, start=1):
            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.mp3")
            print(f"Rendering chunk {i}/{len(chunks)}...", flush=True)
            # Retry with exponential backoff on failures (rate limits, network)
            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    tts = gTTS(text=ch, lang=lang, slow=slow)
                    tts.save(chunk_path)
                    chunk_files.append(chunk_path)
                    success = True
                    break
                except Exception as e:
                    print(f"gTTS chunk {i} attempt {attempt} failed: {e}", flush=True)
                    if attempt < max_retries:
                        sleep_time = backoff_factor * (2 ** (attempt - 1))
                        print(f"Retrying in {sleep_time:.1f}s...", flush=True)
                        time.sleep(sleep_time)
                    else:
                        print("gTTS failed after retries. Falling back to local TTS.", flush=True)
                        _fallback_to_local_tts(text, output_path, rate=rate, volume=volume)
                        return

        # If only one chunk, move to output
        if len(chunk_files) == 1:
            os.replace(chunk_files[0], output_path)
            print(f"Audio saved to: {output_path}", flush=True)
            return

        # Try pydub concatenation first (allow silence insert for narration/story)
        if AudioSegment is not None:
            print("Concatenating chunks with pydub...", flush=True)
            combined = None
            silence = AudioSegment.silent(duration=pause_ms) if style in ('narration', 'story') else None
            for f in chunk_files:
                seg = AudioSegment.from_file(f, format='mp3')
                if combined is None:
                    combined = seg
                else:
                    if silence is not None:
                        combined += silence + seg
                    else:
                        combined += seg
            out_format = Path(output_path).suffix.lstrip('.') or 'mp3'
            combined.export(output_path, format=out_format)
            print(f"Audio saved to: {output_path}", flush=True)
            return

        # Fallback: try ffmpeg concat
        list_file = os.path.join(tmpdir, 'files.txt')
        with open(list_file, 'w') as fh:
            for f in chunk_files:
                fh.write(f"file '{f}'\n")

        ffmpeg_cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', list_file, '-c', 'copy', output_path]
        print('Attempting ffmpeg concat...', flush=True)
        try:
            subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"Audio saved to: {output_path}", flush=True)
            return
        except Exception as e:
            print('ffmpeg concat failed or not available:', e, flush=True)
            print('Chunks are available in:', tmpdir, flush=True)
            print(f"Please install pydub (`pip install pydub`) and ffmpeg for automatic concatenation.", flush=True)

    finally:
        # Do not auto-delete tmpdir so user can recover chunks if concat failed.
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF text to audio file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf2audio.py document.pdf
  python pdf2audio.py document.pdf -o output.mp3
  python pdf2audio.py document.pdf --engine gtts
  python pdf2audio.py document.pdf --rate 180 --volume 0.8
        """
    )
    
    parser.add_argument('pdf_file', type=str, help='Path to the PDF file')
    parser.add_argument('-o', '--output', type=str, help='Output audio file path')
    parser.add_argument('--engine', type=str, choices=['pyttsx3', 'gtts', 'say'], 
                        default='gtts' if gTTS else ('say' if platform.system() == 'Darwin' else 'pyttsx3'),
                        help='TTS engine to use (default: gtts if available)')
    parser.add_argument('--rate', type=int, default=150,
                        help='Speech rate for pyttsx3 (default: 150)')
    parser.add_argument('--volume', type=float, default=1.0,
                        help='Volume level for pyttsx3, 0.0-1.0 (default: 1.0)')
    parser.add_argument('--lang', type=str, default='en',
                        help='Language code for gTTS (default: en)')
    parser.add_argument('--slow', action='store_true',
                        help='Use slower speech speed for gTTS')
    parser.add_argument('--style', type=str, choices=['default', 'narration', 'story'], default='narration',
                        help='Reading style: narration/story add pauses and slower pacing (default: narration)')
    parser.add_argument('--pause-ms', type=int, default=300,
                        help='Pause (ms) to insert between sentences or chunks when using narration/story')
    parser.add_argument('--voice', type=str, default=None,
                        help='Voice name to use with pyttsx3 (if available)')
    
    args = parser.parse_args()
    
    # Check if PDF file exists
    if not Path(args.pdf_file).exists():
        print(f"Error: PDF file not found: {args.pdf_file}")
        sys.exit(1)
    
    # Determine output file path
    if args.output:
        output_path = args.output
    else:
        pdf_stem = Path(args.pdf_file).stem
        extension = '.mp3' if args.engine == 'gtts' else '.wav'
        output_path = f"{pdf_stem}_audio{extension}"
    
    # Extract text from PDF
    print(f"Extracting text from: {args.pdf_file}")
    text = extract_text_from_pdf(args.pdf_file)
    text = preprocess_text(text, style=args.style)
    
    if not text:
        print("Warning: No text extracted from PDF")
        sys.exit(1)
        
    print(f"Extracted {len(text)} characters")
    
    # Convert to speech
    if args.style in ('narration', 'story'):
        # make narration/story a bit slower by default
        if args.style == 'narration' and args.rate == 150:
            args.rate = 140
        if args.style == 'story' and args.rate == 150:
            args.rate = 130
        if args.style == 'story' and args.pause_ms == 300:
            args.pause_ms = 450

    if args.engine == 'pyttsx3':
        text_to_speech_pyttsx3(text, output_path, args.rate, args.volume, voice=args.voice,
                               pause_ms=args.pause_ms, style=args.style)
    elif args.engine == 'say':
        text_to_speech_say(text, output_path, args.rate, voice=args.voice,
                           pause_ms=args.pause_ms, style=args.style)
    elif args.engine == 'gtts':
        text_to_speech_gtts(text, output_path, args.lang, args.slow, rate=args.rate, volume=args.volume,
                            pause_ms=args.pause_ms, style=args.style)
    else:
        print(f"Unknown engine: {args.engine}")
        sys.exit(1)
    
    print("✓ Conversion complete!")


if __name__ == "__main__":
    main()
