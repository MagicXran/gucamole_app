# AGENTS.md

This file guides Codex, Claude Code, and similar coding agents working in this repository. If a direct user instruction conflicts with anything here, follow the user.

## What This Repo Actually Is

This is not a blank project and not a generic Guacamole demo. It is a FastAPI-based RemoteApp portal in front of Apache Guacamole:

```text
Browser -> Nginx -> FastAPI portal + static frontend
                 -> Guacamole web client
                 -> /internal-drive/ X-Accel download
                      -> guacd -> Windows RDP / RemoteApp host
                      -> MySQL 8.0 (Guacamole DB + portal DB)
```

The core promise is simple: users log into the portal, click an app card, and land in a Guacamole RemoteApp session without dealing with Guacamole login or navigation directly.

## Non-Negotiable Repo Rules

- This workspace is Windows-first. Save edited files with `CRLF`.
- Chinese content is normal here. Pick encoding per file type instead of blindly slapping BOM everywhere.
- Do not add BOM to `Dockerfile`, `*.yml`, `*.yaml`, `.env`, `nginx.conf`, or `*.sql`. Those files are easy to break.
- `config/config.json` is read with `utf-8-sig`, so BOM there is acceptable.
- For Markdown in this repo, use UTF-8 without BOM unless the user explicitly asks otherwise.
- Treat `deploy/backups/` as data, not source code. It currently contains dump artifacts and is untracked.

## Authoritative Startup Paths

Use these paths and commands unless the user explicitly wants something else:

- Python venv: `.\.venv\Scripts\python.exe`
- Install deps if needed: `.\.venv\Scripts\pip.exe install -r requirements.txt`
- Start backend only: `.\.venv\Scripts\python.exe backend\app.py`
- Start Guacamole/MySQL dependencies for local dev:
  - `cd deploy`
  - `docker compose up -d guacd guac-sql guac-web`
- Start the full stack:
  - `cd deploy`
  - `docker compose up -d --build`

Do not assume the root `docker-compose.yml` is current. It is an older, smaller Guacamole-only stack. The real deployment entry is `deploy/docker-compose.yml`.

## Project Map

### Backend

- `backend/app.py`: FastAPI entrypoint, router registration, stale-session cleanup loop, stale-upload cleanup loop, static frontend mount.
- `backend/auth.py`: JWT login, bearer auth, admin guard, in-memory IP rate limit.
- `backend/router.py`: user app list and RemoteApp launch flow.
- `backend/guacamole_crypto.py`: builds encrypted JSON auth payloads for Guacamole.
- `backend/guacamole_service.py`: token creation, validation, redirect URL assembly, session cache.
- `backend/admin_router.py`: app/user/ACL/audit admin APIs.
- `backend/monitor.py`: heartbeat, session-end, monitoring overview, stale-session cleanup.
- `backend/file_router.py`: personal-space quota, list, mkdir, resumable upload, X-Accel download, delete.
- `backend/dataset_router.py`: PoC dataset browser for `data/samples/`.
- `backend/database.py`: sync MySQL connection pool + env override loading.
- `backend/models.py`: Pydantic models shared across routers.

### Frontend

- `frontend/index.html`: user portal.
- `frontend/login.html`: login page.
- `frontend/admin.html`: admin UI.
- `frontend/viewer.html`: VTK.js viewer PoC.
- `frontend/js/app.js`, `frontend/js/login.js`, `frontend/js/admin.js`: plain browser JS, no build step.

### Deploy / Infra

- `deploy/docker-compose.yml`: authoritative full-stack deployment.
- `deploy/nginx/conf.d/portal.conf`: reverse proxy, WebSocket upgrade, upload streaming, X-Accel download.
- `deploy/portal.Dockerfile`: backend image.
- `deploy/guac-web.Dockerfile`: Guacamole web image with branding JAR.
- `branding/`: branding source assets.
- `deploy/branding/portal-branding.jar`: packaged branding extension used in deploy image.

### Data / SQL

- `config/config.json`: main config, env-overridable.
- `database/init.sql`: baseline portal schema and seed data.
- `deploy/initdb/01-portal-init.sql`: deploy-time init SQL copy with monitor table included.
- `database/migrate_*.sql`: manual incremental migrations.

## Stable API Prefixes

