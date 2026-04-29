# syntax=docker/dockerfile:1.7
FROM python:3.13-slim

# bcrypt and a few transitive deps prefer wheels but fall back to sdist
# builds, which need a C toolchain. Keep the layer slim by removing apt
# caches afterwards.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/

# SQLite file lives on a Compose-managed volume so it survives container
# restarts. The path is also reflected in DATABASE_URL below.
ENV DATABASE_URL=sqlite:////data/pyweb.db

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
