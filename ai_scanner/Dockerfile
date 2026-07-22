FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/documents data/temp data/metadata

EXPOSE 8000

ENV PORT=8000
ENV PYTHONUNBUFFERED=1

CMD gunicorn --bind=0.0.0.0:$PORT --workers=2 --timeout=120 --access-logfile=- --error-logfile=- src.web_app:app
