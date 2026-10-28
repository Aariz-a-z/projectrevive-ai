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
- PDF and DOCX upload, validated by file content rather than extension.
- Text extraction with page numbers preserved.
- A structured `ProjectProfile`: title, domain, problem statement, algorithms,
  tech stack, evaluation metrics, stated limitations.
- A tabbed dashboard — Overview, Tech Stack, Evaluation, Findings, Evidence —
  including an evidence view that groups every quote by the page it came from.
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
cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend && npm run dev
```

Then open http://localhost:3000. A sample report to try is in
[`samples/sample_report.pdf`](samples/sample_report.pdf).

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
- [ ] **Phase 1** — hardening: rate limits on auth, Alembic migrations, CI
- [ ] **Phase 2** — real Anthropic provider, gap analysis
- [ ] **Phase 3** — hybrid recommendation engine and knowledge base
- [ ] **Phase 4** — stack comparison, Mermaid architecture, roadmap, export
- [ ] **Phase 5** — evaluation harness vs. baselines, accessibility
- [ ] **Phase 6** — deployment

## Licence

MIT (dependency licences were chosen to keep this possible).
