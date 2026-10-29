# Deployment

Frontend on Vercel, backend as a Docker container on Hugging Face Spaces,
Postgres managed elsewhere.

Every step below needs an account you own. Nothing here can be done for you.

## What has and has not been verified

| | Status |
|---|---|
| API proxy carries the session cookie | **Verified** — signed up through the proxy, confirmed `Set-Cookie` returns from the proxy origin with `HttpOnly; SameSite=lax`, and an authenticated request through it succeeds |
| Frontend production build | **Verified** — `npm run build` passes |
| Migrations against SQLite | **Verified** — fresh database built by migration on startup, 299 tests pass |
| Health check reports a lost database | **Verified** — returns 503 and `"database": "unreachable"` rather than claiming to be healthy |
| **PostgreSQL** | **Verified in CI** — the full suite (299 tests) runs against PostgreSQL 17, and migrations upgrade, downgrade to base and upgrade again. See the `Backend against PostgreSQL` job. |
| Docker image builds | **Not verified** — the Dockerfile has never been built, see below |

> **Docker could not be started on the development machine.**
> `com.docker.service` is set to Manual start and launching it needs a
> Windows elevation prompt that cannot be accepted from a terminal session.
> This is a permission boundary, not a configuration problem.
>
> To unblock it: open **Docker Desktop** from the Start menu and accept the
> **"Do you want to allow this app to make changes to your device?"** prompt
> (publisher: *Docker Inc.*). Wait until the whale icon stops animating and
> Settings shows **Engine running**. If an error dialog appears instead, its
> text is the thing to act on — it is not written to the log files.
>
> PostgreSQL compatibility no longer depends on this: it is verified in CI
> against a real PostgreSQL service container. Docker is only needed to build
> the image locally, which `docker compose` at the repository root does.

The Postgres half of that is now covered: the `Backend against PostgreSQL`
job runs the whole suite and the migrations against a real PostgreSQL 17, so
the differences that used to surface only in production — stricter type
handling, real transactional DDL, and `JSON` behaving differently from
SQLite's loose storage — are exercised on every push.

The image is the remaining gap. Once Docker starts, this builds it and proves
the container serves:

```bash
docker compose up --build -d                    # db, migrations, then the API
curl http://localhost:8000/api/health
docker compose --profile test run --rm tests    # the suite against that Postgres
docker compose down -v
```

If `/api/health` answers `"database": "ok"`, the image and the migrations are
sound together. Until that runs, treat the Dockerfile as unproven.

## The one thing that is easy to get wrong

**The browser must only ever talk to the Vercel origin.** The frontend proxies
`/api/*` to the backend through a Next.js rewrite (`frontend/next.config.ts`).

This is not a convenience. The session cookie is `SameSite=Lax`, and browsers
do not send Lax cookies on cross-site requests. `your-app.vercel.app` and
`you-projectrevive.hf.space` are different registrable domains, so a direct
call from one to the other is cross-site and the cookie would be dropped:
sign-in would appear to succeed and every later request would be anonymous.

It works in development only because `localhost:3000` and `localhost:8000`
differ by port alone, which is still the same site. If you ever change the
frontend to call the backend directly, authentication will break in
production and keep working locally.

## 1. Postgres

The Hugging Face Spaces filesystem is ephemeral — a rebuild or a sleep cycle
loses it — so SQLite is not an option there. Any managed Postgres works:
Supabase, Neon and Railway all have usable free tiers.

Create a database and keep the connection string. It must start with
`postgresql://` (not `postgres://`, which SQLAlchemy rejects).

```
postgresql://user:password@host:5432/dbname
```

Then apply the schema once, from your machine:

```bash
cd backend
DATABASE_URL='postgresql://...' ./.venv/Scripts/python.exe -m alembic upgrade head
```

Run this on every deploy that includes a migration. It is a deliberate step
rather than something the app does at boot — see `AUTO_MIGRATE` below.

## 2. Backend on Hugging Face Spaces

Create a Space with the **Docker** SDK.

