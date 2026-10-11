# College Scheduling Management System

A full-stack web application for **college timetable scheduling and course registration**, modelled on the
slot-based (FFCS-style) structure used by large Indian universities. Its core job is **scheduling optimisation**: placing
every course offering into weekly slots so that no teacher, student group or room is ever double-booked — and showing
everyone, before registration starts, exactly which subjects sit in which slot.

Management (Admin), Faculty and Students each get their own login and dashboard. Registration itself stays simple:
students pick credits and subjects, choose a faculty option, and faculty accept requests in the order they arrive.

![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-4169E1?logo=postgresql&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-4-06B6D4?logo=tailwindcss&logoColor=white)

## Try it

**Live demo — nothing to install:** <https://anvita-arun-scheduling-frontend.onrender.com>

Sign in with any of the [sample accounts](#sample-data--credentials) (for example admin `admin@college.edu` /
`Admin@123`). The demo runs on a free hosting tier, so the **first load after a quiet period can take about a minute**
while the server wakes up. It is a shared demo: anyone can use these accounts, so the data may be changed by other
visitors, and it may be reset at any time.

**Run it yourself with one command** — no Python, Node.js or PostgreSQL installation required, just
[Docker Desktop](https://www.docker.com/products/docker-desktop/) (and Git):

```bash
git clone https://github.com/Anvita-13/scheduling-management-system.git
cd scheduling-management-system
docker compose up --build
```

Open <http://localhost:3000> and sign in with the same sample accounts. The first build takes a few minutes. See
[Getting Started](#getting-started) for details and [DEPLOY.md](DEPLOY.md) to host your own copy.

## Table of Contents

- [Try it](#try-it)
- [Core Idea: Slots](#core-idea-slots)
- [Features](#features)
- [Phase 1 Algorithms](#phase-1-algorithms)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Sample Data & Credentials](#sample-data--credentials)
- [API Overview](#api-overview)
- [Testing](#testing)
- [Documentation](#documentation)
- [Security](#security)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Core Idea: Slots

- A **slot** is a named weekly package of meeting periods, e.g. theory `A1+TA1` (Mon 08:00, Wed 09:00, Fri 10:00) or lab
  `L1+L2` (Mon 08:00–09:40). Slots **clash when their periods overlap in time** — a theory slot can clash with a lab slot.
- An **offering** is one faculty member teaching one subject, as a complete unit with **its own** theory slot and, for
  theory+lab courses, **its own** lab slot. A student who picks that faculty gets exactly that pair — no mixing a theory
  of one faculty with the lab of another. Two faculty may share a lab slot (they then use different lab rooms).
- Different subjects in the same slot are **alternatives** (a student can hold only one). The *Slot Chart* (admin) and
  *Slot View* (student) show this directly.
- Courses are theory-only or theory+lab. Students pick freely from all available subjects, up to their chosen credit
  limit. Only a couple of courses come with several faculty options; most have a single faculty.
- **Slots are fixed before registration.** The admin can place offerings by hand (busy teachers are simply missing from
  the faculty drop-down) or let the optimiser place them. Students can't hold overlapping offerings: such requests are
  refused, with a clash warning showing exactly which theory/lab sessions overlap and when.

## Features

**Scheduling (the main purpose)**
- Standard VIT-style slot chart (36 theory + 30 lab packages) loadable in one click
- **Auto-assign slots**: a backtracking optimiser places every unplaced offering — no teacher in overlapping slots, theory clear of its own lab, within the room limit — and spreads subjects so students can combine them. Hand-placed offerings stay put
- **Eligible-faculty filter** when assigning a teacher: anyone already teaching at an overlapping time is left out (with a "why not listed" note)
- **Automatic rooms**: only room type and size are entered; which class gets which room is derived (same time ⇒ different rooms, labs ⇒ lab rooms)
- **Clash report** with part-level detail (shows exactly which theory/lab session clashes and when), **slot chart**, weekly timetable for admin / faculty / student, all derived from the slots

**Admin / Management** — subjects and offerings, slots and rooms, registration period and credit range, seats and class closing, unmet demand and waitlist, alerts when no faculty is available, faculty reopen requests with approval/denial, account settings

**Faculty** — own classes with slots and rooms, pending requests in strict arrival order, accept/decline from the front, accepted students, request to reopen a closed class, close a class, account settings, own timetable

**Student** — credit load, pick any subjects within credit limit with auto-queue for single-faculty options, faculty options with detailed clash warnings, join requests with queue position, *Slot View*, notifications, account settings, own timetable

**Platform** — JWT authentication with role-based access enforced in the backend, in-app notifications, race-safe seat allocation (row locking + database constraints)

## Phase 1 Algorithms

| # | Algorithm | Where it is used | Complexity |
|---|---|---|---|
| 1 | **FIFO Queue** | Each class's pending join requests (first come, first served) | enqueue / dequeue **O(1)** |
| 2 | **Greedy Faculty Allocation** | Suggesting another faculty option when a class is full (never proposes one that clashes) | **O(F)** for F candidate faculties |
| 3 | **Backtracking Graph Coloring** | **Slot optimisation**: class parts = vertices, "must not overlap" = edges, slot packages = colours (clash = time overlap) | worst case **O(k^V)** (NP-complete), pruned in practice |
| 4 | **Edmonds-Karp Maximum Flow** | Admin capacity planning: how many waiting students could be seated, and where the bottlenecks are | **O(V·E²)** |

Each algorithm is a pure-Python module in [`backend/app/algorithms/`](backend/app/algorithms) with no web or database
imports, so it can be unit-tested on its own. A plain-language explanation of what each does and why it was chosen is in
[WORKFLOW.md](WORKFLOW.md).

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS 4, React Router — built and served by nginx in the container |
| Backend | Python, FastAPI, Pydantic v2 |
| Database | PostgreSQL, SQLAlchemy 2 (ORM), Alembic (migrations) |
| Auth | JWT (PyJWT), bcrypt password hashing |
| Testing | pytest, FastAPI TestClient |
| Containers | Docker Compose (3 services: `db`, `backend`, `frontend`), each with its own Dockerfile and health check |

## Architecture

```
React (Vite + Tailwind) ──REST/JSON──▶ FastAPI routers ──▶ Services ──▶ SQLAlchemy ──▶ PostgreSQL
 pages · role guards                    HTTP + JWT/RBAC     business     models,         constraints,
 centralised API client                                     rules, txns  row locks       partial indexes
                                                               │
                                                               ▼
                                                  Algorithms (pure Python)
                                  fifo_queue · greedy_faculty_allocation ·
                                  backtracking_graph_coloring · edmonds_karp
```

The backend is the single source of truth for slots, capacity, request order, permissions and algorithm results; the
React app only presents them.

At runtime the three pieces are containers on one Docker network: the browser talks only to `frontend` (nginx), which
serves the built React app and proxies every `/api/...` call to `backend`; `backend` is the only service that talks to
`db`. Nothing needs installing on the host beyond Docker itself.

## Project Structure

```
scheduling-management-system/
├── docker-compose.yml         # the three services: db, backend, frontend
├── .env.example               # Docker Compose configuration (copy to .env)
├── render.yaml                # Render Blueprint: database + backend + static frontend (see DEPLOY.md)
├── backend/
│   ├── Dockerfile
│   ├── docker-entrypoint.sh   # waits for the database, runs migrations, loads sample data, then starts uvicorn
│   ├── app/
│   │   ├── main.py            # FastAPI application
│   │   ├── core/              # config, security (JWT/bcrypt), RBAC dependencies, errors
│   │   ├── db/                # engine/session, wait_for_db, seed script (VIT-style sample data)
│   │   ├── models/            # SQLAlchemy models (users, academic, scheduling, registration, system)
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── routers/           # auth, admin, faculty, student, timetable, notifications
│   │   ├── services/          # slot_, room_, timetable_, registration_, faculty_, capacity_, admin_, allocation_, insights_, notification_service
│   │   └── algorithms/        # the four Phase 1 algorithms
│   ├── alembic/               # database migrations
│   ├── db/schema.sql          # plain-SQL schema (for direct database setup, e.g. in DBeaver)
│   ├── db/sample_college_data.sql   # the sample dataset as plain INSERTs
│   ├── tests/                 # unit, scheduling, workflow, security and concurrency tests
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile             # builds the app, then serves it with nginx
│   ├── nginx.conf             # serves the static build and proxies /api to the backend container
│   └── src/                   # api/ auth/ components/ hooks/ layouts/ pages/ services/ utils/ styles/
├── README.md                  # this file
├── SETUP.md                   # build, run and database instructions
├── WORKFLOW.md                # how the system works, explained for everyone
└── DEMO.md                    # guided demo: every screen and algorithm, in presentation order
```

## Getting Started

**Prerequisite:** [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows, macOS or Linux). Nothing
else — no Python, Node.js or PostgreSQL install. DBeaver is optional, for browsing the containerised database.

```bash
git clone https://github.com/Anvita-13/scheduling-management-system.git
cd scheduling-management-system
cp .env.example .env            # Windows PowerShell: copy .env.example .env — optional, sensible defaults are built in
docker compose up --build
```

The first run builds the images, starts PostgreSQL, applies the database migrations and loads the sample dataset
automatically — watch for `Starting the application server...` in the `backend` logs. Then open:

- **http://localhost:3000** — the application
- **http://localhost:8000/docs** — the interactive API reference

Stop everything with `Ctrl+C`, or `docker compose down` from another terminal. Your data persists in a Docker volume
across restarts (`docker compose up` again picks up where you left off); `docker compose down -v` deletes it.
Every setting — ports, the sample-data switch, production secrets — lives in `.env`; see
**[SETUP.md](SETUP.md)** for the full guide (configuration, rebuilding after a code change, running tests inside the
containers, direct database access, troubleshooting).

## Sample Data & Credentials

The sample dataset is loaded automatically the first time the app starts (the seed script, `python -m app.db.seed`). It is a semester modelled on VIT's FFCS structure (see [SETUP.md §6.1](SETUP.md#61-the-vit-style-sample-dataset)):
29 VIT-style courses (BMAT101L Calculus, BCSE202L Data Structures and Algorithms, …), 122 students in one pool (all
can pick from all courses), exactly two courses with faculty options (Calculus: 4 faculty, theory only; DSA: 5 faculty, theory+lab
with a lab slot per faculty), 26 faculty with fake names, 66 slots, 18 rooms — the two option courses are placed by hand and
the optimiser places the other 27 offerings with zero clashes, plus a simulated registration (full classes, waiting queues,
unmet demand). Faculty names are fake; everything else follows VIT's structure. Students freely select subjects up to
their chosen credit load; single-faculty subjects auto-queue the student when picked.

Demo accounts, public by design — they work on the live demo and in your local Docker copy (do not reuse these passwords
anywhere real, and set `SEED_ADMIN_PASSWORD` if you host your own copy for other people):

| Role | Email | Password |
|---|---|---|
| Admin | `admin@college.edu` | `Admin@123` |
| Faculty | `first.last@college.edu`, e.g. `rajesh.patel@college.edu` (DSA), `harish.mehta@college.edu` (Calculus) | `Faculty@123` |
| Student | `stu1@college.edu` … `stu122@college.edu` (single pool) | `Student@123` |

## API Overview

All routes are prefixed with `/api` and need a `Authorization: Bearer <token>` header, except login.

| Area | Key endpoints |
|---|---|
| Auth | `POST /auth/login`, `GET /auth/me`, `PATCH /auth/me` (profile), `POST /auth/change-password` |
| Admin — scheduling | `GET /admin/slots`, `POST /admin/slots/load-standard`, `GET /admin/eligible-faculty`, `POST /admin/offerings`, `PATCH /admin/offerings/{id}/slots`, `GET /admin/slot-chart`, `GET /admin/scheduling/clashes`, `POST /admin/scheduling/auto-assign`, `POST /admin/scheduling/assign-rooms`, `POST /admin/scheduling/clear`, `/admin/rooms` |
| Admin — other | `/admin/subjects`, `/admin/classes` (+ capacity, close, reopen), `POST /admin/classes/{id}/decline-reopen`, `/admin/registration`, `/admin/demand`, `/admin/faculty`, `/admin/students` |
| Faculty | `/faculty/dashboard`, `/faculty/classes`, `/faculty/classes/{id}`, `POST …/accept-next`, `…/reject-next`, `…/close`, `POST …/request-reopen` |
| Student | `/student/profile`, `PUT /student/credits`, `/student/subjects` (pick subjects freely), `/student/subjects/{id}/classes`, `/student/offerings` (slot view), `/student/requests` |
| Timetable | `GET /timetable` (role-specific weekly view) |
| Notifications | `/notifications`, `/notifications/unread-count`, `POST /notifications/{id}/read` |

Errors are returned as `{"detail": "...", "code": "MACHINE_READABLE_CODE"}` (for example `SLOT_CLASH`, `FACULTY_CLASH`,
`SLOT_LOCKED`, `CLASS_FULL`). The full, interactive reference is served at `/docs` while the backend is running.

## Testing

```bash
docker compose up -d db backend     # the backend container has pytest installed already
docker compose exec backend pytest -q
```

The suite runs on in-memory SQLite by default. To also run the concurrency tests against PostgreSQL, set
`TEST_DATABASE_URL` to a scratch database inside the container (see [SETUP.md](SETUP.md#9-running-the-tests)); the
tests are baked into the backend image, so rebuild it (`docker compose up -d --build backend`) after editing them. It covers
every algorithm, the slot rules (overlap by time, faculty clashes, theory+lab pairing, rooms, locking), student clash
blocking, authentication and role authorisation, the registration/acceptance/capacity workflows, race conditions, the
sample dataset, and the complete admin → student → faculty → timetable flow.

## Documentation

| Document | Contents |
|---|---|
| [SETUP.md](SETUP.md) | Build, run and implementation instructions — for the application and for working directly with the database (DBeaver/psql) |
| [DEPLOY.md](DEPLOY.md) | Putting it on the internet with Render: what the free tier does and doesn't give you, the exact steps, and troubleshooting |
| [WORKFLOW.md](WORKFLOW.md) | A full, plain-language walkthrough of how the system works and what each algorithm does, why it was chosen and how it works |
| [DEMO.md](DEMO.md) | A presentation script: Admin → Faculty → Student, every tab and function, with the algorithm behind each and how it works, plus a 10-minute demo plan |

## Security

- Passwords are hashed with bcrypt; plaintext passwords are never stored.
- JWT access tokens are validated server-side; the user's role is re-read from the database on every request.
- Every protected route enforces its role in the backend; the frontend route guards only hide screens.
- All input is validated with Pydantic. Secrets and database credentials come from environment variables (set in the
  root `.env`, read by Docker Compose) — never commit `.env`; the default `SECRET_KEY`/`POSTGRES_PASSWORD` baked into
  `docker-compose.yml` are for local use only and **must** be overridden before exposing this beyond your own machine.
  The sample admin password (`Admin@123`) is public — set `SEED_ADMIN_PASSWORD` for any deployment other people can
  reach (the Render Blueprint generates a random one for you).
- Seat counts are protected by row-level locks, atomic conditional updates and a database `CHECK` constraint.

## Known Limitations

- An offering has one theory slot and (for theory+lab courses) one lab slot; per-faculty availability windows and workload caps are not modelled.
- Slots are fixed *before* registration. An offering that already has students (or waiting requests) is locked and cannot be moved.
- Clash detection is real-time (when a student requests): the optimiser does not predict future clashes, so it spreads all subjects equally; students' actual clashes are prevented at request time instead.
- When registration is closed no new requests are accepted; the admin reopens it for students who still need a seat, or faculty can request the admin to reopen a specific closed class.
- No CSV/bulk import yet (subjects, faculty and students are created one at a time or by the seed script), and no self-service sign-up, password reset, refresh tokens or login rate limiting.

## Roadmap

Phase 1 (this release) contains the four algorithms above. **Phase 2 is reserved for future work** and is intentionally
not implemented: Hopcroft-Karp matching, Knapsack-based optimisation, Priority-Queue recommendation, a DFS conflict
module and Greedy seat expansion. Bulk CSV import is another planned convenience.

## Contributing

1. Fork the repository and create a feature branch.
2. `docker compose up --build` to run the app; `docker compose exec backend pytest -q` must pass.
3. Keep algorithm code free of web/database imports so it stays independently testable.
4. Update README.md / SETUP.md / WORKFLOW.md / DEMO.md when behaviour or commands change.
5. Open a pull request describing the change.

## License

Released under the MIT License — see [LICENSE](LICENSE).
