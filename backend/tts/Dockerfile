FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg build-essential \
    && rm -rf /var/lib/apt/lists/*
# coqui-tts does NOT declare torch/torchaudio as dependencies (expects
# them pre-installed) — install them plainly (not pinned to the CPU-only
# wheel index: that index didn't have a torchaudio build matching the
# latest torch, and the mismatch broke torchcodec's native library
# loading at runtime). This pulls some unused CUDA wheels; accepted
# tradeoff for correctness.
RUN pip install --no-cache-dir torch torchaudio
RUN pip install --no-cache-dir faster-whisper
# coqui-tts is the actively-maintained fork of the abandoned Coqui TTS
# project; the original "TTS" package breaks against current transformers.
# Pin transformers to the 4.x line coqui-tts targets (5.x removes internal
# APIs it depends on), and install the codec extra torch>=2.9 requires for
# audio IO.
RUN pip install --no-cache-dir "coqui-tts[codec]" "transformers>=4.57,<5"
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" python-multipart
ENV COQUI_TOS_AGREED=1
COPY app /app/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8200"]
