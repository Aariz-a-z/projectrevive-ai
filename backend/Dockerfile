# Backend image.
#
# Host-agnostic on purpose: the port comes from $PORT, which is how Hugging
# Face Spaces, Fly.io, Render and Railway all assign one. Nothing here is tied
# to a particular provider.

FROM python:3.13-slim AS base

# PYTHONDONTWRITEBYTECODE: no .pyc files in a layer that is never reused.
# PYTHONUNBUFFERED: logs appear immediately rather than when a buffer fills,
#   which matters when the only way to debug a boot failure is the log stream.
#
# PIP_NO_CACHE_DIR is deliberately absent. It was set here, which made the
# `--mount=type=cache` below do nothing at all: pip wrote no cache, so there
# was nothing for the mount to keep. The two cancelled out and the file
# implied build caching it did not have. A cache mount lives outside the
# image, so dropping the variable costs no image size.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, in their own layer: application code changes on every
# commit, this file rarely, so the expensive install stays cached.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip setuptools wheel \
    && pip install ".[postgres]"

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini run.py ./

# Run as a non-root user. A container process that does not need to write
# outside /app should not be able to.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Defaults a platform can override. RELOAD is off: a container runs one
# process and the file watcher is pure overhead.
ENV HOST=0.0.0.0 \
    PORT=8000 \
    RELOAD=false \
    AUTO_MIGRATE=false \
    COOKIE_SECURE=true

EXPOSE 8000

# Checks the app, not just the process: a server that booted but cannot reach
# its database still answers the port.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",8000)}/api/health', timeout=4).status==200 else 1)"

CMD ["python", "run.py"]

# ---------------------------------------------------------------------------
# Test image. Adds the development dependencies -- pytest above all -- which
# the shipped image deliberately omits. docker-compose's `tests` service
# builds this target; without it, running the suite in a container fails with
# "No module named pytest", because mounting the test *files* does nothing
# about the test *runner*.
#
# The test files themselves stay mounted rather than copied, so they never
# reach either image.
FROM base AS test
USER root
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install ".[dev,postgres]"
USER appuser

# ---------------------------------------------------------------------------
# The image that ships. Last on purpose: `docker build` with no --target
# builds the final stage, and Hugging Face Spaces builds the Dockerfile
# exactly that way. If the test stage were last, a deploy would quietly ship
# the test dependencies.
FROM base AS runtime
