# ProjectRevive AI

Analyses an existing AI/ML project report and recommends evidence-based,
explainable improvements.

> **Status: accounts + analysis dashboard.** Create an account, upload a PDF or
> DOCX, and read a structured project profile with page-cited evidence across a
> tabbed dashboard. The recommendation engine, stack comparison, architecture
> diagrams, roadmap and export are not built yet. See [Roadmap](#roadmap).

## What works today

- **Accounts.** Email and password signup, Argon2id hashing, a JWT session in
  an httpOnly cookie. Analyses are private to the account that created them,
  and another account gets a 404 rather than a 403 so ids cannot be probed.
- **Rate limiting**, in two layers because neither alone is enough. A per-IP
  sliding window stops one host hammering the endpoint; a per-account lockout
  with exponential backoff stops a *distributed* attack that rotates addresses
  and would walk straight through a per-IP limit. Responses carry
  `Retry-After`.
- PDF and DOCX upload, validated by file content rather than extension.
- Text extraction with page numbers preserved.
- A structured `ProjectProfile`: title, domain, problem statement, algorithms,
  tech stack, evaluation metrics, stated limitations.
- **Weakness and gap analysis**, from two sources that are labelled separately
  because they are not equally trustworthy:
  - 14 **deterministic rules** over the structured profile and document text.
    They cannot hallucinate, they are readable in `backend/app/analysis/rules.py`,
    and they run with no API key — so this feature works on the mock provider.
  - The **model**, for judgements the rules cannot make. Its findings go
    through the same citation verification as the profile, and a weakness whose
    quote cannot be found is dropped rather than softened.
- A **hybrid recommendation engine** over a curated, version-controlled
  knowledge base of 22 improvements:
  - **Knowledge linkage** — a rule detected a problem and an entry declares it
    fixes that exact rule, so the recommendation cites a page of your report.
  - **Content similarity** — TF-IDF (or sentence-transformers) against the
    project description, for ideas no rule covers. Capped below anything a
    finding supports, so a lexical coincidence never outranks real evidence.
  - A **transparent score**: a weighted sum whose components and weights are
    shown with every recommendation. Hardware a project does not have excludes
    an entry outright rather than ranking it lower, with the reason stated.
- A tabbed dashboard — Overview, Tech Stack, Evaluation, Findings,
  Recommendations, Evidence — including an evidence view that groups every
  quote by the page it came from.
- **Every finding is labelled** as either stated in the report, with a page
  citation and verbatim quote you can open and check, or inferred, with the
  reasoning shown.
- **Citations are verified against the uploaded document.** A claim citing a
  page that does not exist, or quoting text that is not on the page it names,
  has its citation rejected and is demoted to an inference with a warning.
- Prompt-injection defence: document text is fenced as untrusted data and never
  enters the system prompt; injection-looking content is flagged, not obeyed.
- A deterministic mock provider, so the whole pipeline runs with no API key and
  no spend. Its output is labelled as mock everywhere it appears.
- A real **Anthropic provider** using structured outputs, so the model's
  response is schema-validated before anything downstream sees it. Handles
  policy declines (which arrive as HTTP 200, not an exception), truncated
  output, and every SDK error class as a distinct, actionable message.

## Requirements

- Python 3.12+ (developed on 3.14.3)
- Node.js 20+ (developed on 22.15.0)

## Setup

```bash
# Backend
cd backend
py -3.14 -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"   # Windows
# source .venv/bin/activate && pip install -e ".[dev]"  # macOS/Linux
cp .env.example .env

# Frontend
cd ../frontend
npm install
cp .env.example .env.local
```

## Running

Two processes:

```bash
cd backend && ./.venv/Scripts/python.exe run.py
```

> Use `run.py` rather than calling `uvicorn` directly. Uvicorn enables proxy
> headers by default, which makes it rewrite the client address from
> `X-Forwarded-For` *before* any application code runs — so with no proxy in
> front, a client can spoof that header and hand itself a fresh identity on
> every request, defeating per-IP rate limiting. `run.py` ties uvicorn's
> setting to `TRUST_PROXY_HEADERS`. If you do run uvicorn directly, pass
> `--no-proxy-headers`.

```bash
cd frontend && npm run dev
```

Then open http://localhost:3000. A sample report to try is in
[`samples/sample_report.pdf`](samples/sample_report.pdf).

## Using a real model

The app runs on the mock provider by default — no key, no spend. To use a real
model, put a key in `backend/.env` and verify it before wiring it in:

```bash
cd backend && ./.venv/Scripts/python.exe check_provider.py
```

That makes one small real call (a fraction of a cent), prints the measured
token usage and an estimated cost, and confirms structured output validates.
Then set `LLM_PROVIDER=anthropic` to use it for analyses.

Roughly **$0.25–0.40 per 20-page report** on `claude-opus-5-5`. Setting
`ANALYSIS_MODEL=claude-haiku-5-5` drops that to about $0.015, at the cost of
weaker reasoning about *why* something is a weakness.

> The provider's unit tests use a stubbed SDK client, so they verify the
> request shape and every failure path without spending anything. What they
> cannot verify is that the live API accepts those parameters — an invalid key
> is rejected before parameter validation. `check_provider.py` is what closes
> that gap, and a rejected parameter surfaces as `llm_invalid_output` with the
> API's own explanation.

## Database migrations

The schema is managed by Alembic. `create_all` is no longer used by the
application: it builds whatever the models currently say, which silently
diverges from what migrations would have produced.

On startup the app brings the database to head automatically. After changing
`backend/app/db/models.py`:

```bash
cd backend
./.venv/Scripts/python.exe -m alembic revision --autogenerate -m "what changed"
```

Read the generated file before committing it — autogenerate is a good first
draft, not a finished migration, and it cannot see data changes at all.

```bash
./.venv/Scripts/python.exe -m alembic upgrade head    # apply
./.venv/Scripts/python.exe -m alembic downgrade -1    # undo the last one
./.venv/Scripts/python.exe -m alembic current         # where am I
```

**In production set `AUTO_MIGRATE=false`** and run `alembic upgrade head` as a
deploy step. Automatic migration on startup races when several instances boot
at once. With it off the app verifies the database is at head and refuses to
start otherwise, rather than serving requests against an unexpected schema.

`tests/test_migrations.py` asserts the models and the migrations agree, so
adding a column and forgetting the migration fails the suite instead of
surfacing on a real deployment. Tests build their database with migrations
too, so the migration path is exercised on every run.

## Testing

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest -q
```

```bash
cd frontend && npm run lint && npm run build
```

Tests generate real PDFs and DOCX files with reportlab and python-docx rather
than committing binary fixtures, so the parsers are exercised on genuine
documents. Failure paths covered: empty file, executable renamed `.pdf`,
non-Word zip, truncated PDF, scanned PDF, over page budget, unverifiable
citations, prompt injection, missing API credentials.

## Configuration

All settings come from the environment. See `backend/.env.example`.

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | _generated_ | Signs session tokens. Unset in development, a random key is generated and persisted to `backend/.secret_key` (gitignored). **Must be set explicitly in production** — there is deliberately no hardcoded fallback. |
| `COOKIE_SECURE` | `false` | Set `true` behind HTTPS so the session cookie is never sent in clear. |
| `MIN_PASSWORD_LENGTH` | `10` | Length floor. Composition rules are deliberately not enforced (see `backend/app/auth/policy.py`). |
| `LOGIN_ATTEMPTS_PER_IP` | `20` per 5 min | Per-address cap on sign-in attempts. |
| `SIGNUP_ATTEMPTS_PER_IP` | `5` per hour | Per-address cap on account creation. |
| `UPLOAD_PER_USER` | `20` per hour | Per-account cap on analyses — this is the one that costs money once a model is configured. |
| `LOCKOUT_THRESHOLD` | `5` | Consecutive failed sign-ins before an account locks. |
| `LOCKOUT_MAX_SECONDS` | `600` | Backoff ceiling. Capped at minutes, not hours: a per-account lock can be triggered deliberately by anyone who knows the address, and there is no password reset yet. |
| `TRUST_PROXY_HEADERS` | `false` | Only enable behind a proxy that **overwrites** `X-Forwarded-For`. Requires starting via `run.py` to take effect. |
| `LLM_PROVIDER` | `mock` | `mock` costs nothing and needs no key. `anthropic` performs a real analysis. |
| `ANTHROPIC_API_KEY` | _unset_ | Required only when `LLM_PROVIDER=anthropic`. |
| `ANALYSIS_MODEL` | `claude-opus-5-5` | Roughly $0.25–0.40 per 20-page report. `claude-haiku-5-5` is about 25x cheaper. |
| `EMBEDDER` | `tfidf` | `sentence_transformer` needs the `[semantic]` extra (pulls in PyTorch). |
| `DATABASE_URL` | `sqlite:///./projectrevive.db` | Postgres in production, same code. |
| `MAX_UPLOAD_MB` / `MAX_PAGES` | `20` / `300` | Upload limits. |
| `ENABLE_OCR` | `false` | Scanned PDFs are rejected with a clear message when off. |

## Design decisions that differ from the original spec

| Spec said | Built with | Why |
|---|---|---|
| Next.js (no version) | Next.js 16.4.3 | Next.js 15 reached end of life on 2026-10-21. |
| PyMuPDF | pdfplumber + pypdfium2 | PyMuPDF is AGPL-3.0, which would force this project to be AGPL. pdfplumber is MIT and gives per-word boxes for page citations. |
| Sentence Transformers | Pluggable embedder, TF-IDF default | PyTorch does not fit a free backend host. TF-IDF also serves as the content-only baseline the evaluation plan requires. |
| Server-side PDF export | Markdown + print-ready HTML | Avoids a heavy PDF toolchain; browsers already print to PDF. |

## Measured quality

```bash
cd backend && ./.venv/Scripts/python.exe -m eval.run_eval
```

Ranking quality against a labelled set of 10 cases, hybrid versus two
ablations. **The rules-only baseline currently beats the hybrid at the top of
the ranking** (P@3 0.733 vs 0.700, NDCG@3 0.746 vs 0.736); the hybrid leads on
recall (0.699 vs 0.628). Content similarity trades top-of-list precision for
coverage, and on this set that trade is not yet worth it at K=3.

That result is reported rather than tuned away — with 10 cases there is no
honest train/test split, so fitting the weights to this set and reporting the
improvement would be reporting the fit. Full numbers, caveats and the reason
the P@10 column is misleading are in [`backend/eval/README.md`](backend/eval/README.md).

The labels were written by one person, who also wrote the knowledge base being
scored, so the numbers are biased upward and are not evidence of performance
for anyone else.

## The knowledge base

`backend/app/knowledge/kb/*.yaml` holds the candidate improvements. It is
plain YAML on purpose: you can read an entry, disagree with it, and change it
in a pull request. It is validated on load, so a malformed entry stops the
service starting rather than failing mid-analysis.

**Nothing in it is learned.** There is no interaction data, nothing was
trained, and no recommendation came from user behaviour. Every field was
written by hand, and `impact` in particular is a considered estimate that is
identical for every project matching that entry. The UI says so next to the
score.

Two invariants are enforced by tests rather than convention:

- every entry states at least one **trade-off** — a recommendation with no
  stated downside is advertising, not analysis;
- every detection rule has at least one entry that addresses it, so a rule
  cannot report a problem the system has no answer for.

## Architecture

```
frontend/  Next 16 + Tailwind 4, dark theme. Client-side fetch against the API.
  app/            /, /signup, /login, /dashboard, /analysis/[id]
  components/     ui primitives, icons, claim rendering, auth form
  lib/            typed API client, session provider
backend/
  app/auth/       Argon2 hashing, JWT sessions, password policy
  app/documents/  validation and text extraction (no AI)
  app/llm/        provider interface, mock provider, injection defence
  app/analysis/   extracted text -> validated ProjectProfile
  app/schemas/    the contract; provenance rules enforced here
  app/db/         SQLAlchemy models (profiles, not uploaded files)
  app/api/        FastAPI routes
```

Uploaded files are processed in memory and never written to disk. What is
stored is the structured profile, including the short evidence quotes the UI
must display.

## Roadmap

- [x] **Phase 0** — walking skeleton: upload, extract, profile, render
- [x] **Accounts and dashboard** — signup/login, per-user analyses, dark tabbed
      UI. Pulled forward from the original "future features" list on request.
- [x] **Rate limiting** — per-IP windows, per-account lockout, proxy-header
      hardening
- [ ] **Phase 1** — remaining hardening: Alembic migrations, CI
- [x] **Real Anthropic provider** — structured outputs, refusal and truncation
      handling, prompt caching, server-side fallbacks
- [x] **Phase 2** — weakness and gap analysis, rules plus model
- [x] **Phase 3** — hybrid recommendation engine and knowledge base
- [ ] **Phase 4** — stack comparison, Mermaid architecture, roadmap, export
- [x] **Evaluation harness** — precision@K, NDCG@K, coverage, hybrid against
      two ablations, with the result reported as measured
- [ ] **Phase 5** — accessibility pass, more evaluation cases from a second
      annotator
- [ ] **Phase 6** — deployment

## Licence

MIT (dependency licences were chosen to keep this possible).
