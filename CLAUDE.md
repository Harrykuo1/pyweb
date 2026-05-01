# CLAUDE.md

This file provides guidance to Claude Code when working in this repository. **Read this file before starting any task.**

---

## 1. Project Overview

A community member management website that records member profiles and internship/job-hunting experiences.

**Tech Stack:**
- **Frontend**: Vue 3 (Composition API with `<script setup>`) + Vue Router + Pinia + Element Plus + md-editor-v3
- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **Database**: SQLite
- **Auth**: server-side session via Starlette `SessionMiddleware` (signed cookie, `itsdangerous`). NOT JWT.
- **Markdown Rendering**: server stores raw Markdown; frontend renders with DOMPurify to prevent XSS
- **Deployment**: `docker compose up --build` brings up backend + nginx-fronted frontend on host port 8081 (container exposes 8080 internally). SQLite persists at `./data/pyweb.db` via bind mount — readable directly with host tools.

---

## 2. Development Rules (STRICT)

### 2.1 Language Conventions
- **Code comments**: English only
- **Communication with user**: Traditional Chinese (繁體中文)
- **Git commit messages**: English only
- **UI text / user-facing copy**: Traditional Chinese

### 2.2 Git Commit Rules
- Follow [Conventional Commits](https://www.conventionalcommits.org/)
- Format: `<type>(<scope>): <subject>`
- Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `build`
- **Small-step commits**: each logical unit = one commit. Never bundle unrelated changes.
- **English-only message body.** Don't quote Chinese UI strings inside commit messages — describe by route, component, field, or behavior instead. Chinese is only acceptable for irreducible proper nouns (e.g. real names in test data).
- Examples:
  - `feat(auth): add JWT token generation in login endpoint`
  - `feat(member): create member list table component`
  - `chore(db): init SQLite schema for users table`
- Never use `--no-verify`, `--amend` on pushed commits, or force-push without explicit user approval.

### 2.3 TODO Workflow (CRITICAL)
1. **Before starting any task**, output a TODO checklist and **wait for user confirmation**.
2. Granularity rule: **one TODO = one commit**.
3. After completing each TODO, report progress and commit immediately.
4. If a TODO needs adjustment mid-task, **ask the user first** before changing course.
5. Use the `TodoWrite` tool to track progress in-session.

### 2.4 Response Format
- When modifying files, **always state the absolute or repo-relative file path**.
- Do not dump large blocks of unreviewed code — discuss approach first.
- Keep responses concise; the user can read diffs.

### 2.5 Code Style
- **No comments unless the WHY is non-obvious.** Don't narrate what the code does.
- **No premature abstraction.** Three similar lines beats a wrong abstraction.
- **No backwards-compat shims** unless the user asks for them.
- Validate at system boundaries (user input, external APIs); trust internal code.

### 2.6 Unit Tests (MANDATORY)
- **Every feature ships with a passing unit test** — backend or frontend, no exceptions.
- **Tests must pass before the next commit.** If a test fails, fix the code (not the test) before moving on.
- **Bundle test with feature** — include the test in the same commit as the feature it covers. Tests are part of "done", not a separate phase.
- **DB-touching tests use mock / in-memory data** — never a persistent database. Backend tests use the in-memory SQLite fixture from `backend/tests/conftest.py`. Never touch `pyweb.db`.
- **Backend stack**: `pytest` + FastAPI `TestClient` (`httpx`-backed). Tests live in `backend/tests/`.
- **Frontend stack**: `vitest` + `@vue/test-utils` + `happy-dom` / `jsdom`. Tests live next to source as `*.spec.js` or under `__tests__/`.
- **Trivial plumbing exempt**: pure declarative config additions (declaring a Pydantic field) don't need a dedicated test if the next feature's test exercises them end-to-end. Use this exemption sparingly — when in doubt, write the test.
- **Run before committing**: `cd backend && pytest`; `cd frontend && npm run test`.

### 2.7 Docker Rebuild Before Handoff (MANDATORY)

- After all of a feature's tests pass and the work is ready for the user to verify in a browser, **automatically run `docker compose up -d --build`** from the repo root before declaring the task done. Don't ask first — the user has pre-authorized this.
- Frontend serves on host port **8081** (container internal 8080); SQLite persists at `./data/pyweb.db`.
- Once per task is enough — don't rebuild between every small commit in a multi-commit feature. Rebuild once at the end before handing back.
- If the build or container startup fails, surface the error and stop — don't claim the task is complete with a broken image.
- Skip only when the change has no runtime impact (docs-only, CI-only, or test-file-only changes).

### 2.8 Wait for User Verification Before Commit (MANDATORY)

- **Tests passing ≠ feature works.** Unit tests catch regressions in known invariants; they don't catch broken UI mounts, missing imports surfacing only at runtime, circular module init, wrong API contract, dynamic import failures, or anything else that only shows up when the page actually loads.
- **Default workflow for any change that touches runtime code** (backend handlers, frontend components, API client, router, store, migrations, etc.):
  1. Apply the edit.
  2. Run the relevant test suite (`cd backend && .venv/bin/pytest` / `cd frontend && npm run test`).
  3. Run `docker compose up -d --build` so the change is live on `http://localhost:8081`.
  4. Hand off to the user explicitly noting the change is **uncommitted** — e.g. "rebuilt and live, verify in browser then I'll commit".
  5. **Only commit after the user confirms** the change actually behaves correctly in the browser.
- If the user reports it didn't work: fix forward in the working tree (or revert local edits) and rebuild. Nothing was committed, so no `git reset` needed.
- **Allowed to commit immediately without browser verification only when:**
  - Change is docs-only, CI-only, or test-file-only (no runtime impact).
  - Change is a pure refactor with no behavior change AND tests fully cover the affected paths.
- When in doubt, wait for verification. One extra round-trip costs nothing; rolling back a published commit is expensive.
- This supersedes the older "only wait for visual / Safari fixes" guidance — the rule now applies to **all** runtime changes.

---

## 3. Feature Requirements

### 3.1 Login Page `/login`
- Two seeded accounts (bcrypt-hashed, written by `init_db.py`):
  - **admin** — full CRUD
  - **viewer** — read-only
- Session stored server-side via Starlette `SessionMiddleware` (signed cookie). Login writes `user_id` and `role` into `request.session`; logout clears it.
- Backend: FastAPI `Depends` reads `request.session` for permission guards (`require_admin`, `require_user`).
- Frontend: cookie sent automatically by browser; axios must use `withCredentials: true`. Vue Router guard + component-level button visibility.
- Show clear error message on login failure.

### 3.2 Members Page `/members`
Table fields:

| Field | Required | Type |
|---|---|---|
| Graduation year | Yes | number |
| Photo | No | BLOB (stored in SQLite) |
| Real name | Yes | string |
| Current job / school | Yes | string |
| Resume | No | Markdown text |
| Join date | Yes (auto or manual) | datetime |

- **Sort by join date** (default: oldest → newest, toggleable).
- Resume edited/previewed via `md-editor-v3`.
- Photo upload: `<input type="file">` → frontend compresses → base64 → backend stores BLOB. Display via dedicated API endpoint returning the image.
- Admin sees Add / Edit / Delete buttons; viewer does not.

### 3.3 Internships Page `/internships`
Table fields:

| Field | Required | Type |
|---|---|---|
| Job-hunting year | Yes | number |
| Company | Yes | string |
| Experience (心得) | Yes | Markdown (interview questions, hands-on tasks, domain Q&A) |
| Real name | No | string (can be anonymous) |
| Timeline (時程表) | No | Markdown |

- List page filterable by year / company.
- Experience and timeline edited/previewed via `md-editor-v3`.

### 3.4 Markdown Editing
- Markdown fields: member resume, internship experience, internship timeline.
- Editor: `md-editor-v3` (edit + preview toggle).
- Storage: raw Markdown string in DB.
- Render: frontend converts → HTML, sanitized with **DOMPurify**.

---

## 4. Project Structure

```
project/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── database.py       # SQLAlchemy engine & session
│   │   ├── models/           # ORM models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── routers/          # auth, members, internships
│   │   ├── core/             # security (JWT, password hash), deps
│   │   └── init_db.py        # seed two accounts
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── views/            # Login, Members, Internships
│   │   ├── components/
│   │   ├── router/
│   │   ├── stores/           # Pinia (auth store)
│   │   ├── api/              # axios instance + API wrappers
│   │   └── utils/
│   └── package.json
└── README.md
```

---

## 5. Development Phases

Commit incrementally through each phase. Always present the phase's TODO list and wait for confirmation before coding.

| Phase | Goal |
|---|---|
| 0 | Initialize project (frontend + backend skeletons, `.gitignore`) |
| 1 | DB schema + seed two accounts |
| 2 | Backend JWT login API + permission dependency |
| 3 | Frontend login page + router guard + Pinia auth store |
| 4 | Member CRUD API + list view + form |
| 5 | Member photo upload / display |
| 6 | Internship CRUD API + frontend pages |
| 7 | Markdown editor integration |
| 8 | Permission polish (button visibility, error handling) |
| 9 | README |

---

## 6. Security Notes

- Passwords: bcrypt hashed, never logged.
- Session secret: read from `SESSION_SECRET` env var, never committed. Cookies marked `httponly` + `samesite=lax`; `secure` flag enabled in production.
- XSS: all user-supplied Markdown rendered through DOMPurify on the client.
- File uploads: validate MIME type and size on the backend; reject non-image content for the photo field.
- SQL: use SQLAlchemy ORM / parameterized queries — never string-concatenate SQL.
- **Admin recovery**: there is no self-serve forgot-password flow. If admin credentials are lost, an operator with host shell access runs `docker compose exec backend python -m app.reset_password admin <new_pw>` — this rotates the hash and bumps `password_version` so any previously-issued cookie is also evicted.

---

## 7. Workflow Reminder

**Every task starts with a TODO list, ends with small-step commits.** No exceptions.
