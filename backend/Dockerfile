# Using Docker (instead of a plain Python buildpack) because Tesseract OCR
# is a system program, not a pip package — most host "native" Python
# environments (Render's included) won't let you apt-get install it, but a
# Docker deploy can install anything the image needs.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render/most hosts inject $PORT; default to 5000 for local `docker run`.
ENV PORT=5000
EXPOSE 5000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --timeout 120 app:app"]
