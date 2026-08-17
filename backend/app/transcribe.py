_model = None


def get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        # int8 on CPU keeps this fast enough to not need a GPU; "base" is
        # the speed/accuracy tradeoff point for a tool meant to return
        # quickly rather than a maximum-accuracy transcript.
        _model = WhisperModel("base", device="cpu", compute_type="int8")
    return _model


def transcribe_audio(path):
    model = get_model()
    segments, info = model.transcribe(path, beam_size=1)
    segments = [
        {"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
        for s in segments
    ]
    return {
        "language": info.language,
        "segments": segments,
        "text": " ".join(s["text"] for s in segments).strip(),
    }
