# CLAUDE.md

This file provides guidance to Claude Code when working in this repository. **Read this file before starting any task.**

---

## 1. Project Overview

A community member management website: member profiles, job-hunting/internship write-ups, and event records, for a student/alumni community.

**Tech Stack:**
- **Frontend**: Vue 3 (Composition API with `<script setup>`) + Vue Router + Pinia + Element Plus + md-editor-v3
- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **Database**: PostgreSQL 17 in Docker. Existing SQLite data is imported automatically on first startup; see `docs/postgresql-migration.md`.
- **Auth**: server-side session via Starlette `SessionMiddleware` (signed cookie, `itsdangerous`). **Not JWT** — the only JWT in the codebase signs OnlyOffice conversion requests.
- **Login**: Discord OAuth is the primary and only visible path. Password login survives as a hidden break-glass fallback — see §3.1.
- **Markdown Rendering**: server stores raw Markdown; frontend sanitizes with DOMPurify (`frontend/src/utils/sanitizeHtml.js`).
- **Deployment**: `bash scripts/deploy.sh` builds, stops old writers, and brings up backend + nginx-fronted frontend on host port 8081, OnlyOffice, and PostgreSQL. PostgreSQL persists at `./data/postgresql/`; the original SQLite file and import snapshots are retained.

---

## 2. Development Rules (STRICT)

### 2.1 Language Conventions
- **Code comments**: English only
- **Communication with user**: Traditional Chinese (繁體中文)
- **Git commit messages**: English only
- **UI text / user-facing copy**: Traditional Chinese
- **API error `detail`**: mixed today. User-facing 404/403 messages in routers are Chinese; structural errors are English. Follow whatever the file you're editing already does.

