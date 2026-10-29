# Deployment

Frontend on Vercel, backend as a Docker container on Render, Postgres managed
elsewhere.

Every step below needs an account you own. Nothing here can be done for you.

> **This document previously recommended Hugging Face Spaces. That no longer
> works on a free account.** Creating a Docker Space returns
> `402 Payment Required`: Static Spaces stay free, but Gradio and Docker
> Spaces now require a PRO subscription, and new free accounts have a
> CPU-basic quota of zero. Render is the replacement because its free tier
> still takes a Dockerfile and needs no card.

## What has and has not been verified

| | Status |
|---|---|
| API proxy carries the session cookie | **Verified** — signed up through the proxy, confirmed `Set-Cookie` returns from the proxy origin with `HttpOnly; SameSite=lax`, and an authenticated request through it succeeds |
| Frontend production build | **Verified** — `npm run build` passes |
| Migrations against SQLite | **Verified** — fresh database built by migration on startup, 313 tests pass |
| Health check reports a lost database | **Verified** — returns 503 and `"database": "unreachable"` rather than claiming to be healthy |
| **PostgreSQL** | **Verified in CI** — the full suite (313 tests) runs against PostgreSQL 17, and migrations upgrade, downgrade to base and upgrade again |
| Docker image builds and serves | **Verified in CI** — the `Backend image builds and serves` job builds the image, applies migrations to PostgreSQL 17, checks `/api/health` answers `"database": "ok"`, analyses the sample report end to end, runs the suite inside the container, and asserts the shipped image carries no test dependencies |
| **Fits a 512MB instance** | **Verified** — in a container capped at 512MB, 250-page and 300-page uploads both returned 201. Both were OOM-killed before the extraction fix |
| Production settings boot | **Verified** — the shipped image starts with `AUTO_MIGRATE=false`, `COOKIE_SECURE=true` and `TRUST_PROXY_HEADERS=true`, and issues `HttpOnly; SameSite=lax; Secure` |
| **A live deployment** | **Not verified — nothing is deployed.** Everything above was measured locally or in CI |
| Cookie withheld over plain HTTP | **Not verified** — `Secure` is set, but showing a client refuse to send it needs a real non-localhost origin. `localhost` is a secure context, so curl and browsers both send it there |
| Render's request timeout | **Not verified** — see Known limitations. A 300-page analysis takes 100s on a fast machine and Render's free CPU is slower |

> **On `com.docker.service`,** for anyone verifying locally on Windows: it is
> set to Manual start and needs an elevation prompt, which looks like the
> reason the engine will not come up. It is not — it governs *Windows*
> containers. The Linux engine runs in WSL2 and does not need it; everything
> above was verified with that service stopped. If the engine really is down,
> open **Docker Desktop** and accept the **"Do you want to allow this app to
> make changes to your device?"** prompt (publisher: *Docker Inc.*). Error
> dialogs it raises are not written to its log files, so their text has to be
> read off the screen.

## The one thing that is easy to get wrong

**The browser must only ever talk to the Vercel origin.** The frontend proxies
`/api/*` to the backend through a Next.js rewrite (`frontend/next.config.ts`).

This is not a convenience. The session cookie is `SameSite=Lax`, and browsers
do not send Lax cookies on cross-site requests. `your-app.vercel.app` and
`your-service.onrender.com` are different registrable domains, so a direct
call from one to the other is cross-site and the cookie would be dropped:
sign-in would appear to succeed and every later request would be anonymous.

It works in development only because `localhost:3000` and `localhost:8000`
differ by port alone, which is still the same site. If you ever change the
frontend to call the backend directly, authentication will break in
production and keep working locally.

## 1. Postgres

Render's filesystem is ephemeral and its own free Postgres expires, so neither
SQLite nor a bundled database is an option for something meant to keep
working. Any managed Postgres with a non-expiring free tier does — Neon and
Supabase both qualify.

Create a database and keep the connection string. It must start with
`postgresql://` (not `postgres://`, which SQLAlchemy rejects).

```
postgresql://user:password@host:5432/dbname
```

Set it in the Render dashboard, not in a file. Nothing in this repository
should ever contain it.

## 2. Backend on Render

There is a blueprint at `render.yaml`, so this is not a click-path to
remember. In Render: **New → Blueprint**, point it at this repository, and it
reads that file — Docker runtime, free plan, `backend/` as the service root,
`/api/health` as the health check, and the non-secret configuration already
set.

Two variables are marked `sync: false` and must be filled in the dashboard:

| Variable | Value |
|---|---|
| `DATABASE_URL` | The `postgresql://` string from step 1 |
| `FRONTEND_ORIGIN` | `https://your-app.vercel.app` — which does not exist until step 3, so set it afterwards |

`SECRET_KEY` is generated by Render (`generateValue: true`) as a
base64-encoded 256-bit value. That clears the minimum the app enforces, and
it is generated once, so redeploys do not invalidate existing sessions.

