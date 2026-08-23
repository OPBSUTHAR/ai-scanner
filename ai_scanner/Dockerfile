FROM python:3.11-slim-trixie

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libzbar0t64 \
    libgl1 \
    libglib2.0-0t64 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir --timeout 180 --retries 10 \
    torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir --timeout 180 --retries 10 \
    -r requirements.txt

COPY . .

RUN mkdir -p data/documents data/temp data/metadata

EXPOSE 8000

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "gunicorn --bind=0.0.0.0:${PORT:-8000} --workers=2 --timeout=120 --access-logfile=- --error-logfile=- src.web_app:app"]