Spaces require the `Dockerfile` **and** a `README.md` with YAML frontmatter at
the *root of the Space repository*, while here the Dockerfile lives in
`backend/`. Rather than keep a second Dockerfile at the repository root — two
files that would drift apart — push the `backend/` subtree as the Space:

```bash
git remote add hf https://huggingface.co/spaces/<your-username>/<space-name>
git subtree push --prefix backend hf main
```

`backend/` then *is* the Space: `backend/README.md` already carries the
required frontmatter, and `backend/Dockerfile` sits beside it. Nothing is
duplicated, and later deploys are the same one command.

`app_port` in that frontmatter is `8000`, matching the Dockerfile's own
default, so the service listens where the Space expects without depending on
the platform injecting `PORT`.

Set these as **Secrets** in Space settings (not Variables — Variables are
visible in the UI):

| Secret | Value |
|---|---|
| `SECRET_KEY` | A long random string. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATABASE_URL` | The `postgresql://` string from step 1 |
| `ANTHROPIC_API_KEY` | Only if you want real analysis; otherwise leave the mock provider |
| `FRONTEND_ORIGIN` | `https://your-app.vercel.app` |

And these as Variables:

| Variable | Value | Why |
|---|---|---|
| `AUTO_MIGRATE` | `false` | Migrating at boot races when instances restart. With it off the app verifies the schema is current and refuses to start otherwise, rather than serving against an unexpected one. |
| `COOKIE_SECURE` | `true` | The session cookie is then never sent over plain HTTP. |
| `LLM_PROVIDER` | `anthropic` or `mock` | `mock` costs nothing and still produces real rule-based findings. |
| `TRUST_PROXY_HEADERS` | `true` | Spaces puts a proxy in front, so the client address arrives in `X-Forwarded-For`. Leave it off and every client looks like the proxy, which makes per-IP rate limiting useless. |

> `TRUST_PROXY_HEADERS=true` is only correct **behind** a proxy that
> overwrites the header. Set it on a directly exposed service and any client
> can spoof its own address and bypass the rate limits entirely.

Check it came up at `https://<your-space>.hf.space/api/health`.

## 3. Frontend on Vercel

Import the repository and set the root directory to `frontend`.

| Environment variable | Value |
|---|---|
| `BACKEND_ORIGIN` | `https://<your-space>.hf.space` |

That is the only one. It is read server-side by the rewrite and never reaches
the browser, which is why the backend's address stays private and there is no
`NEXT_PUBLIC_` URL to get wrong per environment.

Deploy, then go back and set `FRONTEND_ORIGIN` on the Space to the real Vercel
URL.

## 4. Check the deployment

In this order, because each step depends on the one before:

1. `https://your-app.vercel.app/api/health` — the proxy reaches the backend.
2. Create an account. **Then reload the page.** If you are still signed in,
   the cookie is surviving, which is the whole point of the proxy. If you are
   signed out, the browser is reaching the backend directly somewhere.
3. Upload `samples/sample_report.pdf`. You should get a profile, six findings
   and twelve recommendations.
4. Sign out, sign back in, and confirm the analysis is still listed.

## Known limitations

- **The Space sleeps after 48 hours idle.** The first request afterwards waits
  for a cold start of roughly a minute. For a portfolio demo this mostly means
  warning anyone you send the link to.
- **Uploads are processed in memory.** A large file on a small instance is a
  memory spike, which is what `MAX_UPLOAD_MB` bounds.
- **Rate limits are per process.** Several instances means several independent
  counters, so the effective limit multiplies. The limiter is small enough to
  swap for a Redis-backed one when that matters.
- **No password reset.** Someone who forgets a password needs the account
  deleting from the database by hand.

## Costs

Hugging Face Spaces CPU Basic and the Vercel hobby tier are free. Postgres on
Supabase or Neon has a free tier adequate for this.

The only thing that costs money is the model. With `LLM_PROVIDER=anthropic`
and the default `claude-opus-5-5`, roughly $0.25–0.40 per 20-page report;
`claude-haiku-5-5` is about 25× cheaper. `mock` is free and still produces the
rule-based findings and recommendations, which do not need a model at all.
