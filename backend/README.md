---
title: ProjectRevive API
emoji: 🔍
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
short_description: Analyses AI/ML project reports and recommends improvements
---

# ProjectRevive AI — backend

FastAPI service for [ProjectRevive AI](https://github.com/Aariz-a-z/projectrevive-ai).
Full documentation is in the repository root README.

## Why this file has YAML at the top

Hugging Face Spaces reads that frontmatter from the **root of the Space
repository** and refuses to build without it. It also expects the
`Dockerfile` at that root, while in this project the Dockerfile lives in
`backend/`.

Rather than keep a second Dockerfile at the repository root — two files that
would silently drift apart — the Space is given this directory as its root:

```bash
git subtree push --prefix backend hf main
```

So `backend/` *is* the Space, this file is the Space's README, and the
Dockerfile beside it is the one that gets built. Nothing is duplicated.

`app_port: 8000` matches the Dockerfile's own default, so the service listens
where the Space expects without depending on the platform injecting `PORT`.

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
| `SECRET_KEY` | A long random string. There is deliberately no default. |
| `DATABASE_URL` | A `postgresql://` URL. The filesystem here is ephemeral. |
| `AUTO_MIGRATE` | `false` — migrations are a deploy step, not a boot side effect. |
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
