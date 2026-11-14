# syntax=docker/dockerfile:1

# ---- builder ---------------------------------------------------------------
# Dependencies are built into a virtualenv in a separate stage so the runtime
# image carries no compilers or build headers.
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copied alone so the dependency layer is cached across source changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# ---- runtime ---------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Never run as root.
RUN useradd --create-home --uid 10001 neurofab

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY --chown=neurofab:neurofab . .

# Uploaded files land here; it must be a volume in production so documents
# survive a redeploy.
RUN mkdir -p /app/data/documents && chown -R neurofab:neurofab /app/data

USER neurofab
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

# Migrations are NOT run here: with several replicas they would race. Run
# `alembic upgrade head` as a release step before rolling out.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
