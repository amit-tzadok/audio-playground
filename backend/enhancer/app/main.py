import io

import soundfile as sf
import torch
import torchaudio
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response

app = FastAPI(title="playground-audio-enhancer")

_DEVICE = "cpu"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/enhance")
async def enhance_audio(file: UploadFile = File(...), nfe: int = 16):
    from resemble_enhance.enhancer.inference import enhance

    raw = await file.read()
    dwav, sr = torchaudio.load(io.BytesIO(raw))
    num_channels = dwav.shape[0]
    dwav = dwav.mean(dim=0)

    hwav, new_sr = enhance(dwav, sr, _DEVICE, nfe=nfe, solver="midpoint", lambd=0.5, tau=0.5)

    # The model is mono-only; restore the caller's original channel count
    # (duplicated across channels) so the response stays concatenation-
    # compatible with the rest of the (stereo) pipeline.
    hwav_multi = hwav.unsqueeze(0).expand(num_channels, -1).contiguous()

    buf = io.BytesIO()
    sf.write(buf, hwav_multi.numpy().T, new_sr, format="WAV")
    return Response(content=buf.getvalue(), media_type="audio/wav")
