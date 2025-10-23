agents.md — Volaris Contributor Guide (for Codex)

> **Mission:** Act as a diligent pair-programmer. Produce clean, testable, and documented code for the **Volaris** backend (FastAPI + Postgres + Redis + Discord).  
> **Important:** **Never run Git commands; always propose exact commands for me to execute.** Ask for any missing credentials or context before proceeding.

---

## 📖 Documentation Standards

### Phase Documentation
- **One file per phase**: Each phase should have ONE consolidated markdown file: `docs/PHASE_X.md`
- **Sub-phases as sections**: Sub-phases (e.g., 1.1, 1.2) should be sections within that file, not separate files
- **Example**: Phase 1 (with sub-phases 1.1 and 1.2) → `docs/PHASE_1.md`
- **Required sections**:
  - Overview & status
  - Completed tasks (checklist format)
  - Key files created/modified
  - Usage examples (code + cURL)
  - Testing procedures
  - Configuration details
  - Next steps
- **Do NOT create**:
  - Separate files for sub-phases (e.g., `PHASE_1.1.md`, `PHASE_1.2.md`)
  - Separate testing guides
  - Separate completion summaries
  - Multiple checklist files
- **Update after each phase**: Mark as complete in `docs/roadmap.md`

### Code Documentation
- Inline **docstrings** for all public functions/classes (Google-style)
- **Type hints** required on all function signatures
- Module-level docstrings explaining purpose
- Complex logic requires inline comments

---

## 0) How to Work With Me

- **Before writing code**, confirm:
  - Which **Phase/Task** you’re addressing (e.g., *Phase 1.1 – Project Setup*).
  - Any **required secrets**: `DATABASE_URL`, `REDIS_URL`, optional `SENTRY_DSN`.
  - Target environment (local vs. cloud), Python version, package manager.
- **During implementation**, provide a short **PLAN** (numbered steps) → then the code.
- **After implementation**, provide:
  - A **diff summary** of changed/added files.
  - **Manual test steps** (copy-pasteable shell commands and HTTP examples).
  - A **Git section** with exact commands for me to run (see §8).

---

## 1) Coding Standards

- **Language & Runtime**: Python 3.11+ with **type hints** everywhere.
- **Style**: 
  - Format with **Black**.
  - Lint with **Ruff** (flake8 rules + import order). Include `pyproject.toml` config.
  - Docstrings: **Google-style** (or PEP 257) with clear param/return/raise.
- **Project Layout** (do not deviate without discussion):
  ```
  Volaris/
  ├── app/
  │   ├── main.py               # FastAPI app factory + router wiring
  │   ├── config.py             # Pydantic settings: env, secrets, toggles
  │   ├── db/                   # SQLAlchemy models, session, migrations
  │   ├── services/             # API clients (schwab, tiingo, alpaca, finnhub)
  │   ├── core/                 # trade planning, volatility, risk mgmt
  │   ├── alerts/               # Discord webhooks + slash commands
  │   ├── workers/              # APScheduler jobs
  │   └── utils/                # retries, rate limit, error helpers
  ├── tests/
  ├── requirements.txt
  ├── docker-compose.yml
  ├── Dockerfile
  ├── .env.example
  └── README.md
  ```
- **Do**:
  - Keep functions short and single-purpose.
  - Prefer **composition over inheritance**.
  - Fail fast with precise exception messages; avoid silent `except Exception`.
- **Don’t**:
  - Introduce global state (outside DI/config).
  - Hardcode secrets/URLs.
  - Over-abstract on the first pass.

---

## 2) Configuration & Secrets

- Centralize config in **`app/config.py`** using **Pydantic BaseSettings**:
  - `DATABASE_URL`, `REDIS_URL`, optional `SENTRY_DSN`, environment (`ENV=dev|prod`), feature flags.
- Provide/maintain a **`.env.example`** with placeholder values and comments.
- **Never** commit real secrets. If secret-dependent, ask me explicitly and block with actionable placeholders.

---

## 3) Database & Migrations

- ORM: **SQLAlchemy** (async engine). Use **Alembic** for migrations.
- Define models with explicit **indexes** and **constraints**.
- For schema changes:
  - Propose the migration file and **explain upgrade/downgrade**.
  - **Do not** generate destructive changes without calling it out.
- Testing: use an ephemeral test DB and **transaction rollbacks**.

---

## 4) API Clients & Resilience

- For external data providers (Schwab, Tiingo, Alpaca, Databento, Finnhub):
  - Put each client in `app/services/<provider>.py`.
  - Implement **retry with backoff**, **circuit-breaker** or simple cooldown, and **rate-limit awareness**.
  - Clear error taxonomy: provider errors vs. network vs. parsing.
- Add **health checks** and a minimal **fallback strategy** (document assumptions).

---

