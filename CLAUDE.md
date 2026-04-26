# CLAUDE.md

This file provides guidance to Claude Code when working in this repository. **Read this file before starting any task.**

---

## 1. Project Overview

A community member management website that records member profiles and internship/job-hunting experiences.

**Tech Stack:**
- **Frontend**: Vue 3 (Composition API with `<script setup>`) + Vue Router + Pinia + Element Plus + md-editor-v3
- **Backend**: FastAPI + SQLAlchemy + Pydantic
- **Database**: SQLite
- **Auth**: JWT (access token, stored in frontend `localStorage`)
- **Markdown Rendering**: server stores raw Markdown; frontend renders with DOMPurify to prevent XSS

Docker is **out of scope** — focus on functionality first.

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

---

## 3. Feature Requirements

### 3.1 Login Page `/login`
- Two seeded accounts (bcrypt-hashed, written by `init_db.py`):
  - **admin** — full CRUD
  - **viewer** — read-only
- JWT payload includes a `role` field (`admin` | `viewer`).
- Backend: FastAPI `Depends` for permission guards.
- Frontend: Vue Router guard + component-level button visibility control.
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
- JWT secret: read from environment variable, never committed.
- XSS: all user-supplied Markdown rendered through DOMPurify on the client.
- File uploads: validate MIME type and size on the backend; reject non-image content for the photo field.
- SQL: use SQLAlchemy ORM / parameterized queries — never string-concatenate SQL.

---

## 7. Workflow Reminder

**Every task starts with a TODO list, ends with small-step commits.** No exceptions.
