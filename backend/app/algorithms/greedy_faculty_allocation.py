"""PHASE 1 / ALGORITHM 2 - Greedy Faculty Allocation.

Problem
-------
A student needs a class (faculty) for a subject - typically because the class they
wanted is full or closed.  Several faculties teach the subject; which one should
the student be steered to?

Greedy rule (documented so it can be explained in a DAA evaluation)
------------------------------------------------------------------
1. Discard candidates that are *not available* (class not OPEN or no remaining seat).
2. Give every remaining candidate a **priority vector**, one component per criterion,
   in a configurable order (``GreedyConfig.criteria``).  Default order::

       (preferred, slot_compatible, remaining_capacity, short_queue)

   * ``preferred``          1 if it is the class/faculty the student explicitly chose
   * ``slot_compatible``    1 if the offering's slots do not overlap in time with any class the
                            student already holds (an overlapping offering is also never *available*)
   * ``remaining_capacity`` seats still free (more is better - ties on the earlier
                            criteria are broken toward the roomier class)
   * ``short_queue``        negative pending-queue length (shorter queue is better)
3. Pick the candidate with the lexicographically largest vector; remaining ties are
   broken by the smallest ``class_id`` so output is deterministic.

The *greedy property*: the decision is made once, from the current snapshot, taking
the locally best available option; earlier allocations are never reconsidered or
reshuffled.  An explicitly preferred class is never overridden while it is available
because ``preferred`` is the first criterion.

Complexity
----------
Selection is a single linear scan: O(F * C) for F candidate faculties and C criteria
(C is a small constant, so O(F)).  ``rank_candidates`` additionally sorts for display
purposes only: O(F log F).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Candidate:
    class_id: int
    faculty_id: int
    faculty_name: str = ""
    remaining_capacity: int = 0
    queue_length: int = 0
    is_open: bool = True
    slot_compatible: bool = True

    @property
    def available(self) -> bool:
        return self.is_open and self.remaining_capacity > 0


@dataclass(frozen=True)
class Preference:
    """What the student explicitly asked for (either may be None)."""

    class_id: Optional[int] = None
    faculty_id: Optional[int] = None


CriterionFn = Callable[[Candidate, Preference], int]

# Criterion registry - add a function here and list its name in the config to use it.
CRITERIA: Dict[str, CriterionFn] = {
    "preferred": lambda c, p: int(
        (p.class_id is not None and c.class_id == p.class_id)
        or (p.faculty_id is not None and c.faculty_id == p.faculty_id)
    ),
    "slot_compatible": lambda c, p: int(c.slot_compatible),
    "remaining_capacity": lambda c, p: c.remaining_capacity,
    "short_queue": lambda c, p: -c.queue_length,
}

DEFAULT_CRITERIA: Tuple[str, ...] = (
    "preferred",
    "slot_compatible",
    "remaining_capacity",
    "short_queue",
)


@dataclass(frozen=True)
class GreedyConfig:
    criteria: Tuple[str, ...] = DEFAULT_CRITERIA

    def __post_init__(self) -> None:
        unknown = [c for c in self.criteria if c not in CRITERIA]
        if unknown:
            raise ValueError(f"unknown greedy criteria: {unknown}")


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: Tuple[int, ...]
    available: bool


@dataclass
class AllocationResult:
    selected: Optional[Candidate]
    considered: List[ScoredCandidate] = field(default_factory=list)
    criteria: Tuple[str, ...] = DEFAULT_CRITERIA
    preferred_honoured: bool = False
    reason: str = ""


def score_candidate(
    candidate: Candidate, preference: Preference, config: GreedyConfig = GreedyConfig()
) -> Tuple[int, ...]:
    return tuple(CRITERIA[name](candidate, preference) for name in config.criteria)


def _better(a: ScoredCandidate, b: ScoredCandidate) -> bool:
    """True if ``a`` should replace the incumbent ``b`` (higher vector, then lower class_id)."""
    if a.score != b.score:
        return a.score > b.score
    return a.candidate.class_id < b.candidate.class_id


def select_best(
    candidates: Iterable[Candidate],
    preference: Preference = Preference(),
    config: GreedyConfig = GreedyConfig(),
) -> AllocationResult:
    """Greedy Faculty Allocation: one linear scan keeping the best available candidate."""
    best: Optional[ScoredCandidate] = None
    considered: List[ScoredCandidate] = []
    for cand in candidates:
        scored = ScoredCandidate(cand, score_candidate(cand, preference, config), cand.available)
        considered.append(scored)
        if scored.available and (best is None or _better(scored, best)):
            best = scored

    if best is None:
        return AllocationResult(
            None, considered, config.criteria, False, "No faculty/class currently has a free seat."
        )

    honoured = bool(CRITERIA["preferred"](best.candidate, preference))
    has_preference = preference.class_id is not None or preference.faculty_id is not None
    if honoured:
        reason = "The student's preferred class is available, so it was kept."
    elif has_preference:
        reason = (
            "The preferred class is unavailable; selected the best available alternative "
            f"by priority {' > '.join(config.criteria)}."
        )
    else:
        reason = f"Selected the best available class by priority {' > '.join(config.criteria)}."
    return AllocationResult(best.candidate, considered, config.criteria, honoured, reason)


def rank_candidates(
    candidates: Iterable[Candidate],
    preference: Preference = Preference(),
    config: GreedyConfig = GreedyConfig(),
) -> List[ScoredCandidate]:
    """Available candidates best-first (for display; the greedy choice is rank #1)."""
    scored = [
        ScoredCandidate(c, score_candidate(c, preference, config), c.available) for c in candidates
    ]
    scored.sort(key=lambda s: (not s.available, tuple(-x for x in s.score), s.candidate.class_id))
    return scored
