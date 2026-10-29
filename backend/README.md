# ProjectRevive AI — backend

FastAPI service for [ProjectRevive AI](https://github.com/Aariz-a-z/projectrevive-ai).
Full documentation is in the repository root README; deployment is in
`DEPLOYMENT.md`.

## Where the Dockerfile fits

The Dockerfile lives here rather than at the repository root, because the root
also holds the frontend. Render is pointed at this directory through
`rootDir: backend` in `render.yaml`, so `backend/Dockerfile` is what gets
built and nothing is duplicated.

It is a multi-stage build and **the shipped stage is deliberately last**:
`docker build` with no `--target` builds the final stage, so a test stage left
at the end would ship pytest into production. The `test` target exists for
`docker compose`'s `tests` service, which needs a runner the shipped image
does not carry.

> This file used to begin with Hugging Face Space frontmatter. That approach
> is gone: Docker Spaces now require a PRO subscription, so the backend moved
> to Render. See the note at the top of `DEPLOYMENT.md`.

## Running it

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
python run.py
```

Use `run.py` rather than invoking uvicorn directly: it ties uvicorn's
proxy-header handling to the application's `TRUST_PROXY_HEADERS` setting.
Uvicorn trusts forwarded headers by default, which would let any client spoof
its address and bypass the per-IP rate limits.

## Configuration

See `.env.example`. The settings that matter for a deployment:

| Variable | Deployment value |
|---|---|
| `SECRET_KEY` | A random string of **at least 32 bytes**; the app refuses to start below that. There is deliberately no default. |
| `DATABASE_URL` | A `postgresql://` URL. The deployed filesystem is ephemeral. |
| `AUTO_MIGRATE` | `false` wherever more than one instance can start at once, so concurrent migrations cannot race. `true` is correct on a single-instance free tier. |
| `COOKIE_SECURE` | `true` behind HTTPS. |
| `TRUST_PROXY_HEADERS` | `true` only behind a proxy that overwrites `X-Forwarded-For`. |
| `FRONTEND_ORIGIN` | The frontend's URL. |

## Tests

```bash
pytest -q                                           # SQLite
TEST_DATABASE_URL=postgresql://... pytest -q        # a real PostgreSQL
```

`TEST_DATABASE_URL` is separate from `DATABASE_URL` on purpose: the fixtures
drop every table before running.

One test is POSIX-only and skips on Windows — the memory ceiling in
`tests/test_extraction_memory.py`, which measures peak RSS in a subprocess.
It runs in CI, which is Linux.
