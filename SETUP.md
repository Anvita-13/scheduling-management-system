# Setup, Build & Run Guide

Everything needed to install, run, build, test and extend the College Scheduling Management System — through
**Docker Compose** (the only supported way to run it) and by working **directly with the PostgreSQL database** it creates.

> New to the project? Read [README.md](README.md) first for the overview, and [WORKFLOW.md](WORKFLOW.md) for how the
> system behaves. Commands are given for **macOS/Linux (bash)** and **Windows (PowerShell)** where they differ.

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Environment variables](#2-environment-variables)
3. [Quick start — Docker Compose](#3-quick-start--docker-compose)
4. [Everyday Docker Compose commands](#4-everyday-docker-compose-commands)
5. [Working with the database directly](#5-working-with-the-database-directly)
6. [Sample data](#6-sample-data)
7. [Production deployment](#7-production-deployment)
8. [Database migrations](#8-database-migrations)
9. [Running the tests](#9-running-the-tests)
10. [Implementation guide](#10-implementation-guide)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Prerequisites

| Tool | Version | Check |
|---|---|---|
| Docker Desktop | any recent version (ships Docker Compose v2) | `docker --version` and `docker compose version` |
| DBeaver *(optional)* | any recent | a graphical client for browsing and querying the database (see [§5.6](#56-using-dbeaver)) |

That is the **entire** requirement. You do **not** need Python, Node.js or PostgreSQL installed on your machine — the
application builds and runs completely inside containers. On Windows, Docker Desktop's default backend (WSL2) is
sufficient; no extra configuration is needed for this project.

Start Docker Desktop and wait for it to say "Docker Desktop is running" before continuing (`docker info` succeeds once it
is ready).

## 2. Environment variables

Docker Compose reads a `.env` file **in the project root** (next to `docker-compose.yml`) automatically. Copy the
template:

```bash
cp .env.example .env             # Windows PowerShell: copy .env.example .env
```

Nothing in it is required — `docker compose up --build` works immediately with the built-in defaults — but you should
set a real `SECRET_KEY` and `POSTGRES_PASSWORD` before leaving this running anywhere other than your own machine.

| Variable | Meaning | Default |
|---|---|---|
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | Credentials and database name used by both the `db` and `backend` containers | `postgres` / `postgres` / `scheduling` |
| `POSTGRES_PORT` | Host port mapped to PostgreSQL (for DBeaver/psql — see §5) | `5432` |
| `SECRET_KEY` | Key that signs login tokens. Generate a real one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` (no local Python? `docker run --rm python:3.12-slim python -c "import secrets; print(secrets.token_urlsafe(48))"`) | an insecure placeholder — fine for local use, **not** for anything reachable by anyone else |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Login token lifetime | `480` |
| `CORS_ORIGINS` | Extra browser origins allowed to call the API directly (comma-separated or a JSON list) — the main app doesn't need this since the frontend calls the API through its own nginx proxy, same-origin | `http://localhost:3000,http://127.0.0.1:3000` |
| `DEFAULT_CLASS_CAPACITY` | Seats used when none is specified | `30` |
| `DEFAULT_MIN_CREDITS` / `DEFAULT_MAX_CREDITS` | Initial allowed credit range (the sample data sets 16–27 in the database; Admin → Registration changes it) | `12` / `24` |
| `BCRYPT_ROUNDS` | Password-hash cost (higher = slower & stronger) | `12` |
| `BACKEND_PORT` | Host port mapped to the API directly (`/docs`) | `8000` |
| `FRONTEND_PORT` | Host port you open in your browser | `3000` |
| `SEED_ON_START` | Load the sample dataset automatically when the backend container starts (it skips itself once the database already has data — safe to leave on) | `true` |
| `RESET_ON_START` | **Wipe the database and reload fresh sample data on every container start.** Useful while developing the seed script itself; leave `false` for normal use | `false` |
| `SEED_ADMIN_PASSWORD` | Password for `admin@college.edu` when the sample data is created. Empty = the documented demo password `Admin@123`. **Set it whenever anyone else can reach the app.** Applied only when the data is first created (or reset) | *(empty)* |

> **Never commit `.env`.** It is already listed in `.gitignore`.

## 3. Quick start — Docker Compose

```bash
git clone <this repository>
cd scheduling-management-system
cp .env.example .env            # Windows PowerShell: copy .env.example .env — optional, see §2
docker compose up --build
```

What happens, in order:

1. Docker builds the `backend` image (installs Python dependencies) and the `frontend` image (runs `npm ci && npm run
   build`, then copies the result into an nginx image) — the first build takes a few minutes; later ones reuse cached layers.
2. The `db` container starts PostgreSQL and waits until it reports healthy (`pg_isready`).
3. The `backend` container starts only once `db` is healthy. Its entrypoint (`backend/docker-entrypoint.sh`) then:
   - waits until it can actually open a connection (a second, belt-and-braces check beyond the health check above);
   - runs `alembic upgrade head` to create every table;
   - loads the VIT-style sample dataset (`python -m app.db.seed`) — this takes about 20 seconds and **only happens
     once**: on every later start it detects the database already has data and skips itself;
   - starts `uvicorn`.
4. The `frontend` container starts only once `backend` reports healthy, and serves the built React app via nginx,
   proxying `/api/...` calls to the `backend` container.

Watch the `backend` service's log for `Starting the application server...` — that is your signal everything is ready
(`docker compose ps` should then show all three services as `healthy`; the frontend takes a further ~10–30 seconds to
report it after the backend does). Then open:

- **http://localhost:3000** — the application (sign in with a [sample account](#61-the-vit-style-sample-dataset))
- **http://localhost:8000/docs** — the interactive API reference

Stop it with `Ctrl+C` in that terminal, or run `docker compose down` from another one. **Your data is kept**: it lives in
a named Docker volume (`db_data`), so stopping and starting again (`docker compose up`) picks up exactly where you left
off — the seed step will not run again because the database is no longer empty. Run `docker compose down -v` to delete
that volume (and therefore all data) and start completely fresh next time.

### 3.1 Quick verification checklist

0. *(Optional command-line smoke test.)* From a second terminal:
   ```bash
   docker compose ps                                  # db, backend and frontend all "healthy"
   curl http://localhost:3000/api/health              # {"status":"ok"}  — i.e. nginx is proxying to the backend
   curl -X POST http://localhost:3000/api/auth/login -H "Content-Type: application/json" \
        -d '{"email":"admin@college.edu","password":"Admin@123"}'     # returns an access_token
   ```
   (In Windows PowerShell use `curl.exe` instead of `curl`, and put the login command on one line without the `\`;
   it is optional — the browser steps below cover the same ground.)
1. Sign in as `admin@college.edu` / `Admin@123` → **Dashboard** says *Schedule is clash-free* (36 offerings, 0 without a slot, 0 clashes).
2. **Slot Chart** lists slots such as `C1+TC1` and `L1+L2` with the offerings in them; **Offerings & Slots** shows BCSE202L with five faculty options, each with its own theory slot and lab slot.
3. On **Offerings & Slots** open *Add a faculty option* for any subject, choose a theory slot — teachers already teaching at an overlapping time are missing from the Faculty list (the "not listed — why?" note names them).
4. Sign in as `stu40@college.edu` / `Student@123` (group CSE-S3) → **Subjects** shows mandatory subjects already registered; **Slot View** groups every offering by slot.
5. Sign in as a faculty member (see [§6.1](#61-the-vit-style-sample-dataset)) → *My Classes* shows slot, lab slot and rooms; pending students appear in arrival order and only the first has **Accept**.

---

## 4. Everyday Docker Compose commands

Run these from the project root (where `docker-compose.yml` is).

```bash
docker compose up --build          # (re)build images if needed, then start all three services, logs in this terminal
docker compose up -d --build       # the same, but detached (returns you to the prompt)
docker compose logs -f             # follow every service's logs (Ctrl+C to stop watching, services keep running)
docker compose logs -f backend     # just one service
docker compose ps                  # status + health of each container
docker compose restart backend     # restart one service without rebuilding
docker compose up --build backend  # rebuild and restart just the backend after a code change
docker compose down                # stop and remove the containers (the db_data volume is kept)
docker compose down -v             # the same, AND delete all data (fresh start next time)
docker compose exec backend sh     # a shell inside the running backend container
```

There is no bind-mount/hot-reload set up for either service (this is a from-scratch, "it just runs" setup, not a live-dev
environment) — after changing backend or frontend code, rebuild that service's image with `docker compose up --build
<service>` to see the change.

---

## 5. Working with the database directly

`docker compose up` starts a completely normal PostgreSQL server; nothing about it is special to Docker once it is
running, and `POSTGRES_PORT` (default `5432`) maps it straight to your machine, exactly as a locally-installed
PostgreSQL would be. Connect with `psql`, DBeaver, or any other client:

```bash
psql -h localhost -p 5432 -U postgres -d scheduling      # or whatever you set POSTGRES_USER/PORT/DB to in .env
```

(No local `psql`? Run it from inside the `db` container instead: `docker compose exec db psql -U postgres -d scheduling`.)

Useful `psql` commands: `\dt` (tables) · `\d class_sections` (columns, constraints, indexes) · `\x` (expanded output) · `\q` (quit).

### 5.1 Inspection queries

**Which offerings share a slot** (students can take only one of them):

```sql
SELECT sl.name, sl.kind, string_agg(s.code || ' / ' || u.name, ', ' ORDER BY s.code) AS offerings
FROM slots sl
JOIN class_sections c ON sl.id IN (c.theory_slot_id, c.lab_slot_id)
JOIN subjects s ON s.id = c.subject_id
JOIN users u    ON u.id = c.faculty_id
GROUP BY sl.name, sl.kind HAVING count(*) > 1
ORDER BY sl.name;
```

**Courses that come with faculty options** (more than one offering):

```sql
SELECT s.code, count(*) AS faculty_options
FROM class_sections c JOIN subjects s ON s.id = c.subject_id
GROUP BY s.code HAVING count(*) > 1;
```

**Offerings with their slots, rooms and seats:**

```sql
SELECT s.code, u.name AS faculty, ts.name AS theory_slot, ls.name AS lab_slot,
       c.capacity, c.enrolled_count, c.status
FROM class_sections c
JOIN subjects s ON s.id = c.subject_id
JOIN users u    ON u.id = c.faculty_id
LEFT JOIN slots ts ON ts.id = c.theory_slot_id
LEFT JOIN slots ls ON ls.id = c.lab_slot_id
ORDER BY s.code, u.name;
```

**Mandatory subjects per student group:**

```sql
SELECT cu.group_code, string_agg(s.code, ', ' ORDER BY s.code) FILTER (WHERE cu.is_mandatory) AS mandatory
FROM curriculum cu JOIN subjects s ON s.id = cu.subject_id
GROUP BY cu.group_code ORDER BY 1;
```

**A class's FIFO queue — in exact serving order** (replace `8` with a class id):

```sql
SELECT jr.queue_seq, u.name AS student, jr.requested_at
FROM join_requests jr
JOIN users u ON u.id = jr.student_id
WHERE jr.class_id = 8 AND jr.status = 'PENDING'
ORDER BY jr.queue_seq;
```

**Unmet demand** (students who chose a subject but have neither a seat nor a pending request):

```sql
SELECT s.code, count(*) AS unmet
FROM registrations r JOIN subjects s ON s.id = r.subject_id
WHERE r.status = 'SELECTED'
GROUP BY s.code;
```

**One student's week:**

```sql
SELECT p.day, p.start_time, p.end_time, s.code, sl.name AS slot
FROM registrations r
JOIN class_sections c ON c.id = r.class_id
JOIN subjects s       ON s.id = c.subject_id
JOIN slots sl         ON sl.id IN (c.theory_slot_id, c.lab_slot_id)
JOIN slot_periods p   ON p.slot_id = sl.id
WHERE r.status = 'ENROLLED' AND r.student_id = (SELECT id FROM users WHERE email = 'stu40@college.edu')
ORDER BY array_position(ARRAY['Mon','Tue','Wed','Thu','Fri'], p.day::text), p.start_time;
```

**Admin alerts:**

```sql
SELECT n.type, n.message, n.is_read, n.created_at
FROM notifications n JOIN users u ON u.id = n.user_id
WHERE u.role = 'ADMIN' ORDER BY n.id DESC LIMIT 10;
```

**Clash audits** — every one of these should return **0 rows**. Two periods overlap when they are on the same day and
`start < other end` and `other start < end` — slots clash by *time*, not by name:

```sql
-- a teacher in two overlapping classes
SELECT a.faculty_id, a.id AS class_a, b.id AS class_b
FROM class_sections a
JOIN class_sections b ON b.faculty_id = a.faculty_id AND b.id > a.id
JOIN slot_periods pa ON pa.slot_id IN (a.theory_slot_id, a.lab_slot_id)
JOIN slot_periods pb ON pb.slot_id IN (b.theory_slot_id, b.lab_slot_id)
WHERE pa.day = pb.day AND pa.start_time < pb.end_time AND pb.start_time < pa.end_time
GROUP BY 1, 2, 3;

-- a student holding two overlapping classes
SELECT r1.student_id, r1.class_id AS class_a, r2.class_id AS class_b
FROM registrations r1
JOIN registrations r2 ON r2.student_id = r1.student_id AND r2.class_id > r1.class_id
JOIN class_sections a ON a.id = r1.class_id
JOIN class_sections b ON b.id = r2.class_id
JOIN slot_periods pa ON pa.slot_id IN (a.theory_slot_id, a.lab_slot_id)
JOIN slot_periods pb ON pb.slot_id IN (b.theory_slot_id, b.lab_slot_id)
WHERE r1.status = 'ENROLLED' AND r2.status = 'ENROLLED'
  AND pa.day = pb.day AND pa.start_time < pb.end_time AND pb.start_time < pa.end_time
GROUP BY 1, 2, 3;

-- a lecture hall booked by two classes at overlapping times
SELECT a.room_id, a.id AS class_a, b.id AS class_b
FROM class_sections a
JOIN class_sections b ON b.room_id = a.room_id AND b.id > a.id
JOIN slot_periods pa ON pa.slot_id = a.theory_slot_id
JOIN slot_periods pb ON pb.slot_id = b.theory_slot_id
WHERE pa.day = pb.day AND pa.start_time < pb.end_time AND pb.start_time < pa.end_time
GROUP BY 1, 2, 3;
```

**Integrity guard** — the database itself refuses overbooking:

```sql
UPDATE class_sections SET enrolled_count = capacity + 1 WHERE id = 1;
-- ERROR: new row for relation "class_sections" violates check constraint "ck_class_enrolled_le_capacity"
```

### 5.2 Reset data (keep the schema)

```sql
TRUNCATE users, students, faculty, subjects, faculty_subjects, class_sections, join_requests,
         registrations, slots, slot_periods, rooms, notifications,
         registration_settings, algorithm_runs
RESTART IDENTITY CASCADE;
```

Or let the seed script do it: `docker compose exec backend python -m app.db.seed --reset` (see §6), or just set
`RESET_ON_START=true` in `.env` and `docker compose restart backend` once.

### 5.3 Drop everything and start over

The simplest way, since the database lives in a Docker volume: **`docker compose down -v && docker compose up --build`**
— this deletes the `db_data` volume entirely and re-initialises (migrations + seed) from nothing.

To do the same thing with `psql` instead, without touching the container itself:

```sql
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
```

Then re-apply the schema: `docker compose restart backend` (its entrypoint runs `alembic upgrade head` on every start,
which is a no-op once the schema already matches, but recreates it here since you just dropped it) — or run `backend/db/schema.sql`
directly as in [§5.6 step 3](#56-using-dbeaver).

### 5.4 Backup & restore

```bash
docker compose exec db pg_dump -U postgres -Fc scheduling > scheduling.dump                        # backup to your machine
docker compose exec -T db pg_restore -U postgres -d scheduling --clean --if-exists < scheduling.dump   # restore
```

(`-T` disables TTY allocation so the file redirection works correctly.)

### 5.5 Key tables at a glance

| Table | Purpose |
|---|---|
| `users`, `students`, `faculty` | accounts and role profiles |
| `subjects` | a course: `credits` = theory credits, `lab_credits` > 0 means theory + lab |
| `faculty_subjects`, `class_sections` | an **offering**: one faculty teaching one subject, with seats and **its own** `theory_slot_id`, `lab_slot_id`, `room_id`, `lab_room_id` |
| `slots`, `slot_periods` | slot packages (`A1+TA1`, `L1+L2`, …) and their weekly meeting periods |
| `rooms` | lecture halls and labs (type + size) |
| `join_requests` | every request; rows with `status='PENDING'` ordered by `queue_seq` **are** the FIFO queue |
| `registrations` | a student's state per subject: `SELECTED` → `ENROLLED` (auto-queued for single-faculty subjects, or manual request for multi-faculty) |
| `notifications` | in-app notifications |
| `registration_settings` | single row: registration open/closed and credit range |
| `algorithm_runs` | log of slot-assignment / max-flow runs |

Built-in safeguards: `CHECK (enrolled_count <= capacity)`; `UNIQUE (student_id, subject_id)` on registrations (no double
registration); a partial unique index allowing only one live (pending/accepted) request per student per subject;
`UNIQUE (class_id, queue_seq)`; `UNIQUE (subject_id, faculty_id)` (a faculty offers a subject once);
foreign keys throughout. Slot-overlap and room rules span several rows, so they are enforced by the
application (and checked by the audit queries above).

### 5.6 Using DBeaver

DBeaver is only a window onto the same PostgreSQL database the `db` container runs; nothing in the project depends on
it, and you never need it to run the app.

1. **Connect:** *Database → New Database Connection → PostgreSQL*. Host `localhost`, port `5432` (or your `POSTGRES_PORT`),
   database `scheduling`, user `postgres`, the password from your `.env` → *Test Connection* (accept the driver download) → *Finish*.
   (The container must already be running: `docker compose up -d db` if you only want the database.)
2. **Browse:** *Databases → scheduling → Schemas → public → Tables*; double-click a table → *Data* tab. For a diagram,
   open a table → *ER Diagram* tab (or right-click *Tables* → *View Diagram*).
3. **Query:** *SQL Editor → New SQL script* (Ctrl+]) and run the queries in [§5.1](#51-inspection-queries) with Ctrl+Enter.
4. **Refresh after the app changes data:** select the table and press **F5** (DBeaver does not auto-refresh).

**Preparing a database by hand instead of letting the backend do it** (e.g. a DBA preparing the schema in advance, or
you want a custom dataset instead of the sample one): start only `db` (`docker compose up -d db`), then either open
`backend/db/schema.sql` in a DBeaver SQL script and *Execute script* (Alt+X), or from a terminal:

```bash
docker compose up -d db
psql -h localhost -p 5432 -U postgres -d scheduling -v ON_ERROR_STOP=1 -f backend/db/schema.sql
psql -h localhost -p 5432 -U postgres -d scheduling -v ON_ERROR_STOP=1 -f backend/db/sample_college_data.sql   # optional, the sample data as plain INSERTs
```

Then `docker compose up --build` as normal — the backend entrypoint sees the schema already matches and the data
already exists, and starts straight away without running migrations again or re-seeding.

> **Important — some defaults live in the application, not the database.** If you insert rows by hand (beyond the two
> files above) you must supply values for columns such as `users.is_active`, `students.max_credits`, `faculty.department`,
> `subjects.lab_credits`, `rooms.kind`, `curriculum.is_mandatory`, `faculty_subjects.default_capacity`, and
> `class_sections.capacity / enrolled_count / status / next_queue_seq`. Timestamps (`created_at`) are filled automatically.
> A class's slots and rooms may stay `NULL` ("not scheduled yet"): the Admin *Auto-assign slots* button then places it.
> Passwords must be **bcrypt hashes**, e.g. `docker compose exec backend python -c "from app.core.security import hash_password; print(hash_password('Admin@123'))"`.
>
> **Create the *workflow* data through the application, not SQL.** Join requests, enrolments and notifications involve
> business rules (queue order, atomic seat counting, slot-clash checks, auto-closing full classes, notifications). Inserting
> them directly bypasses those rules and can leave counters inconsistent. Use raw SQL for setup and for *reading* data.

Tips: use *Edit → Auto-commit* mode (default) for reads; avoid hand-editing `join_requests`, `registrations` or
`class_sections` counters. To start over, see [§5.3](#53-drop-everything-and-start-over).

---

## 6. Sample data

The backend container loads this automatically on first start (§3); you rarely need to run it yourself. To run it again
with different options, use `docker compose exec`:

```bash
docker compose exec backend python -m app.db.seed [--reset] [--no-activity] [--seed N]
```

| Flag | Effect |
|---|---|
| *(none)* | Structure, slot optimisation **and** a simulated registration (queues, full classes, unmet demand). Refuses to run on a non-empty database |
| `--no-activity` | Structure and slots only: all offerings placed, no student requests (everything is still unlocked, so you can re-run the optimiser) |
| `--reset` | Deletes all application data first |
| `--seed N` | Another random variant (same seed ⇒ identical data; default 2026) |

Passwords: `Admin@123`, `Faculty@123`, `Student@123`. **Change or remove them outside local demos.**

### 6.1 The VIT-style sample dataset

A semester modelled on VIT's FFCS structure (everything except faculty names, which are fake).

| What | Contents |
|---|---|
| **Slot chart** | 66 slots. Theory: 14 two-credit (`A1`…`G2`), 14 three-credit (`A1+TA1`…), 8 four-credit (`A1+TA1+TAA1`…) — "1" = morning, "2" = afternoon family. Labs: 30 two-period pairs `L1+L2` … `L59+L60`. Theory and lab slots overlap in time as in the real chart (e.g. `A1` Mon 08:00 overlaps `L1`) |
| **Courses** | 29 courses with VIT-style codes (BMAT101L Calculus, BCSE202L Data Structures and Algorithms, BCSE302L Database Systems, BECE204L Microprocessors…); 19 are theory+lab (one selectable unit with its own lab slot), 10 theory-only |
| **Students** | 122 students (`stu1`–`stu122`) in a single pool — all students can pick from all courses up to their chosen credit load |
| **Option courses** | exactly two courses have faculty options: **BMAT101L Calculus** (theory only, 4 faculty) and **BCSE202L Data Structures and Algorithms** (theory+lab, 5 faculty — each with their own lab slot; two of them share lab slot `L1+L2` and so use different lab rooms). Single-faculty subjects auto-queue the student when selected. Every other course has a single faculty |
| **Faculty** | 26 faculty with fake names (e.g. `Dr. Rajesh Patel`), e-mail `first.last@college.edu`; each teaches 1–2 courses; the optimiser places everyone without any teacher overlap |
| **Rooms** | 10 lecture halls (60–120 seats) and 8 labs (60 seats) |
| **Registration state** | credit range 16–27; students pick subjects freely (single-faculty subjects auto-queue automatically); some classes fill (e.g. Calculus faculty 1 & 2), some queues stay pending, `BCSE306L` (AI) and `BCSE307L` (Compiler Design) have unmet demand |

Useful logins (password `Faculty@123` / `Student@123`):

| Role | Account |
|---|---|
| Admin | `admin@college.edu` / `Admin@123` |
| DSA faculty (option course) | `rajesh.patel@…` (C1+TC1, lab L1+L2), `anita.subramanian@…` (D1+TD1, lab L1+L2), `priya.iyer@…`, `shalini.naidu@…`, `anita.shetty@…` |
| Calculus faculty (option course) | `harish.mehta@…`, `ananya.patel@…`, `mohan.shetty@…`, `neha.menon@…` |
| Students | `stu1@college.edu` … `stu122@college.edu` (all `@college.edu`); the group is in *Admin → People* |

(Names are deterministic for the default seed; with another `--seed` look them up in *Admin → People*.)

**Things to try**
- *Admin → Slot Chart*: slots with several subjects show "N subjects share this slot — students pick one".
- *Admin → Offerings & Slots*: add an offering and pick the theory slot first — teachers who already teach at an overlapping time are not in the Faculty list.
- *Admin → Scheduling*: **Clear unlocked slots** then **Auto-assign slots**. With the activity data most offerings are locked (students enrolled), so seed with `--no-activity` to re-optimise *everything* (the Calculus/DSA slots are un-placed too, and the optimiser re-places them):
  `docker compose exec backend python -m app.db.seed --reset --no-activity`.
- *Student (e.g. `stu40`) → Subjects*: pick a subject with multiple faculty to see the clash detection — if they're all at the same time, you get a "subject clash" message. Picking a single-faculty subject auto-queues you immediately.
- *Student → Subjects → Clash Report*: see all subjects that clash at the offering level (part-type detail: which theory/lab sessions overlap and when).
- *Admin → Demand*: raise the seats of `BCSE306L` and watch the unmet students be auto-queued (the sync system marks them as waiting and notifies them).

**Not modelled** (the schema has no place for them): per-faculty availability windows, a per-faculty maximum workload, and
tutorial/"embedded" component variants beyond one theory slot + one lab slot per offering. Treat these as future extensions.

---

## 7. Production deployment

To host it on **Render** (database + backend + static frontend from the `render.yaml` Blueprint) follow
[DEPLOY.md](DEPLOY.md). The rest of this section is for running the Docker Compose setup on a server you control.

The Dockerfiles are already production-shaped (the frontend is a static build served by nginx; the backend runs plain
`uvicorn`), so the path from "runs on my machine" to "runs on a server" is mostly configuration, not a different setup:

1. **Secrets.** Set a real, unique `SECRET_KEY`, a strong `POSTGRES_PASSWORD` and a `SEED_ADMIN_PASSWORD` in `.env` on
   the server — never reuse the defaults from `.env.example` (the sample admin password is public).
2. **Database.** Either keep the `db` service (fine for a small/single-server deployment — its data volume should then
   be included in your backup strategy, see §5.4) or point `DATABASE_URL`/`POSTGRES_*` at a managed PostgreSQL instance
   instead and remove the `db` service and its `depends_on` entries from `docker-compose.yml`.
3. **Workers.** For more throughput, run multiple backend workers by overriding the backend service's command, e.g. add
   `command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4` to `docker-compose.yml` (or a
   `docker-compose.override.yml`). Multiple workers are safe: queue order and seat counts are protected by database row
   locks and constraints, not process memory.
4. **TLS / a real domain.** Put a reverse proxy (nginx, Caddy, Traefik, or your cloud provider's load balancer) in front
   of the `frontend` service for HTTPS; point it at `frontend`'s port 80. Do **not** rely on the plain HTTP `frontend`
   container being reachable directly from the internet.
5. **Seeding.** Set `SEED_ON_START=false` once real data exists — the seed script is for demos — and never set
   `RESET_ON_START=true` on anything but a disposable demo instance.
6. **Images.** `docker compose build` and push the resulting images to a registry for a multi-server/CI deployment
   instead of building on the server itself; `docker compose up --build` is for convenience on one machine.
7. **Backups.** Automate §5.4 on a schedule.

---

## 8. Database migrations

Run these inside the backend container (it has `alembic` and the full app installed already):

```bash
docker compose exec backend alembic current                                   # which revision the database is at
docker compose exec backend alembic history                                   # list revisions
docker compose exec backend alembic upgrade head                              # apply all pending migrations (also runs automatically on container start)
docker compose exec backend alembic downgrade -1                              # undo the last migration
docker compose exec backend alembic check                                     # models and migrations agree? ("No new upgrade operations detected")
docker compose exec backend alembic revision --autogenerate -m "add column"   # create a migration from model changes (review it!)
```

An autogenerated migration is created **inside the container**, so copy it back to your working tree to commit it:

```bash
docker compose cp backend:/app/alembic/versions/. backend/alembic/versions/
```

Regenerate the plain-SQL schema after adding a migration, then copy it out the same way:

```bash
docker compose exec backend sh -c "alembic upgrade head --sql > /tmp/schema.sql 2>/dev/null"
docker compose cp backend:/tmp/schema.sql backend/db/schema.sql
```

If you change the sample data generator, regenerate `db/sample_college_data.sql` from a database that already has the
new data loaded (the redirect writes straight to your working tree; `-T` disables TTY allocation so it works correctly):

```bash
docker compose exec -T db pg_dump -U postgres -d scheduling --data-only --column-inserts --no-owner --exclude-table=alembic_version > backend/db/sample_college_data.sql
```

---

## 9. Running the tests

The backend image already has `pytest` installed — no separate environment to set up:

```bash
docker compose up -d db backend
docker compose exec backend pytest -q
```

By default the tests use **in-memory SQLite** — no database needed for most of them. Three concurrency tests need
PostgreSQL row locks and are skipped under SQLite. To run the **entire suite on PostgreSQL**, create a scratch database
in the same `db` container and point the tests at it (its tables are dropped and recreated on every run — never use a
database with real data):

```bash
docker compose exec db createdb -U postgres scheduling_test
docker compose exec -e TEST_DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/scheduling_test backend pytest -q
```

(Adjust the user/password in that URL if you changed `POSTGRES_USER`/`POSTGRES_PASSWORD` in `.env`. The host is `db` —
the service name on the Compose network — not `localhost`, because this runs *inside* the backend container. Drop the
scratch database afterwards with `docker compose exec db dropdb -U postgres scheduling_test`.)

**Expected result** with the sample setup: every test passes — on PostgreSQL all of them run (one case is skipped because
it needs the root `.env.example`, which is not in the image); on the default SQLite run the three PostgreSQL-only
concurrency tests are skipped as well. The tests are copied into the backend image when it is built, so after editing a
test file run `docker compose up -d --build backend` (or `docker compose cp backend/tests backend:/app/` for a quick try)
before re-running `pytest`.

| Test file | What it checks |
|---|---|
| `test_algo_fifo_greedy.py` | FIFO ordering and edge cases; Greedy selection, ties, configurability |
| `test_algo_coloring_flow.py` | Conflict-graph building, valid/impossible colourings, backtracking, "unknown, try one more" handling; Edmonds-Karp on known networks |
| `test_algo_slot_assignment.py` | The slot optimiser: clashes by time overlap, per-vertex domains, pre-placed offerings, room limit per period, infeasible cases, determinism, step budget |
| `test_slot_scheduling.py` | VIT-style slot chart; busy teachers hidden from the drop-down; faculty clashes refused; theory+lab pairing rules; shared lab slot → different rooms; slot lock; student clash blocking; subject-level clash detection (part-type detail); unscheduled offerings; auto-assign rules; slot chart, timetables, clash report |
| `test_registration_faculty_workflow.py` | Credits, subjects (free picking, auto-queue for single-faculty), queueing, acceptance in order, full-class rejection, notifications, admin capacity changes |
| `test_auth_rbac.py` | Password hashing, login, forged/expired tokens, every role boundary, input validation |
| `test_integration_workflow.py` | The full slot-first flow over HTTP: slot chart → offerings → eligible faculty → auto-assign → FIFO → full class → capacity → timetables |
| `test_seed_sample.py` | The VIT-style sample dataset: fake faculty names, exactly two option courses, 122-student single pool, shared lab slot, no clashes, simulated registration never double-books a student, auto-queue on single-faculty subject selection |
| `test_config.py` | A `.env` in the `.env.example` format loads correctly (inline comments, Compose-only keys such as `POSTGRES_*`/`FRONTEND_PORT`, comma-separated `CORS_ORIGINS`, JSON list, single value); the real root `.env.example` is checked too when the file is reachable (it is not inside the backend image, so that one case is skipped in-container); a database connection failure returns a clear 503 |
| `test_concurrency.py` | Parallel accepts never overbook; unique queue positions; double-submit safety (PostgreSQL only) |

The frontend has no automated tests; verify it manually with the checklist in §3.1. `npm run build` (which
`docker compose up --build frontend` already runs for you) also catches syntax errors.

---

## 10. Implementation guide

### Where things live

| To change… | Edit |
|---|---|
| A business rule (capacity, queue, registration, clash checks) | `backend/app/services/*.py` |
| The slot chart (names, periods, timings) | `slot_service.standard_chart()` (`THEORY_GRID`, `THEORY_START`, `LAB_PERIODS`) |
| What the optimiser treats as a conflict | `timetable_service.build_problem()` |
| How rooms are assigned | `room_service.assign_rooms()` |
| An algorithm | `backend/app/algorithms/*.py` (pure Python — keep HTTP/DB imports out) |
| A new endpoint | add a function in `backend/app/routers/<role>.py` that calls a service; use the `require_admin` / `require_faculty` / `require_student` dependency |
| Request validation | `backend/app/schemas/schemas.py` |
| The database structure | `backend/app/models/*.py`, then create a migration (§8) |
| The sample data | `backend/app/db/seed.py` (`COURSES`, `STUDENT_COUNT`) |
| What happens on container start | `backend/docker-entrypoint.sh` |
| A screen | `frontend/src/pages/<role>/…`; register its route in `frontend/src/App.jsx` and menu in `layouts/DashboardLayout.jsx` |
| A frontend API call | `frontend/src/api/index.js` (all calls are centralised here) |
| How the frontend reaches the backend | `frontend/nginx.conf` (the `/api/` proxy) |

After any backend or frontend code change, rebuild that service to see it: `docker compose up --build backend` or
`docker compose up --build frontend` (§4).

### Request flow (backend)

`router` (HTTP, auth, validation) → `service` (rules, transaction, notifications) → `model`/database. Services raise
`DomainError` subclasses (`NotFoundError`, `ConflictError`, …); `main.py` converts them to JSON `{detail, code}`.

### Common extensions

**Add a Greedy criterion** — in `greedy_faculty_allocation.py` add a function to the `CRITERIA` dict, then list its name in
`DEFAULT_CRITERIA` (order = priority) or in `allocation_service.GREEDY_CONFIG`.

**Add a scheduling rule** — add the extra "must not overlap" (hard) or "prefer not to overlap" (soft) edges in
`timetable_service.build_problem()`; the algorithm and the clash report pick them up automatically.

**Add a database column** — change the model → `docker compose exec backend alembic revision --autogenerate -m "…"` →
copy it out and review it (§8) → rebuild (`docker compose up --build backend`, which runs the migration on start) →
regenerate `db/schema.sql` (§8) → add tests.

**Locking rule of thumb** — any code that changes a class's seats or queue must load the class with
`capacity_service.get_class(db, id, lock=True)` first and finish in one transaction.

> **Editing files on Windows:** if you script edits with Python, use UTF-8 explicitly (`python -X utf8`, or
> `read_text(encoding="utf-8")`) — the default Windows code page corrupts characters such as `·` and `—`.

---

## 11. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `Cannot connect to the Docker daemon` / `docker info` fails | Docker Desktop is not running. Start it from the Start Menu/Applications and wait for it to report "running" before retrying. |
| `docker compose up` hangs with `backend` never becoming healthy | Check its logs: `docker compose logs backend`. Usually a one-off: wait longer (first start runs migrations + ~20s of seeding), or it will show the real error (bad `SECRET_KEY`, etc.). |
| `port is already allocated` | Something else on your machine is already using port 3000, 8000 or 5432. Change `FRONTEND_PORT` / `BACKEND_PORT` / `POSTGRES_PORT` in `.env` and `docker compose up` again. |
| Login page shows *"The server cannot reach the database"* (HTTP 503) | The `backend` container cannot reach `db`. Check `docker compose ps` (is `db` healthy?) and `docker compose logs db`. If you edited `POSTGRES_*` in `.env` after the volume was created, the existing database still has the old password — run `docker compose down -v` to reset, or change `.env` back. |
| Login says *Incorrect email or password* for every user | The database is empty — `SEED_ON_START` may be `false`, or the seed step failed (check `docker compose logs backend`) — or the e-mail is wrong: faculty use `first.last@college.edu`, students `stuN@college.edu`. |
| Dashboard / login says *"The database structure is out of date"* (`SCHEMA_OUTDATED`) | Only possible if you point this version of the app at a database created by an older version. `docker compose down -v` to start from an empty, current schema. |
| An old native install (venv/`npm run dev`) still lying around and confusing things | This project's **only** supported way to run is `docker compose up --build`; remove any local `backend/.venv`, `backend/.env`, `frontend/node_modules` or background `uvicorn`/`vite` processes from a previous version of this guide — they are unused now and can conflict on the same ports. |
| `Everyone is logged out after a restart` | `SECRET_KEY` changed (e.g. you edited `.env` and ran `docker compose up` again). Tokens signed with the old key are rejected — sign in again. |
| `401 Invalid or expired token` | Token expired (default 8 h) — sign in again. |
| `docker compose build` is slow or seems stuck | First build downloads base images and installs all dependencies — normal to take a few minutes depending on your connection. Subsequent builds reuse Docker's layer cache and are much faster; `docker compose build --no-cache` forces a clean rebuild if you suspect stale layers. |
| CORS error calling the API from somewhere other than the bundled frontend | Add that origin to `CORS_ORIGINS` in `.env` and `docker compose up -d backend` to restart it with the new value. |
| Scheduling: *Load the standard slot chart first* (`NO_SLOTS`) | No slots exist yet. *Offerings & Slots → Load the standard slot chart* (or `POST /api/admin/slots/load-standard`). |
| Scheduling: *No clash-free placement exists* (`PLACEMENT_INFEASIBLE`) | Too few slots/rooms for the rules (a teacher with too many courses, a group with too many mandatory subjects, or too few rooms). Add rooms, spread the teachers' courses, or fix a hand-placed slot. Nothing is saved on failure. |
| *Faculty clash* / *theory and lab slot overlap* (`FACULTY_CLASH`, `SLOT_SELF_CLASH`) when placing | The chosen slot overlaps another class of that teacher, or the offering's own lab. Pick another slot; the teacher list on the form already hides busy teachers. |
| *Students are enrolled or waiting … slot cannot be changed* (`SLOT_LOCKED`) | An offering with students is locked so nobody is silently put into a clash. Resolve the requests/enrolments first. |
| *No free room of the right type and size* (`NO_ROOM`) | Add a lecture hall / lab (Scheduling → Rooms) or choose a less crowded slot. |
| Student sees *Slot clash: X overlaps Y which you already hold* | By design: the offering overlaps in time with a class the student already has. They pick another option (Slot View shows which). |
