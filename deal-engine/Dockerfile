FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PYTHONPATH=/srv
WORKDIR /srv

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install -r requirements.txt

# Optional: build with --build-arg WITH_BROWSER=true to bake Chromium in for Playwright rendering
ARG WITH_BROWSER=false
RUN if [ "$WITH_BROWSER" = "true" ]; then playwright install --with-deps chromium; fi

COPY alembic.ini ./
COPY app ./app
COPY config ./config
COPY scripts ./scripts
RUN useradd -m -u 10001 deals && mkdir -p /srv/debug && chown -R deals /srv
USER deals
EXPOSE 8000
CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
