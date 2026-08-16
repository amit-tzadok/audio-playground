from pathlib import Path

import soundfile as sf

_model = None


def get_model():
    global _model
    if _model is None:
        from demucs.pretrained import get_model as _get_model
        _model = _get_model("htdemucs")
        _model.cpu().eval()
    return _model


def separate_vocals(path, dest_dir):
    """Isolate vocals from background music/instrumentals via Demucs source
    separation. Unlike noisereduce's spectral gating (built for steady
    broadband noise), this handles tonal/musical background content that
    overlaps speech frequencies and can't be spectrally gated out.
    """
    from demucs.apply import apply_model
    from demucs.audio import AudioFile

    model = get_model()
    wav = AudioFile(str(path)).read(
        streams=0, samplerate=model.samplerate, channels=model.audio_channels
    )
    sources = apply_model(model, wav[None], device="cpu", progress=False)[0]
    vocals = sources[model.sources.index("vocals")].numpy().T

    stem = Path(path).stem
    out_path = Path(dest_dir) / f"{stem}_vocals.wav"
    sf.write(str(out_path), vocals, model.samplerate)
    return str(out_path)
