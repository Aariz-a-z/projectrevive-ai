# Deployment

Frontend on Vercel, backend as a Docker container on Hugging Face Spaces,
Postgres managed elsewhere.

Every step below needs an account you own. Nothing here can be done for you.

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

Create a Space with the **Docker** SDK. Push this repository to it, or point
it at the GitHub repository. The Space builds `backend/Dockerfile`.

Spaces serve on port 7860, which the image already honours through `$PORT`.

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