Frontend code assumes these paths. Do not rename them casually:

- `/api/auth`
- `/api/remote-apps`
- `/api/admin`
- `/api/monitor`
- `/api/admin/monitor`
- `/api/files`
- `/api/datasets`
- `/guacamole/`
- `/internal-drive/`

## Critical Design Constraints

### 1. Per-user token reuse is deliberate

`backend/router.py` does not build a token for only one app. It packages all connections the user can access into one payload, then `backend/guacamole_service.py` reuses a cached auth token per portal user.

Reason: Guacamole stores auth in localStorage. If every launch creates a fresh token, opening a second tab trashes the first session. Do not "simplify" this away.

### 2. Cache invalidation is part of correctness

When app definitions or ACLs change, cached Guacamole sessions become stale. That is why `backend/admin_router.py` calls `guac_service.invalidate_all_sessions()` after app and ACL mutations. Keep that behavior.

### 3. External Guacamole URL is request-sensitive

Launch flow rebuilds the external Guacamole base URL from proxy headers when possible. This avoids redirecting users to the wrong host. Hardcoding localhost here is a rookie mistake.

### 4. File downloads depend on Nginx, not FastAPI streaming

`backend/file_router.py` returns `X-Accel-Redirect`, and `deploy/nginx/conf.d/portal.conf` serves `/internal-drive/` from `/drive/`. If you break that contract, downloads break.

### 5. Drive isolation is per user

The redirected drive path is `/drive/portal_u{user_id}`. Keep per-user isolation and keep Windows filename restrictions in place.

## Important Tables

Portal-side tables you will touch most often:

- `remote_app`
- `remote_app_acl`
- `portal_user`
- `token_cache`
- `active_session`
- `audit_log`

Seed dev users from init SQL:

- `admin / admin123`
- `test / test123`

## Config Rules

- `backend/database.py` loads `config/config.json` first, then overrides selected values from env vars.
- Do not remove env override behavior just because local defaults work on your machine.
- `GUACAMOLE_INTERNAL_URL` is backend-to-Guacamole.
- `GUACAMOLE_EXTERNAL_URL` is browser-facing fallback, but launch flow may replace it dynamically from the request host.

## Known Gotchas

- Guacamole brute-force protection must stay disabled in Docker deployment: `BAN_ENABLED=false`. Behind the reverse proxy, otherwise one container IP can lock out everyone.
- `disable-gfx: true` is intentional. It works around Guacamole RemoteApp refresh issues.
- Chinese paths in `X-Accel-Redirect` must be URL-encoded segment by segment because HTTP headers are Latin-1 only.
- Hiding the Guacamole side menu requires JavaScript enforcement, not just CSS.
- Build branding JARs with Python `zipfile`, not PowerShell `Compress-Archive`. The latter writes bad archive paths for Guacamole.
- Use `mysql --default-character-set=utf8mb4` for manual SQL imports, or you will produce garbage Chinese text.
- The root `docker-compose.yml` is older and incomplete for this portal. Prefer `deploy/docker-compose.yml`.

## Test Reality

Do not lie to yourself about the current test suite.

- `tests/test_file_router.py` is not a normal pytest module. It executes immediately on import and calls `sys.exit()`.
- Its low-level helper checks run, but its E2E section currently fails with installed `httpx` because sync `httpx.Client` no longer works with the chosen `ASGITransport` usage (`'ASGITransport' object has no attribute 'handle_request'`).
- `python -m pytest tests\test_file_router.py -v` currently ends in failure for that reason.
- If you need trustworthy tests, rewrite this file into real pytest tests before claiming green coverage.

## Practical Agent Guidance

- Prefer editing existing files over adding layers. This repo is intentionally direct.
- Stick to FastAPI + plain JS + mysql-connector unless the user explicitly asks for a stack change.
- If you touch auth, keep JWT payload keys stable: `user_id`, `username`, `display_name`, `is_admin`, `exp`.
- If you touch launch flow, preserve multi-tab behavior.
- If you touch admin app/ACL code, think about session cache invalidation first.
- If you touch file APIs, preserve path traversal defenses and Windows reserved-name checks.
- If you touch frontend pages, remember there is no build pipeline to rescue broken imports or syntax.
- If you touch deploy files, keep them BOM-free.
