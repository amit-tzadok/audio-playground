import os
from pathlib import Path

import yt_dlp


def download_audio_as_wav(url: str, dest_dir: Path) -> Path:
    """Download the given URL's audio track (YouTube or any yt-dlp-supported
    site, including direct audio file links) and convert it to WAV.

    Returns the path to the resulting .wav file.
    """
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
        }],
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        # YouTube's default web client formats have been 403ing without a JS
        # runtime to derive signatures; the android client serves direct URLs.
        "extractor_args": {"youtube": {"player_client": ["android"]}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        downloaded = ydl.prepare_filename(info)
        base, _ = os.path.splitext(downloaded)
        return Path(base + ".wav")
