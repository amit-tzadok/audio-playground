FROM python:3.11-slim
WORKDIR /app
# torchcodec (a pyannote-audio dependency) loads FFmpeg's shared libraries at
# runtime to decode audio; python:3.11-slim doesn't ship them.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/
# CPU-only torch/torchaudio/torchcodec first, so pyannote-audio's install
# doesn't pull in the CUDA-enabled wheels from PyPI (torchcodec's default
# PyPI wheel dlopen()s libnvrtc at import time even for CPU-only decoding).
RUN pip install --no-cache-dir torch torchaudio torchcodec --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt
COPY app /app/app
ENV PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
