"""PHASE 1 / ALGORITHM 3 - Backtracking Graph Coloring for timetable generation.

This module holds the textbook algorithm (``backtracking_color`` / ``color_with_min_slots``: "fewest identical
colours") and, at the bottom, the generalisation the application uses (``backtracking_slot_assignment``: slot
packages as colours, clashes by *time overlap*, per-vertex domains, pre-placed vertices, a room limit per period
and soft preferences). Both use the same recursive try / check / recurse / undo search.

Model
-----
* vertex  = a class section that needs a time slot
* edge    = two classes that must NOT run simultaneously, because they share a faculty
            member, share at least one registered student, or were explicitly
            configured as conflicting (shared lab, etc.)
* colour  = a time slot

Goal: give every vertex a colour so adjacent vertices never share one.

Search (recursive backtracking)
-------------------------------
``backtracking_color`` visits vertices in a fixed order (highest degree first -
the most constrained classes are placed while there is still plenty of freedom).
For the current vertex it tries each colour in ascending order:

    1. is_safe?  no already-coloured neighbour has this colour (and the colour's
                 optional capacity - e.g. number of rooms - is not exhausted)
    2. assign it and recurse to the next vertex
    3. if the recursion fails, UNDO the assignment (a *backtrack*) and try the next colour

Pruning that keeps the search practical without changing its correctness:
    * highest-degree-first vertex order,
    * colour symmetry breaking - a vertex may only open the *next unused* colour,
      since colours are interchangeable (this cuts k! equivalent branches),
    * an optional step budget so a pathological input can never hang the server.

``color_with_min_slots`` minimises the number of slots: it computes a lower bound
(size of a greedily found clique, and ceil(V / capacity)), then tries k = lb, lb+1, ...
up to the number of slots available and stops at the first k that has a valid colouring.

Complexity
----------
Graph colouring is NP-complete; in the worst case the search explores O(k^V) states
(each of V vertices tries up to k colours).  Ordering and pruning make typical
timetables fast, but there is no polynomial-time guarantee.  Building the conflict
graph is O(sum over faculties/students of (classes per entity)^2).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, Hashable, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

Vertex = Hashable
Adjacency = Dict[Vertex, Set[Vertex]]
Edge = Tuple[Vertex, Vertex]

DEFAULT_MAX_STEPS = 200_000  # per attempted slot count


# --------------------------------------------------------------------------- #
# Conflict graph
# --------------------------------------------------------------------------- #
@dataclass
class ConflictGraph:
    vertices: List[Vertex]
    adjacency: Adjacency
    edge_reasons: Dict[Edge, List[str]] = field(default_factory=dict)

    def edges(self) -> List[Edge]:
        return sorted(self.edge_reasons)

    def degree(self, v: Vertex) -> int:
        return len(self.adjacency[v])


def _edge(a: Vertex, b: Vertex) -> Edge:
    return (a, b) if a <= b else (b, a)  # type: ignore[operator]


def build_conflict_graph(
    class_ids: Iterable[Vertex],
    faculty_of: Mapping[Vertex, Vertex],
    student_classes: Mapping[Vertex, Iterable[Vertex]],
    extra_conflicts: Iterable[Tuple[Vertex, Vertex, str]] = (),
) -> ConflictGraph:
    """Build the conflict graph.

    ``faculty_of``      class -> faculty id (same faculty => conflict)
    ``student_classes`` student -> classes the student is registered in (any two => conflict)
    ``extra_conflicts`` explicit (class_a, class_b, reason) shared-resource constraints
    """
    vertices = sorted(set(class_ids))  # type: ignore[type-var]
    vset = set(vertices)
    adjacency: Adjacency = {v: set() for v in vertices}
    reasons: Dict[Edge, List[str]] = {}

    def add(a: Vertex, b: Vertex, why: str) -> None:
        if a == b or a not in vset or b not in vset:
            return
        adjacency[a].add(b)
        adjacency[b].add(a)
        bucket = reasons.setdefault(_edge(a, b), [])
        if why not in bucket:
            bucket.append(why)

    by_faculty: Dict[Vertex, List[Vertex]] = {}
    for cid in vertices:
        if cid in faculty_of:
            by_faculty.setdefault(faculty_of[cid], []).append(cid)
    for fid, group in by_faculty.items():
        for a, b in combinations(group, 2):
            add(a, b, f"same faculty ({fid})")

    for sid, classes in student_classes.items():
        group = sorted({c for c in classes if c in vset})  # type: ignore[type-var]
        for a, b in combinations(group, 2):
            add(a, b, f"shared student ({sid})")

    for a, b, why in extra_conflicts:
        add(a, b, why or "configured constraint")

    return ConflictGraph(vertices, adjacency, reasons)


def find_conflicts(adjacency: Adjacency, assignment: Mapping[Vertex, int]) -> List[Edge]:
    """Edges whose two endpoints share a colour (empty list == valid colouring)."""
    bad: List[Edge] = []
    for v, nbrs in adjacency.items():
        for u in nbrs:
            if v < u and assignment.get(v) is not None and assignment.get(v) == assignment.get(u):  # type: ignore[operator]
                bad.append((v, u))
    return bad


def is_valid_coloring(adjacency: Adjacency, assignment: Mapping[Vertex, int]) -> bool:
    return set(assignment) >= set(adjacency) and not find_conflicts(adjacency, assignment)


# --------------------------------------------------------------------------- #
# Backtracking search
# --------------------------------------------------------------------------- #
class _StepLimitReached(Exception):
    pass


@dataclass
class ColoringAttempt:
    k: int
    status: str  # "OK" | "INFEASIBLE" | "LIMIT_REACHED"
    assignment: Dict[Vertex, int]
    nodes_visited: int
    backtracks: int

    @property
    def success(self) -> bool:
        return self.status == "OK"


@dataclass
class ColoringResult:
    status: str  # "OK" | "INFEASIBLE" | "LIMIT_REACHED"
    colors_used: int
    assignment: Dict[Vertex, int]
    attempts: List[ColoringAttempt]
    lower_bound: int
    vertex_order: List[Vertex]
    total_nodes: int
    total_backtracks: int
    message: str = ""

    @property
    def success(self) -> bool:
        return self.status == "OK"

    @property
    def proven_minimal(self) -> bool:
        """True when every smaller slot count was proven impossible (not merely out of budget)."""
        return self.success and all(a.status == "INFEASIBLE" for a in self.attempts[:-1])

    @property
    def backtracking_required(self) -> bool:
        """True when the search had to undo at least one assignment."""
        return self.total_backtracks > 0


def vertex_order(adjacency: Adjacency) -> List[Vertex]:
    """Highest degree first; ties by vertex id for determinism."""
    return sorted(adjacency, key=lambda v: (-len(adjacency[v]), v))  # type: ignore[type-var]


def backtracking_color(
    adjacency: Adjacency,
    k: int,
    *,
    color_capacity: Optional[int] = None,
    order: Optional[Sequence[Vertex]] = None,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> ColoringAttempt:
    """Try to colour the graph with at most ``k`` colours using backtracking.

    ``color_capacity`` limits how many vertices may share one colour (e.g. the number
    of rooms available in a single time slot).
    """
    order = list(order) if order is not None else vertex_order(adjacency)
    n = len(order)
    assignment: Dict[Vertex, int] = {}
    counts = [0] * max(k, 0)
    stats = {"nodes": 0, "backtracks": 0}

    def is_safe(v: Vertex, color: int) -> bool:
        if color_capacity is not None and counts[color] >= color_capacity:
            return False
        for u in adjacency[v]:
            if assignment.get(u) == color:
                return False
        return True

    def solve(i: int, used: int) -> bool:
        if i == n:
            return True
        v = order[i]
        # Symmetry breaking: only the already-used colours plus the next fresh one.
        for color in range(min(used + 1, k)):
            if not is_safe(v, color):
                continue
            assignment[v] = color
            counts[color] += 1
            stats["nodes"] += 1
            if stats["nodes"] > max_steps:
                raise _StepLimitReached
            if solve(i + 1, max(used, color + 1)):
                return True
            # BACKTRACK: undo and try the next colour
            del assignment[v]
            counts[color] -= 1
            stats["backtracks"] += 1
        return False

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, n + 200))
    try:
        ok = solve(0, 0)
        status = "OK" if ok else "INFEASIBLE"
    except _StepLimitReached:
        ok, status = False, "LIMIT_REACHED"
    finally:
        sys.setrecursionlimit(old_limit)

    return ColoringAttempt(k, status, dict(assignment) if ok else {}, stats["nodes"], stats["backtracks"])


def clique_lower_bound(adjacency: Adjacency) -> int:
    """Size of a greedily built clique - any proper colouring needs at least this many colours."""
    best = 0
    for start in vertex_order(adjacency):
        clique = [start]
        for v in vertex_order(adjacency):
            if v != start and all(v in adjacency[c] for c in clique):
                clique.append(v)
        best = max(best, len(clique))
    return best


def color_with_min_slots(
    adjacency: Adjacency,
    max_colors: int,
    *,
    color_capacity: Optional[int] = None,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> ColoringResult:
    """Find a valid colouring with the fewest colours (<= ``max_colors``).

    Tries k = lower_bound, lower_bound + 1, ... and returns on the first success.
    """
    order = vertex_order(adjacency)
    n = len(order)
    if n == 0:
        return ColoringResult("OK", 0, {}, [], 0, [], 0, 0, "Nothing to colour.")

    lower = clique_lower_bound(adjacency)
    if color_capacity is not None:
        if color_capacity < 1:
            return ColoringResult(
                "INFEASIBLE", 0, {}, [], lower, order, 0, 0, "No capacity available per time slot."
            )
        lower = max(lower, -(-n // color_capacity))  # ceil(n / capacity)
    lower = max(lower, 1)

    attempts: List[ColoringAttempt] = []
    if lower > max_colors:
        return ColoringResult(
            "INFEASIBLE", 0, {}, attempts, lower, order, 0, 0,
            f"At least {lower} time slots are required but only {max_colors} are available.",
        )

    for k in range(lower, max_colors + 1):
        attempt = backtracking_color(
            adjacency, k, color_capacity=color_capacity, order=order, max_steps=max_steps
        )
        attempts.append(attempt)
        # A budget-exhausted attempt means "unknown" (proving a small k impossible is the exponential
        # part of the problem), so we move on to k + 1 instead of giving up.
        if attempt.success:
            proven = all(a.status == "INFEASIBLE" for a in attempts[:-1])
            note = "" if proven else " (smaller slot counts were not proven impossible within the search budget)"
            return _result("OK", attempts, lower, order, f"Valid colouring found with {k} time slot(s){note}.", attempt)

    if any(a.status == "LIMIT_REACHED" for a in attempts):
        return _result("LIMIT_REACHED", attempts, lower, order, "Search budget exhausted before a colouring was found.")
    return _result(
        "INFEASIBLE", attempts, lower, order,
        f"No conflict-free assignment exists within {max_colors} time slot(s).",
    )


def _result(
    status: str,
    attempts: List[ColoringAttempt],
    lower: int,
    order: List[Vertex],
    message: str,
    winner: Optional[ColoringAttempt] = None,
) -> ColoringResult:
    return ColoringResult(
        status=status,
        colors_used=(winner.k if winner else 0),
        assignment=(winner.assignment if winner else {}),
        attempts=attempts,
        lower_bound=lower,
        vertex_order=order,
        total_nodes=sum(a.nodes_visited for a in attempts),
        total_backtracks=sum(a.backtracks for a in attempts),
        message=message,
    )


# --------------------------------------------------------------------------- #
# Slot assignment: the same backtracking search, generalised for real timetables
# --------------------------------------------------------------------------- #
# A "colour" is now a whole slot package (e.g. A1+TA1 = Mon 08:00, Wed 09:00, Fri 10:00) and two colours
# *clash* when any of their meeting periods overlap in time - they need not be identical. Each vertex also has
# its own domain (a 3-credit theory part may only take 3-credit theory packages, a lab part only lab packages),
# some vertices are pre-placed (fixed), and a room limit caps how many parts may meet in the same period.
#
#   hard edges  - must never overlap (same faculty, theory vs its own lab, mandatory-for-a-group pairs)
#   soft edges  - preferably do not overlap (optional subjects of one group: students want to combine them)
#
# Search = the same recursion as ``backtracking_color``: order vertices (highest degree first), try each slot in
# the domain best-first, check ``safe`` against already-placed neighbours, recurse, undo on failure.
# Worst case is still exponential, O(|domain|^V); ordering, pre-placement and a step budget keep it practical.
Interval = Tuple[int, int, int]  # (day index, start minute, end minute)


def intervals_overlap(a: Iterable[Interval], b: Iterable[Interval]) -> bool:
    for d1, s1, e1 in a:
        for d2, s2, e2 in b:
            if d1 == d2 and s1 < e2 and s2 < e1:
                return True
    return False


@dataclass
class SlotAssignmentResult:
    status: str  # "OK" | "INFEASIBLE" | "LIMIT_REACHED"
    assignment: Dict[Vertex, Hashable]
    nodes_visited: int
    backtracks: int
    order: List[Vertex]
    soft_overlaps: int
    message: str = ""

    @property
    def success(self) -> bool:
        return self.status == "OK"

    @property
    def backtracking_required(self) -> bool:
        return self.backtracks > 0


def backtracking_slot_assignment(
    vertices: Sequence[Vertex],
    domains: Mapping[Vertex, Sequence[Hashable]],
    hard: Mapping[Vertex, Set[Vertex]],
    intervals: Mapping[Hashable, Sequence[Interval]],
    *,
    fixed: Optional[Mapping[Vertex, Hashable]] = None,
    soft: Optional[Mapping[Vertex, Set[Vertex]]] = None,
    resource: Optional[Mapping[Vertex, str]] = None,
    resource_capacity: Optional[Mapping[str, int]] = None,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> SlotAssignmentResult:
    """Assign a slot to every free vertex so that no hard edge overlaps in time.

    ``vertices``  vertices still to be placed;  ``fixed`` already-placed vertices (kept as they are)
    ``domains``   candidate slots per vertex, best-first;  ``intervals`` slot -> meeting periods
    ``resource`` / ``resource_capacity``  e.g. vertex -> "LECTURE", {"LECTURE": 10}: at most that many
    vertices of the kind may meet in the identical period (the number of rooms).
    """
    fixed = dict(fixed or {})
    soft = soft or {}
    free = [v for v in vertices if v not in fixed]
    order = sorted(free, key=lambda v: (-len(hard.get(v, ())), len(domains.get(v, ())), v))  # type: ignore[type-var]
    assignment: Dict[Vertex, Hashable] = dict(fixed)
    load: Dict[Hashable, int] = {}
    usage: Dict[Tuple[str, Interval], int] = {}
    overlap_memo: Dict[Tuple[Hashable, Hashable], bool] = {}
    stats = {"nodes": 0, "backtracks": 0}

    def clash(a: Hashable, b: Hashable) -> bool:
        key = (a, b) if str(a) <= str(b) else (b, a)
        hit = overlap_memo.get(key)
        if hit is None:
            hit = overlap_memo[key] = intervals_overlap(intervals[a], intervals[b])
        return hit

    def occupy(v: Vertex, slot: Hashable, delta: int) -> None:
        load[slot] = load.get(slot, 0) + delta
        if resource and resource.get(v):
            for iv in intervals[slot]:
                k = (resource[v], iv)
                usage[k] = usage.get(k, 0) + delta

    for v, s in fixed.items():
        occupy(v, s, 1)

    def safe(v: Vertex, slot: Hashable) -> bool:
        for u in hard.get(v, ()):
            t = assignment.get(u)
            if t is not None and clash(slot, t):
                return False
        if resource and resource_capacity and resource.get(v):
            cap = resource_capacity.get(resource[v])
            if cap is not None:
                for iv in intervals[slot]:
                    if usage.get((resource[v], iv), 0) >= cap:
                        return False
        return True

    def penalty(v: Vertex, slot: Hashable) -> int:
        return sum(1 for u in soft.get(v, ()) if assignment.get(u) is not None and clash(slot, assignment[u]))

    def solve(i: int) -> bool:
        if i == len(order):
            return True
        v = order[i]
        ranked = sorted(
            enumerate(domains.get(v, ())), key=lambda p: (penalty(v, p[1]), load.get(p[1], 0), p[0])
        )
        for _, slot in ranked:
            if not safe(v, slot):
                continue
            assignment[v] = slot
            occupy(v, slot, 1)
            stats["nodes"] += 1
            if stats["nodes"] > max_steps:
                raise _StepLimitReached
            if solve(i + 1):
                return True
            del assignment[v]  # BACKTRACK
            occupy(v, slot, -1)
            stats["backtracks"] += 1
        return False

    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, len(order) + 200))
    try:
        ok = solve(0)
        status = "OK" if ok else "INFEASIBLE"
    except _StepLimitReached:
        ok, status = False, "LIMIT_REACHED"
    finally:
        sys.setrecursionlimit(old_limit)

    soft_overlaps = 0
    if ok:
        seen = set()
        for v, nbrs in soft.items():
            for u in nbrs:
                pair = (v, u) if str(v) <= str(u) else (u, v)
                if pair in seen or v not in assignment or u not in assignment:
                    continue
                seen.add(pair)
                if clash(assignment[v], assignment[u]):
                    soft_overlaps += 1
    message = {
        "OK": "Every class was placed without a clash.",
        "INFEASIBLE": "These classes cannot all be fitted in without a clash using the slots, rooms and hand-placed "
                      "classes available. Try adding rooms, moving a hand-placed class, or clearing the unlocked slots "
                      "and running the scheduler again.",
        "LIMIT_REACHED": "Working out a clash-free timetable is taking too long. Place a few classes by hand and run "
                         "the scheduler again.",
    }[status]
    return SlotAssignmentResult(
        status, dict(assignment) if ok else {}, stats["nodes"], stats["backtracks"], order, soft_overlaps, message
    )
