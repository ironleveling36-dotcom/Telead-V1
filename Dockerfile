# ── Telegram Ad Bot — production image ──────────────────────────────
FROM python:3.11-slim

# Don't write .pyc files; flush logs immediately (important for Railway logs)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DB_PATH=/data/ad_bot.db

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Persist the SQLite DB (and any file session) in a mounted volume.
# On Railway: attach a Volume and mount it at /data.
RUN mkdir -p /data
VOLUME ["/data"]

# Run as a non-root user for safety
RUN useradd --create-home --uid 1000 appuser \
    && chown -R appuser:appuser /app /data
USER appuser

# Headless worker — no exposed port needed.
CMD ["python", "main.py"]