### 2.2 Git Commit Rules
- Follow [Conventional Commits](https://www.conventionalcommits.org/)
- Format: `<type>(<scope>): <subject>`
- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`
- **Small-step commits**: each logical unit = one commit. Never bundle unrelated changes.
- **English-only message body.** Don't quote Chinese UI strings inside commit messages — describe by route, component, field, or behavior instead. Chinese is only acceptable for irreducible proper nouns (e.g. real names in test data).
- **Work on a branch, merge with `--no-ff`.** No direct commits to `main`; the merge commit is the revert unit (`git revert -m 1`). Branch naming follows the existing history: `fix/…`, `feat/…`, `chore/…`, `test/…`.
- **Never `git push`** — the user pushes themselves.
- Never use `--no-verify`, `--amend` on pushed commits, or force-push without explicit user approval.

### 2.3 TODO Workflow (CRITICAL)
1. **Before starting any task**, output a TODO checklist and **wait for user confirmation**.
2. Granularity rule: **one TODO = one commit**.
3. After completing each TODO, report progress and commit immediately.
4. If a TODO needs adjustment mid-task, **ask the user first** before changing course.
5. Track progress in-session with the `TaskCreate` / `TaskUpdate` / `TaskList` tools.

### 2.4 Response Format
- When modifying files, **always state the absolute or repo-relative file path**.
- Do not dump large blocks of unreviewed code — discuss approach first.
- Keep responses concise; the user can read diffs.

### 2.5 Code Style
- **No comments unless the WHY is non-obvious.** Don't narrate what the code does.
- **No premature abstraction.** Three similar lines beats a wrong abstraction. Exception: a rule that gates *access* is worth consolidating earlier than one that doesn't — a drifted copy of a visibility check fails silently (see `app/core/post_visibility.py`).
- **No backwards-compat shims** unless the user asks for them.
- Validate at system boundaries (user input, external APIs); trust internal code.
- Run `ruff format` + `ruff check` on backend changes before committing.

### 2.6 Unit Tests (MANDATORY)
- **Every feature ships with a passing unit test** — backend or frontend, no exceptions.
- **Tests must pass before the next commit.** If a test fails, fix the code (not the test) before moving on.
- **Bundle test with feature** — include the test in the same commit as the feature it covers.
- **DB-touching tests use disposable data only.** Set `TEST_DATABASE_URL` to a dedicated PostgreSQL test database. `backend/tests/conftest.py` migrates one isolated schema per worker for functional tests, truncating data and restarting sequences after each test. Migration, import, and real HTTP tests use fresh per-test schemas. Functional tests use low-cost real bcrypt; tests marked `production_passwords` retain the production cost. SQLite source-format tests use temporary files. Never point tests at deployed databases or `data/pyweb.db`.
- **Backend stack**: `pytest` + FastAPI `TestClient`. Tests live in `backend/tests/`. Full suite takes ~11 min — use per-file `pytest` during work and run the full suite once before handoff.
- **Frontend stack**: `vitest` + `@vue/test-utils` + `happy-dom` / `jsdom`. Tests live next to source as `*.spec.js`.
- **Trivial plumbing exempt**: pure declarative config additions don't need a dedicated test if the next feature's test exercises them end-to-end. Use sparingly.
- **A new test that passes on first run proves nothing.** Break the code it guards, watch it go red, then restore. Especially for permission and visibility tests.
- **Run before committing**: `cd backend && .venv/bin/pytest`; `cd frontend && npm run test`.

### 2.7 Docker Rebuild Before Handoff (MANDATORY)

- After all of a feature's tests pass and the work is ready for the user to verify in a browser, **automatically run `bash scripts/deploy.sh`** from the repo root before declaring the task done. Don't ask first — the user has pre-authorized this.
- Frontend serves on host port **8081**; PostgreSQL persists at `./data/postgresql/`.
- Once per task is enough — don't rebuild between every small commit in a multi-commit feature.
- If the build or container startup fails, surface the error and stop — don't claim the task is complete with a broken image.
- Skip only when the change has no runtime impact (docs-only, CI-only, or test-file-only changes).
- `requirements.txt` uses version ranges, not a lockfile, so a rebuild can move transitive dependencies. If a build pulls a new major, say so.

### 2.8 Wait for User Verification Before Commit (MANDATORY)

- **Tests passing ≠ feature works.** Unit tests catch regressions in known invariants; they don't catch broken UI mounts, missing imports surfacing only at runtime, circular module init, wrong API contract, or dynamic import failures.
- **Default workflow for any change that touches runtime code**:
  1. Apply the edit.
  2. Run the relevant test suite.
  3. Run `docker compose up -d --build` so the change is live on `http://localhost:8081`.
  4. Hand off explicitly noting the change is **uncommitted**.
  5. **Only commit after the user confirms** it behaves correctly in the browser.
- Playwright MCP is available and may be used to do this verification directly instead of asking the user to click — see §7.
- If the user reports it didn't work: fix forward in the working tree and rebuild. Nothing was committed.
- **Allowed to commit immediately without browser verification only when:** docs-only, CI-only, or test-file-only; or a pure refactor with no behavior change AND tests fully cover the affected paths.
- When in doubt, wait for verification.

### 2.9 Skills

Superpowers skills are installed and load on every session. Where one conflicts with this file, **this file wins** — the skills say so themselves.

Specifically: the `brainstorming` skill mandates a spec document under `docs/superpowers/specs/` plus a `writing-plans` handoff. That is too heavy for this project. Use §2.3's TODO checklist instead, and reach for the skill's structure only on genuinely large features where the user asks for a written design.

---

## 3. Current Feature Surface

The product is built. This section records decisions that are **not** obvious from reading the code; everything else is better answered by the code and tests.

### 3.1 Auth & Accounts

- Three roles: `ADMIN`, `MEMBER`, and the legacy shared `VIEWER` (read-only). `VIEWER` cannot be assigned to anyone new — `PATCH /users/{id}/role` accepts only admin/member.
- **Discord OAuth is the primary login.** A member's `discord_id` is their permanent identity key; `discord_username` is mutable and is not a key. Guild membership is checked on login.
- **Break-glass password login**: `admin` (id 1) and `viewer` (id 3) are the only accounts with a password. The login page still ships the password form but hides it behind a hard-coded `showPasswordLogin = ref(false)` — reachable only via dev tools. It is a deliberate fallback for when Discord is down, not a leftover.
- **Login is identified by password alone** (no username field), so the login endpoint scans users and bcrypt-verifies each. That is why a new password is rejected when it collides with another account.
- **`app/core/deps.py:password_account_by_role` is the single source of truth** for "which account is THE admin/viewer". Anything resolving a credential account must go through it — resolving by role alone breaks as soon as a member is promoted to admin.
- The break-glass admin's password doubles as the **shared confirmation credential** for destructive actions, because Discord-linked admins have no password of their own.
- Admin recovery with no working login: `docker compose exec backend python -m app.reset_password admin <new_pw>`.

### 3.2 Members `/members`

- Fields: graduation year, real name, institution, position, join date (required); photo and Markdown resume (optional).
- **Photos are files on disk**, not BLOBs — `Member.photo_path` relative to `settings.uploads_dir`, served by a dedicated endpoint. `photo_updated_at` is the cache-buster.
- Default sort is by join date, ascending, toggleable.
- The public page is a read-only directory. Member lifecycle (role, suspend, delete) lives in the admin roster under 設定, and is driven off the **members** list — which is why the seeded `admin`/`viewer` accounts never appear there.

### 3.3 Jobs `/jobs` and Events `/events`

(The original spec called this "internships"; the route, model and tables are all `job`.)

- Jobs: job year/month, company, kind (`INTERNSHIP` / `FULLTIME`), Markdown experience, optional timeline, optional `subject_member_id`.
- **`is_anonymous` jobs are masked by default everywhere**; admins get click-to-reveal in the detail view.
- Both jobs and events carry `PostStatus`: `PENDING` / `ACCEPTED` / `REJECTED`, with a review queue at `/review`.
- **Visibility rule, one place**: admins see everything; everyone else sees `ACCEPTED` posts plus their own. Events answer "mine?" by `author_user_id`, jobs by `subject_member_id`. Both live in `app/core/post_visibility.py` — do not re-inline this check.
- Comments and likes exist on both. Comments are **plain text**, rendered with `{{ }}` (not `v-html`). Only the author may edit a comment; an admin may delete but not edit.
- Deletes are **hard deletes** with no undo. Destructive admin actions re-confirm with the break-glass admin password.

### 3.4 Markdown

Markdown fields: member resume, job experience, job timeline. Edited with `md-editor-v3` (zh-TW pack in `utils/mdEditorLangZhTW.js`), stored raw, rendered through DOMPurify.

---

## 4. Project Structure

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py          # engine, sessions, pool health checks
│   │   ├── init_db.py           # seeds the admin/viewer password accounts
│   │   ├── reset_password.py    # admin-recovery CLI
│   │   ├── models/              # user, member, job, event, site_setting, …
│   │   ├── schemas/
│   │   ├── routers/             # auth, members, jobs, events, *_comments,
│   │   │                        # *_likes, job_attachments, event_photos,
│   │   │                        # settings, stats, timeline, internal
│   │   └── core/                # deps, security, post_visibility,
│   │                            # discord_*, member_display, audit_log, …
│   ├── tests/                   # pytest, disposable PostgreSQL schemas
│   └── requirements.txt
├── frontend/
│   └── src/                     # views, components, router, stores, api, utils
├── scripts/                     # rclone backup (runs on the server, not dev)
├── data/                        # postgresql + SQLite backups + uploads (bind-mounted)
└── docker-compose.yml
```

---

## 5. Project State

Phases 0–9 (skeleton → CRUD → photos → markdown → permissions → README) are **complete**, as is the Discord OAuth migration and the settings IA restructure. A second contributor merged a comments/likes/avatars batch in July 2026, so `main` moves through more than one pair of hands.

**Deferred — Phase 10: retire password login and the VIEWER role.** Still open, and deliberately so: the user keeps password login as the break-glass fallback. When it is finally tackled, remember to keep at least one rate-limited entry point (password login is currently the only throttled one) and to generalize `password_version` → `session_version`.

---

## 6. Security Notes

- Passwords: bcrypt hashed, never logged. `password_version` is bumped on every change and re-checked per request, which is what evicts other sessions.
- Session secret from `SESSION_SECRET`, never committed. Cookies `httponly` + `samesite=lax`; `secure` in production.
- XSS: Markdown rendered through DOMPurify on the client; comments are plain text.
- File uploads: validate MIME type and size on the backend.
- SQL: SQLAlchemy ORM / parameterized queries — never string-concatenate.
- Login is rate-limited per IP (5/min), keyed on the nginx-set `X-Real-IP` so a forged `X-Forwarded-For` cannot mint fresh buckets.
- Permission checks read the role from the **database** each request, not from the session cookie — a demoted admin loses access on their next request.
- **Admin recovery**: no self-serve forgot-password flow. See §3.1.
- PostgreSQL publishes only `127.0.0.1:5432` for SSH tunnels. Adminer replaces sqlite-web using `8119:8080` because the HTTPS/Basic Auth nginx proxy runs on another host, authenticating with `SQLITE_WEB_PASSWORD` before using the persistent PostgreSQL credential. Credentials are generated once in `data/.postgres-password`; do not log or commit them.

---

## 7. Environment Notes

- **This repo lives on a dev box, not production.** The backup script in `scripts/` runs on the server; its absence here is expected.
- `data/pyweb.db` holds a **copy of real production data** — real names, institutions, resumes, photos. Prefer a snapshot copy over touching the live file, and never paste personal data into output that doesn't need it.
- Playwright MCP is installed (`mcp__playwright__*`) and can drive `http://localhost:8081` directly. To exercise a non-admin path, the break-glass form can be revealed with `document.querySelector('[data-test="password-login"]').style.display = ''`. Admin short-circuits most permission checks, so verifying as an admin proves less than it looks.
- Test fixtures written into the dev DB must be removed afterwards, and the row counts verified back to their starting values.

---

## 8. Workflow Reminder

**Every task starts with a TODO list, ends with small-step commits on a branch.** No exceptions.