> **`SECRET_KEY` has a hard floor of 32 bytes.** The app refuses to start
> below it rather than warning and signing anyway, because the key length is
> the whole strength of the session cookie: forging the signature forges the
> session. If you ever set it by hand, generate it with
> `python -c "import secrets; print(secrets.token_urlsafe(48))"`.

`AUTO_MIGRATE` is `true` in the blueprint, which is the opposite of what a
larger deployment should do. It is right here because a free service runs
exactly one instance, so there is no second process to race at boot. **On any
plan that runs more than one instance, set it to `false`** and apply
migrations as a deliberate deploy step:

```bash
cd backend
DATABASE_URL='postgresql://...' ./.venv/Scripts/python.exe -m alembic upgrade head
```

With it off, the app verifies the schema is at head and refuses to start
otherwise, rather than serving against a schema it does not expect.

Check it came up at `https://<your-service>.onrender.com/api/health`. A
`"database": "ok"` means the connection string is right — the endpoint runs
`SELECT 1` rather than assuming.

## 3. Frontend on Vercel

Import the repository and set the root directory to `frontend`.

| Environment variable | Value |
|---|---|
| `BACKEND_ORIGIN` | `https://<your-service>.onrender.com` |

That is the only one. It is read server-side by the rewrite and never reaches
the browser, which is why the backend's address stays private and there is no
`NEXT_PUBLIC_` URL to get wrong per environment.

Deploy, then go back and set `FRONTEND_ORIGIN` on Render to the real Vercel
URL.

## 4. Check the deployment

In this order, because each step depends on the one before:

1. `https://your-app.vercel.app/api/health` — the proxy reaches the backend.
2. Create an account. **Then reload the page.** If you are still signed in,
   the cookie is surviving, which is the whole point of the proxy. If you are
   signed out, the browser is reaching the backend directly somewhere.
3. Upload `samples/sample_report.pdf`. You should get a profile, **two
   findings and five recommendations** — measured on SQLite, on PostgreSQL,
   and on a clean CI runner.
4. Sign out, sign back in, and confirm the analysis is still listed.
5. Upload something long, 100 pages or more, and time it. This is the step
   most likely to disappoint; see Known limitations.

## Local verification with Docker

```bash
docker compose up -d --wait db                  # waits for pg_isready
docker compose run --rm migrate                 # applies migrations
docker compose up -d --build --wait api         # waits for the HEALTHCHECK
curl http://localhost:8000/api/health
docker compose --profile test run --rm tests    # the suite against that Postgres
docker compose down                             # keeps the data volume
```

Three things about that `tests` service, each of which failed only in a
container and not on the host:

- It builds the Dockerfile's **`test` target**. The shipped image has no
  pytest, by design, so the default target cannot run the suite.
- It sets **`COOKIE_SECURE=false`**. The image defaults it to true, which is
  right for a deployment, but the suite drives the app over plain http where a
  Secure cookie is never stored — every authenticated test would run anonymous.
- It points at a **separate database** (`projectrevive_test`). The suite drops
  every table in whatever it is given, so sharing the stack's database means
  running the tests destroys the stack's data.

Use `docker compose down` rather than `down -v` unless you mean to discard the
database: `-v` deletes the `pgdata` volume, and with it the test database that
the init script only creates when the volume is first made.

## Known limitations

- **The service sleeps after 15 minutes idle.** The first request afterwards
  waits roughly a minute for a cold start. For a portfolio demo this mostly
  means warning anyone you send the link to.
- **Long documents are slow, and may be too slow.** A 300-page analysis takes
  about 100 seconds on a fast machine; Render's free CPU is shared and
  slower. Render's free-tier request timeout could not be confirmed — reports
  range from 15 seconds to 100 minutes with no official current figure — so
  **test a long upload on the real instance before relying on it.** If it
  times out, the fix is to move analysis off the request: accept the upload,
  return an id, and have the client poll. The schema already carries a
  `status` column for exactly that.
- **Memory is bounded, not generous.** Extraction peaks around 150MB for a
  300-page document, on a 512MB instance that also holds the application. It
  fits with room to spare, and `backend/tests/test_extraction_memory.py`
  asserts it stays that way — before that fix the same document needed 4GB.
- **Rate limits are per process.** Fine on a single free instance; several
  instances means several independent counters, so the effective limit
  multiplies. The limiter is small enough to swap for a Redis-backed one when
  that matters.
- **No password reset.** Someone who forgets a password needs the account
  deleting from the database by hand.

## Costs

Render's free web service tier and the Vercel hobby tier are both free and
neither needs a card. Postgres on Neon or Supabase has a non-expiring free
tier adequate for this.

The only thing that costs money is the model. With `LLM_PROVIDER=anthropic`
and the default `claude-opus-5-5`, roughly $0.25–0.40 per 20-page report;
`claude-haiku-5-5` is about 25× cheaper. `mock` is free and still produces the
rule-based findings and recommendations, which do not need a model at all.
