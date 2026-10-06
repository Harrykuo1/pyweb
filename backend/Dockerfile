# syntax=docker/dockerfile:1.7
FROM python:3.13-slim

# ffmpeg transcodes uploaded event videos to H.264/AAC MP4 and pulls their
# poster frame. Phones record HEVC by default, which Chrome and Firefox will
# not play, so serving the original is not an option. The same binary also
# decodes HEIC stills, which iPhones shoot by default and no browser renders
# — one dependency, two problems.
#
# build-essential used to sit here for packages that fell back to sdist
# builds. Every dependency now ships a wheel, so the toolchain was 137 MB of
# compiler that never ran. Office conversion likewise moved to the onlyoffice
# service, so LibreOffice and its fonts are long gone too.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/

# Compose supplies PostgreSQL settings and enables automatic legacy import.
# Uploaded files keep their existing paths across database migrations.
ENV UPLOADS_DIR=/data/uploads

RUN useradd --create-home --uid 1000 pyweb \
    && mkdir -p /data \
    && chown -R pyweb:pyweb /data /app
USER pyweb

EXPOSE 8000

# init_db is idempotent (skips existing rows) so re-running on every
# container start is safe and ensures the seeded accounts exist.
# --proxy-headers + --forwarded-allow-ips=* makes uvicorn honour the
# X-Forwarded-For / X-Real-IP headers the frontend nginx already sends,
# so request.client.host (and therefore the rate-limiter key) reflects
# the real client IP rather than the docker bridge address. Safe to
# trust all sources here because backend's port 8000 is `expose:` only
# (docker-internal), never published to the host or the internet.
CMD ["sh", "-c", "python -m app.init_db && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=*"]