## 5) FastAPI Design

- Use an **app factory** (`create_app()`), modular routers, and dependency injection.
- Version routes (`/api/v1/...`).
- Pydantic **request/response models** with strict types.
- Include a **/health** endpoint (DB ping, Redis ping).
- Add **CORS** config (default: restrictive; make explicit when loosening).

---

## 6) Background Jobs

- Scheduler: **APScheduler** in `app/workers/`.
- Make jobs **idempotent**, with clear **locks** if needed (Redis keys).
- Log job start/end, duration, and errors.

---

## 7) Logging, Errors, Observability

- Use structured logging (JSON in prod) with contextual fields (request_id, user_id where relevant).
- Map known exceptions to clean **HTTP status codes** and response bodies.
- **Sentry**: keep integration **optional** and behind a flag; no hard dependency during local dev.

---

## 8) Git Protocol (provide concise commit message in chat; I execute commands)

> **Codex must never execute Git commands; only provide the commit message in the chat for me to copy/paste.**

**Format**: Provide a concise commit message following Conventional Commits. Keep to one line when possible, expand to 2-4 lines for large commits:

**Small commit (one line)**:
```
feat(alerts): add Discord webhook integration with rate limiting
```

**Large commit (2-4 lines)**:
```
feat(api): implement Phase 1.2 API integrations

Add 5 provider clients (Schwab OAuth, Tiingo, Alpaca, Databento, Finnhub) with retry logic, error handling, and health checks. Include provider manager with fallback hierarchy and 15+ unit tests.
```

**I will then run**:
```bash
git checkout -b feat/branch-name
git add -A
git commit -m "PASTE_COMMIT_MESSAGE_HERE"
git push -u origin feat/branch-name
gh pr create --title "PR Title" --base main
```

---

## 9) Testing & Quality Gates

- **Unit tests** with **pytest**; minimum coverage goal: **80%** for core logic.
- Provide **arrange–act–assert** examples and **fixture** usage.
- Include **CI** steps (GitHub Actions) for: lint → format check → tests.
- Add **mocks** for external APIs; no live calls in tests.
- **Required pre-flight checks before hand-off** (run locally and report results):
  - `venv/bin/python -m black app tests`
  - `venv/bin/ruff check app/ tests/`
  - `venv/bin/python -m pytest`

---

## 10) Deliverables Checklist (per task)

1. **PLAN** (bulleted steps) + requested **inputs/secrets**.
2. **Code changes** with explanations (files, key functions, decisions).
3. **`.env.example`** updates (if applicable).
4. **Docker** or local run instructions.
5. **Manual test steps** (curl/httpie examples, expected responses).
6. **Lint/format/test results** (copy the commands in §9 and summarize outcomes).
7. **Git commands** to branch, commit, push, and open PR.
8. **Follow-ups**: list of open questions, risks, and next tasks.

---

## 11) Communication Rules

- If anything is ambiguous (e.g., API limits, schema choices, env toggles), **ask first** with concrete options and a recommendation.
- When credentials are needed, **explicitly list** variable names and required scopes.
- Prefer small, incremental PRs (≤ 400 lines diff where possible).

---

## 12) Example: Requesting Credentials

When a secret is required, ask like this:
> I need the following before proceeding:
> - `DATABASE_URL` (Postgres, Neon or Supabase)
> - `REDIS_URL` (Upstash)
> - Optional `SENTRY_DSN` (only if you want error reporting now)
> Add them to `.env` and confirm. I’ll wire `config.py` to read them via Pydantic.

---

## 13) Make Targets (optional but helpful)

If adding a `Makefile`, propose:
```makefile
setup:        ## Create venv and install deps
format:       ## Run black
lint:         ## Run ruff
test:         ## Run pytest -q
run:          ## uvicorn app.main:create_app --factory --reload
```

And provide the Git commands to add/commit it.

---

## 14) Style Examples

- **Function signature**:
```python
async def fetch_iv_metrics(ticker: str, days: int) -> IVSummary:
    '''Return IV/IVR/term-structure for a ticker over N days.'''
```

- **Error handling**:
```python
try:
    data = await client.get_prices(ticker, interval="1m")
except ProviderRateLimitError as e:
    logger.warning("rate_limited", provider="schwab", detail=str(e))
    raise HTTPException(status_code=429, detail="Upstream rate limited")
```

---

## 15) Out of Scope (for now)

- Over-engineering abstractions.
- Adding ML/FinBERT before MVP.
- Building a web UI (Discord commands come first).
- Autotrading/broker order execution.

---

**Remember:**  
- Keep it **clean** (types, docs, tests).  
- Keep it **small** (scoped PRs, clear diffs).  
- Keep it **safe** (no secrets, no destructive migrations without warning).  
- Provide **Git commands**; I will execute them.
