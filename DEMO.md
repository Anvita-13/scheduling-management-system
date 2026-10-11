# Demo Walkthrough

A guided tour of the application in the order you would present it: **Admin → Faculty → Student**, each interface tab by
tab, with every function, **which algorithm is behind it, and how that algorithm works**. Use it as a speaking script or a
checklist while you click through.

> Companion documents: [README.md](README.md) (overview) · [SETUP.md](SETUP.md) (install and database) ·
> [WORKFLOW.md](WORKFLOW.md) (the whole system explained in plain language, with more algorithm detail).

## Contents

0. [Before you start](#0-before-you-start)
1. [The idea in one minute](#1-the-idea-in-one-minute)
2. [Admin](#2-admin) — Dashboard · Offerings & Slots · Slot Chart · Scheduling · Demand & Waitlist · Registration · People · Algorithm Insights · Notifications
3. [Faculty](#3-faculty) — Dashboard · My Classes (class detail) · Timetable · Notifications
4. [Student](#4-student) — Dashboard · Credit Selection · Subjects (options) · Slot View · Request Status · Timetable · Notifications
5. [Algorithm cheat sheet](#5-algorithm-cheat-sheet)
6. [A 10-minute demo script](#6-a-10-minute-demo-script)

---

## 0. Before you start

1. Start everything with Docker Compose ([SETUP.md §3](SETUP.md#3-quick-start--docker-compose)): `docker compose up --build`.
   The sample data loads automatically on first start. Open <http://localhost:3000>.
2. Accounts used in this walkthrough (password `Admin@123`, `Faculty@123`, `Student@123`):

| Role | Account | Why this one |
|---|---|---|
| Admin | `admin@college.edu` | sees everything |
| Faculty | `rajesh.patel@college.edu` | teaches **BCSE202L Data Structures and Algorithms** (theory `C1+TC1`, lab `L1+L2`) — an *option course* with a lab pair |
| Faculty | `anita.subramanian@college.edu` | the DSA faculty who shares lab slot `L1+L2` (different lab room); may have a waiting queue |
| Student | `stu40@college.edu` | group `CSE-S3`, mandatory DSA + Probability, already enrolled |
| Student | any `stu37`–`stu72` | other `CSE-S3` students; `stu1`–`stu36` are `BTECH-FY`, `stu73`–`stu100` `CSE-S5`, `stu101`–`stu122` `ECE-S3` |

(Faculty names are generated and deterministic for the default seed; if yours differ, look them up in **Admin → People**.)

3. Demo actions change data. To get back to the starting point: `docker compose exec backend python -m app.db.seed --reset`
   (or `docker compose down -v && docker compose up --build` for a completely fresh container + database).
4. Keep a second browser profile (or private window) open so you can switch roles without signing out repeatedly.

## 1. The idea in one minute

- A **slot** is a weekly package of meeting periods: theory `A1+TA1` = Mon 08:00, Wed 09:00, Fri 10:00; lab `L1+L2` = Mon 08:00–09:40.
  Two slots **clash when their periods overlap in time**, not when their names match.
- An **offering** = one faculty teaching one subject, with **its own** slot(s). For theory+lab subjects it is a fixed **pair**
  (that faculty's theory slot + that faculty's lab slot) — a student cannot mix one teacher's theory with another's lab.
- Different subjects in the same slot are **alternatives** (a student can hold one).
- Each student **group** (programme + semester) has **2 mandatory** subjects (registered automatically) and many optional ones.
  Only two courses have several faculty options in the sample data: **BMAT101L Calculus** (4 faculty, theory only) and
  **BCSE202L Data Structures and Algorithms** (5 faculty, theory+lab).
- **Slots are fixed before registration.** The main job of the system is *scheduling optimisation*; registration then
  works inside a schedule that is already clash-free.

The four algorithms, where you will meet them:

| # | Algorithm | You will see it in |
|---|---|---|
| 3 | Backtracking Graph Coloring | Admin → **Scheduling** (and Insights) — places every class into slots |
| 1 | FIFO Queue | Student **requests**, Faculty **class detail** — fair order |
| 2 | Greedy Faculty Allocation | Student **options** ("Suggested"), "class is full" messages |
| 4 | Edmonds-Karp Maximum Flow | Admin → **Algorithm Insights → Max Flow** — seat planning |

---

## 2. Admin

Sign in as `admin@college.edu`. The left menu, in order: **Dashboard · Offerings & Slots · Slot Chart · Scheduling ·
Demand & Waitlist · Registration · People · Algorithm Insights · Notifications**.

### 2.1 Dashboard

**What it shows**
- A banner: *"Schedule is clash-free — all N offerings are placed with rooms"*, or *"Scheduling needs attention"* with counts of
  offerings without a slot, clashes and offerings without a room (with a link to **Scheduling**).
- A warning if registration is closed.
- Stat cards: **Offerings**, **Without a slot**, **Clashes** (should always be 0), **Unmet demand**, **Seats filled**,
  **Pending requests**, **Full classes**, **Registration** (open/closed).
- **System alerts**: unread notifications for the admin (class full, no faculty available, schedule updates…).

**Talking point:** this is the health check — a quick yes/no on "is the timetable valid and is anyone left without a seat?".
**Algorithm:** none runs here; the numbers come from the clash report (§2.4) and the demand report (§2.5).

### 2.2 Offerings & Slots

This is where subjects are created and where teachers get slots. One card per subject.

**Functions, top to bottom**
1. **Add a subject** — code, name, **theory credits** (2, 3 or 4 match the slot packages) and **lab credits** (0 = theory only,
   >0 = theory + lab).
2. **Load the standard slot chart** (appears only if no slots exist) — creates the 66 VIT-style slots in one click.
3. **Filter subjects** box.
4. **Offerings table** per subject: Faculty · Theory slot (with times) · Lab slot (with times) · Rooms · Seats · Status. Per row:
   - **Seats** box + Save — change capacity (cannot go below the number already enrolled). Raising a full class **reopens it** and
     notifies the teacher and waiting students.
   - **Slots** button — move the offering to other slots (disabled and greyed when students are enrolled or waiting: the offering is *locked*).
   - **Close / Reopen** — stop or resume accepting requests (waiting students are rejected and notified when closing).
   - **Remove** — delete an offering that has no students.
   - A **Needs slot** badge marks offerings the optimiser should place.
5. **Add a faculty option** form (under each subject):
   - Pick the **theory slot** (only packages with the subject's credit value are listed; theory+lab subjects also ask for the
     **lab slot** — that faculty's own lab).
   - The **Faculty** list then **filters itself**: a teacher already teaching at an overlapping time is *not listed*. Beneath it,
     *"N teacher(s) not listed — why?"* names each teacher and the class that blocks them.
   - Enter seats and **Add**. Or leave the slots on *"Leave for the optimiser"* and add just a teacher.

**Rules the server enforces here** (try each — you get a clear message):
- A slot with the wrong credit value is refused.
- A theory+lab offering needs **both** slots, and the theory slot must not overlap its own lab slot.
- A teacher cannot be placed where they already teach (`FACULTY_CLASH`).
- A slot that would leave no free room of the right type and size is refused (`NO_ROOM`).
- A locked offering's slot cannot be changed (`SLOT_LOCKED`).

**Algorithm — overlap check (not one of the four, but the core rule):** every slot is a set of weekly periods
`(day, start, end)`. Two slots clash if any two periods are on the same day and `start₁ < end₂` and `start₂ < end₁`.
That is why `F1` (Mon 09:00–09:50) clashes with lab `L1+L2` (Mon 08:00–09:40) even though they are different slots. The teacher filter
runs this check against every class the teacher already has.

**Demo move:** open **BCSE202L**. Show the five options, each with its own theory slot and lab slot, and point out that two
options share lab slot `L1+L2` but use different lab rooms. Then open *Add a faculty option*, pick theory slot `C1+TC1`, and show that
Dr. Rajesh Patel has vanished from the list, with the "why?" note.

### 2.3 Slot Chart

**What it shows:** every slot **that has offerings**, as cards — slot name, kind (Theory/Lab), its meeting times, and the offerings in it
(subject, faculty, seats, room, whether it is the theory or the lab part). A yellow note appears when several subjects share the slot:
*"N subjects share this slot — students pick one"*. A banner lists offerings that have no slot yet; a counter shows how many theory and
lab slots are still free.

**Functions:** Theory / Lab / All filter, Refresh.

**Talking point:** this answers *"which subjects are in the same slot, i.e. offered as options?"* at a glance.
**Algorithm:** none; it is a view of the placement the optimiser (§2.4) and the admin produced.

### 2.4 Scheduling  ← the main feature

**What it shows:** four stat cards (Offerings, Without a slot, Clashes, Without a room), the **Clash report**, the **weekly
timetable** of all placed offerings (theory in blue, labs in green, with rooms), and **Rooms**.

**Functions**
- **Auto-assign slots** — runs the optimiser. It places every offering that has no slot and **never moves** offerings that are
  already placed. Afterwards it reports: how many it placed, how many states it searched, whether **backtracking** was needed
  (and how many choices were undone), and how many optional-subject overlaps remain. If it cannot place everything it explains
  why and **saves nothing**.
- **Clear unlocked slots** — un-places every offering with no students, so the optimiser can redo them from scratch.
- **Clash report** — *Offerings without a slot*, *without a room*, *clashes that must be fixed* (teacher or mandatory-subject
  overlaps), *students with overlapping classes*, and *optional subjects sharing time* (informational: students of that group pick one).
- **Rooms** — add/delete lecture halls and labs by **type and size only**. Which class gets which room is automatic.

**Algorithm — Backtracking Graph Coloring (the optimiser)**

*What it solves.* Give every class part a slot so that nothing that must not overlap, overlaps.

*How it is modelled.*
- **Dots (vertices):** every offering's theory part, and its lab part for theory+lab courses.
- **Lines (edges) = "must not overlap":** same teacher · theory vs its own lab · two *mandatory* subjects of one group · a mandatory subject
  vs any optional subject of that group. A weaker "prefer not to overlap" line joins optional subjects of one group.
- **Colours = slot packages**, but clashes are by *time overlap*, not "same colour".
- **Choices per dot:** a 3-credit theory part may only take 3-credit theory slots; a lab part only lab slots.
- **Fixed dots:** offerings already placed stay as they are and block their slots.
- **Room limit:** at most *(number of lecture halls)* theory parts, or *(number of labs)* lab parts, may meet at the identical time.

*How it searches (backtracking).*
1. Order the dots **most lines first** (the hardest are placed while there is freedom).
2. For each dot try the slots best-first — preferring the one that overlaps the fewest optional subjects and is least used.
3. A slot is **safe** if it overlaps no already-placed neighbour in time and does not exceed the room limit. Place it and move on.
4. If a later dot has no safe slot, **go back**, undo the last placement and try the next slot (that undo is a *backtrack*).
5. Stop when every dot is placed — or report "impossible" when all options are exhausted. A step budget stops runaway searches.

*Worked mini-example.* A may use S1 or S2, B only S1, C S2 or S3; A–B and A–C must not overlap. A tries S1 → B (only S1) clashes → **backtrack**,
A takes S2 → B takes S1 → C avoids S2 and takes S3. Done.

*Then:* rooms are assigned automatically (biggest class first, each takes the smallest free room of the right type that fits), and the result is re-verified.

*Complexity:* worst case **O(kᵛ)** (k candidate slots, V class parts — graph colouring is NP-complete); in practice highest-degree-first ordering,
fixed placements and per-part slot lists make the 36 sample offerings solve in a fraction of a second.

**Demo move:** (a) show the clean clash report; (b) press **Clear unlocked slots**, then **Auto-assign slots**, and read the result banner.
*Tip:* if you seeded **with** registrations, most offerings are locked; seed with `docker compose exec backend python -m app.db.seed --reset --no-activity` for a full
re-optimisation demo (all 36 offerings, including the Calculus and DSA slots, are re-placed with 0 clashes).

### 2.5 Demand & Waitlist

**What it shows:** stat cards (**Unmet demand**, subjects with **no open class**, total enrolled, waiting in queues); a red alert per subject where
every class is full or closed; **Demand per subject** (demand, enrolled, waiting, unmet, free seats); and the **Waitlist** of students without a seat.

**Functions:** **Adjust capacity** on a subject expands its classes with a seats editor — increasing seats reopens a full class, notifies the teacher and
every student still without a seat for that subject.

**Algorithms behind it:** the *unmet* and *no faculty available* alerts are produced by the **FIFO queue** flow (when a class fills, everyone still waiting is
cleared in order and counted as unmet) — see §3.2. The planning question "how many of these could we seat?" is answered in **Algorithm Insights → Max Flow** (§2.8).

**Demo move:** open the subject `BCSE306L Artificial Intelligence` (scarce), raise its seats, then show the waiting students being notified (Notifications / the student's inbox).

### 2.6 Registration

**What it shows:** the period status (**Open/Closed**), counters (students, chose credits, registrations, enrolled, pending requests) and the **allowed credit range**.

**Functions:** **Close / Reopen registration** (all students are notified; while closed, students cannot change credits, pick or drop subjects, or send requests —
cancelling a waiting request is still allowed); **Save** the minimum/maximum credits (the sample data uses 16–27).

**Algorithm:** none — a control switch for the workflow.

### 2.7 People

**What it shows:** two tabs, **Faculty** (name, **email = the login**, employee code, department, subjects taught) and **Students** (roll number, **group**, credit target,
max credits). Each tab has an **Add** form (initial password at least 8 characters; students take a *group* like `CSE-S3`, which decides their mandatory subjects).

**Algorithm:** none. Passwords are stored as bcrypt hashes.

### 2.8 Algorithm Insights

Read-only demonstration page — nothing here changes enrolments, queues or capacity. Four tabs, one per algorithm, each ending with its complexity.
At the bottom, **Algorithm execution status** lists recent optimiser and max-flow runs.

| Tab | Controls | What it displays |
|---|---|---|
| **1 · FIFO Queue** | choose a class → **Run** | the queue *before* (in arrival order with sequence numbers), who **would be accepted, in order**, and who would be **turned away when the class fills** |
| **2 · Greedy Faculty Allocation** | choose a subject (and optionally a preferred faculty) → **Run** | every candidate with rank, free seats, queue length, slot-compatibility, availability and its **priority vector**; the selected one; the reason |
| **3 · Backtracking Graph Coloring** | **Run dry-run (nothing is saved)** | offerings to place vs already placed, number of must-not-overlap edges (with the *reason* for each), states visited, **backtracks**, the slots it would pick |
| **4 · Edmonds-Karp Max Flow** | **Run Edmonds-Karp** | requested vs **maximum seatable** vs unaccommodated students, **bottleneck classes**, per-subject outcome, an example best allocation, students who cannot be seated; each run is logged |

**Algorithms explained**

- **FIFO Queue.** A first-in-first-out line: new requests join at the back, only the front can leave. Enqueue/dequeue are **O(1)**. The line is also stored in the database as a per-class sequence
  number (1, 2, 3…), so order survives restarts. *Why:* fairness by arrival time is the college rule — a queue makes cutting in line impossible.
- **Greedy Faculty Allocation.** Take the best option **right now** without reconsidering earlier choices. Steps: discard options that are closed, full, unscheduled or **overlap in time with
  something the student holds**; rank the rest by *(student's own choice, no clash, more free seats, shorter queue)*; ties → lowest class id. One scan, **O(F)**. *Why:* instant, explainable, never
  reshuffles anyone. It only **suggests** — the student decides.
- **Backtracking Graph Coloring.** As described in §2.4 (this tab shows its inputs and result).
- **Edmonds-Karp Maximum Flow.** Build a network *source → each waiting (student, subject) → each open, scheduled, non-clashing class of that subject → drain (capacity = free seats)*. Repeatedly find the
  **shortest** route with spare capacity (breadth-first search) and push flow along it, creating a **reverse "undo" edge** each time so later searches can reroute earlier choices. When no route remains, the
  total flow is the maximum number of students that could be seated; the saturated edges on the **minimum cut** are the **bottleneck classes**. Worst case **O(V·E²)**.
  *Example of the "undo":* classes A and B have 1 seat each; student 1 can take A or B, student 2 only A. A careless method seats student 1 in A and strands student 2; Edmonds-Karp moves student 1 to B so both are seated.
  *Planning tool only* — real seats are given by faculty acceptance, never by this analysis.

**Demo move:** run tab 3 (dry-run), tab 4 (note the unmet students and the bottleneck class), then tab 1 on a class with a pending queue.

### 2.9 Notifications

**What it shows:** the admin's inbox — *class full/closed*, *no faculty available*, *slots assigned by the optimiser*, etc. — with unread highlighting, **Mark read** and **Mark all as read**.
"No faculty available" alerts appear **once per subject until read**, to avoid flooding.

**Algorithm:** none.

---

## 3. Faculty

Sign in as `rajesh.patel@college.edu`. Menu: **Dashboard · My Classes · Timetable · Notifications**. A faculty member sees **only their own** classes — the server refuses anything else.

### 3.1 Dashboard

**What it shows:** stat cards (My classes, **Waiting requests** "in first-come-first-served order", Enrolled students, Total seats) and a **Classes** table: subject, **slot(s)**, seats bar,
waiting count, status, **Open**.

**Algorithm:** none directly (the waiting count is the length of each FIFO queue).

### 3.2 My Classes (and the class page)

**My Classes** shows one card per class: the **theory slot with times and room**, the **lab slot with times and lab room** (for theory+lab courses), seat bar, seats remaining, waiting count, and — if the
class is full or closed — a notice that no further requests are accepted. **Manage queue & students** opens the class page.

**Class page — functions**
- **Status / seats filled / seats remaining** and the slot/room summary; a banner explains *FULL* (closed automatically) or *CLOSED* (closed by someone).
- **Pending requests (n) — first come, first served**: a numbered table (#1, #2, …) with student, roll number and request time. **Only row #1 has buttons: Accept and Decline.** Everyone else shows
  *"Waiting for earlier requests"*. The page refreshes itself every 10 seconds.
- **Accept** — enrols the front student and notifies them.
- **Decline** — rejects the front student (with a suggested alternative in their notification).
- **Close class** — stop accepting; waiting students are rejected and notified.
- **Accepted students** table.

**Algorithm — FIFO Queue (how it works here)**
1. A student's request is stamped with a per-class sequence number and joins the **back** of the line (enqueue, **O(1)**).
2. *Accept* removes the **front** (dequeue, **O(1)**), consumes one seat atomically (a conditional update that can never exceed capacity) and enrols the student.
3. If that was the **last seat**, the class closes itself (*FULL*) and the **rest of the line is cleared in order**: each waiting student is rejected and notified — together with a suggestion from
   **Greedy Faculty Allocation** of another option that still has seats and does not clash with their timetable. If no option anywhere has seats, the **admin is alerted**.
4. The line is rebuilt from the stored sequence numbers every time, so it is identical after a restart or on another server; the browser only displays it, the server decides.

**Demo move:** open a class with a queue; point out that only #1 has buttons; click **Accept**; the next student becomes #1. (Trying to accept someone other than the front through the API is refused:
`NOT_FRONT_OF_QUEUE`.) Accept until the last seat to show the class turning FULL.

### 3.3 Timetable

**What it shows:** the faculty member's **weekly grid** — theory (blue) and lab (green) periods with subject, slot name and room.
It is **derived from the slots**: nothing needs generating at the end of registration.
**Algorithm:** none; it is a view of the optimiser's placement. By construction the teacher never has two overlapping classes.

### 3.4 Notifications

New join requests, class full/closed, seat increases, and **"Your class was scheduled in …"** messages after the optimiser places it.

---

## 4. Student

Sign in as `stu40@college.edu` (group `CSE-S3`). Menu: **Dashboard · Credit Selection · Subjects · Slot View · Request Status · Timetable · Notifications**.
Open a private window for a second student (e.g. a fresh one) if you want to demo selecting from scratch.

### 4.1 Dashboard

**What it shows:** warnings (registration closed; "start here" if no credits chosen; subjects that still need a faculty), stat cards (**Credit target**, **Credits selected**, **Enrolled subjects**, **Pending requests**)
and a **My subjects** table with status badges (*Selected → Requested → Enrolled*).
**Algorithm:** none.

### 4.2 Credit Selection

**What it shows / does:** choose a credit load with a number box and slider, within the allowed range (e.g. 16–27, and never above the student's personal maximum). An info box lists the group's
**mandatory subjects** — they are **added automatically when you save** and count toward the load. The server refuses a load lower than what the mandatory and already-selected subjects need.
**Algorithm:** none (rules enforced by the server).

### 4.3 Subjects (and the faculty-options page)

**Subjects table:** code, name with a badge (**Mandatory** / **Your group**), credits shown as theory+lab (e.g. `3+1 (T+L)`), *options with seats*, my status, and buttons:
**Select** (optional subjects; blocked if it would exceed the credit load), **Choose faculty / View options**, **Drop** (not for mandatory subjects, not once enrolled).

**Faculty-options page** (open a subject): a table of every faculty option with **theory slot (and times)**, **lab slot (and times)** for theory+lab courses, seat bar, waiting count and class status. Per option:
- **Send request** — joins that faculty's FIFO line and shows *"Queue position: n"*.
- **Suggested** badge — the option the Greedy algorithm recommends.
- **Clashes with …** (red, no button) — the option overlaps in time with a class the student already holds.
- **Not scheduled** — the offering has no slot yet.
- **Cancel my request** if one is waiting; a *"That class is full"* box with a **Request {other faculty} instead** button when a request hits a full class.

For theory+lab subjects an option is **one fixed pair**: choosing Dr. X gives Dr. X's theory slot **and** Dr. X's lab slot — nothing to mix.

**Algorithms at work**
- **Clash check (time overlap).** Before a request is accepted into any queue, the offering's periods are compared with every class the student is enrolled in or has requested; any overlap refuses the request and names the clashing subject. This is the "which student is accidentally picking the same slot" guarantee.
- **Greedy Faculty Allocation** — the **Suggested** badge and the full-class suggestion (see §2.8 for the steps). Example: the student's choice is full; alternatives are Iyer (3 free seats), Nair (7, but overlaps their timetable → discarded), Das (5 free) → **Das** is suggested. Their own choice always wins if it has a seat.
- **FIFO Queue** — the queue position after sending a request (§3.2).

**Demo move:** open `BCSE202L`; show the five options with different slot pairs; send a request to one; then on a student who holds a clashing class, show the red *"Clashes with …"* text.

### 4.4 Slot View

**What it shows:** every scheduled offering **grouped by theory slot** as cards: times, then each offering with subject, faculty, lab slot, free seats, a *Mandatory / Your group* badge, *Enrolled/Requested* highlight for the student's own, and *"Clashes with …"* in red. Banner on a card: *"alternatives — pick one"* when several subjects share the slot.

**Functions:** checkboxes **Only my group's subjects** and **Hide options that clash with mine**, a search box, and **Open subject** links.
**Algorithm:** the same time-overlap check as §4.3, shown visually. *Talking point:* "Subjects in the same card are alternatives; a red note means you already hold something that overlaps."

### 4.5 Request Status

**What it shows:** every request with subject, faculty, **slots**, status badge (Pending / Accepted / Rejected / Cancelled), details (**"Position #n in the queue"** while pending; the reason when rejected — *class was full*, *declined by faculty*…), and time sent.
**Functions:** **Cancel** a pending request; **Choose another faculty** for a rejected one.

**Algorithm — FIFO Queue:** the position is the number of pending requests ahead of yours in that class plus one; it drops as faculty accept from the front.

### 4.6 Timetable

**What it shows:** the student's personal weekly grid built from their **enrolled** classes — theory and lab periods with slot name and room, derived from the slots (no generation step).
**Algorithm:** none; clashes were prevented earlier, so the grid never overlaps.

### 4.7 Notifications

Request accepted/declined, **class full** (with a suggested alternative), **seats increased** for a subject they are waiting for, registration opened/closed.

---

## 5. Algorithm cheat sheet

| Algorithm | Where applied | Purpose | Why this one | Core idea | Complexity |
|---|---|---|---|---|---|
| **Backtracking Graph Coloring** | Admin → Scheduling / Insights | place every class into slots with no teacher, group, lab or room clash | scheduling is exactly graph colouring; backtracking finds a clash-free placement or proves none exists | dots = class parts, lines = must-not-overlap, colours = slots (clash = time overlap); try, check, recurse, **undo** on dead end | worst case O(kᵛ), pruned in practice |
| **FIFO Queue** | Student requests, Faculty class page | strict first-come-first-served acceptance | a queue makes unfair ordering impossible | enqueue at rear, dequeue from front; persisted as per-class sequence numbers | O(1) per operation |
| **Greedy Faculty Allocation** | Student options, "class is full" messages | suggest the best remaining option instantly | fast, explainable, never reshuffles others | filter unavailable/clashing → rank by (own choice, no clash, free seats, short queue) → pick best once | O(F) |
| **Edmonds-Karp Max Flow** | Admin → Insights | how many waiting students could be seated, and which classes are bottlenecks | exact solution that can reroute earlier choices | shortest augmenting paths (BFS) with reverse edges; min-cut = bottlenecks | O(V·E²) |

## 6. A 10-minute demo script

1. **(1 min) Idea.** Read §1: slots, offerings, theory+lab pair, groups, mandatory/option courses.
2. **(1 min) Admin → Dashboard.** "Schedule is clash-free."
3. **(2 min) Admin → Offerings & Slots.** Open BCSE202L: five options, own slot pairs, shared lab slot with different rooms. Add-option form: choose slot `C1+TC1` → the busy teacher disappears; read the "why?" note.
4. **(1 min) Admin → Slot Chart.** Find a slot with several subjects ("students pick one").
5. **(2 min) Admin → Scheduling.** Clash report, weekly grid. Explain the optimiser (§2.4). Optionally *Clear unlocked slots* → *Auto-assign slots* on a `--no-activity` database and read the backtracking count.
6. **(1 min) Admin → Algorithm Insights.** Tab 3 dry-run, tab 4 Max Flow (bottleneck class).
7. **(1 min) Faculty (`rajesh.patel`).** Class page: only #1 can be accepted — explain FIFO; Accept one.
8. **(1 min) Student (`stu40`).** Subjects → BCSE202L options (Suggested badge, a red clash), Slot View, Request Status (queue position), Timetable.

Close with the guarantees: no teacher/student/room is ever double-booked; seats can never be oversold; order is always arrival order; the admin can always override the optimiser.
