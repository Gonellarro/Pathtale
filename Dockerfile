FROM python:3.11-slim

# Install minimal system dependencies (ffmpeg is required for audio conversion)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install lightweight dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download default Piper Spanish voice model (davefx medium)
RUN mkdir -p /app/models/piper && \
    curl -L -o /app/models/piper/es_ES-davefx-medium.onnx \
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx" && \
    curl -L -o /app/models/piper/es_ES-davefx-medium.onnx.json \
    "https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES/davefx/medium/es_ES-davefx-medium.onnx.json"

# Copy source code and application files
COPY config.py main.py ./
COPY src/ ./src/
COPY web/ ./web/
COPY Libros/ ./Libros/

# Create persistent data directory
RUN mkdir -p /app/data/books /app/data/temp

ENV PIPER_BIN="piper"
ENV PIPER_MODEL="/app/models/piper/es_ES-davefx-medium.onnx"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["python", "main.py", "all"]
