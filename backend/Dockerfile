# syntax=docker/dockerfile:1.7
# ──────────────────────────────────────────────────────────────────────
#  Relict — API image
#  Multi-stage: builder installs deps into a venv, runtime copies the
#  venv onto a minimal slim base. Runs as non-root, no build tools in
#  the final image.
# ──────────────────────────────────────────────────────────────────────

ARG PYTHON_VERSION=3.11.11

# ─── Stage 1: builder ────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VENV_PATH=/opt/venv

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
      curl \
 && rm -rf /var/lib/apt/lists/*

RUN python -m venv ${VENV_PATH}
ENV PATH="${VENV_PATH}/bin:${PATH}"

WORKDIR /build
COPY pyproject.toml ./
# Install runtime deps only — dev deps live in a separate layer in CI.
RUN pip install --upgrade pip setuptools wheel \
 && pip install .

# ─── Stage 2: runtime ────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_HOME=/app

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpq5 \
      curl \
      tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 relict \
 && useradd  --system --uid 10001 --gid 10001 --home ${APP_HOME} --shell /usr/sbin/nologin relict

COPY --from=builder /opt/venv /opt/venv

WORKDIR ${APP_HOME}
COPY --chown=relict:relict . ${APP_HOME}/

USER relict

EXPOSE 8000

# Healthcheck hits the FastAPI /health route.
HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# tini is PID 1 so SIGTERM reaches uvicorn cleanly.
ENTRYPOINT ["/usr/bin/tini", "--"]

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
