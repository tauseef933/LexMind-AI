# LexMind AI backend — FastAPI + LangGraph
# Build:  docker build -t lexmind-backend backend
# Data (SQLite DB, Chroma vectors, uploads) lives in /data — mount a volume there.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Tesseract for OCR of scanned PDFs / images
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY --chown=app:app . .

USER app

# Bake the embedding model (~80 MB) into the image so the first upload is fast
RUN DATABASE_URL=sqlite:////tmp/warmup.db CHROMA_PERSIST_PATH=/tmp/warmup-chroma UPLOADS_DIR=/tmp/warmup-uploads \
    python -c "from rag.embeddings import encode; encode(['warm up'])" \
    && rm -rf /tmp/warmup*

ENV DATABASE_URL=sqlite:////data/lexmind.db \
    CHROMA_PERSIST_PATH=/data/chroma \
    UPLOADS_DIR=/data/uploads \
    PORT=8000

USER root
RUN mkdir -p /data && chown app:app /data
USER app
VOLUME ["/data"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health', timeout=4)"

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
