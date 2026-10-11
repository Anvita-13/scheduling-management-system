"""PHASE 1 / ALGORITHM 1 - FIFO queue for student join requests.

Every class section owns one queue of pending join requests.  A request is
*enqueued at the rear* when a student submits it and is *dequeued from the front*
when the faculty member accepts (or rejects) the next student.  Nothing in this
module ever sorts or reorders items, so processing order is exactly arrival order.

Complexity
----------
* ``enqueue``  - O(1)   (``collections.deque.append``)
* ``dequeue``  - O(1)   (``collections.deque.popleft``)
* ``peek``     - O(1)
* hydrating a queue from n stored requests - O(n)

Persistence
-----------
The queue itself is an in-memory structure.  The *database* is the durable source
of truth: each stored request carries a per-class, strictly increasing
``queue_seq`` assigned under a row lock at enqueue time.  The service layer
re-hydrates the queue from rows ordered by ``queue_seq`` so ordering survives
restarts and multiple worker processes (see ``registration_service``).
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Generic, Iterable, Iterator, List, Tuple, TypeVar

T = TypeVar("T")


class QueueEmptyError(Exception):
    """Raised when dequeue/peek is attempted on an empty queue."""


class FifoQueue(Generic[T]):
    """A strict first-in-first-out queue."""

    __slots__ = ("_items",)

    def __init__(self, items: Iterable[T] = ()) -> None:
        # Items are taken in the order supplied; callers hydrating from the DB
        # supply them already ordered by ``queue_seq``.
        self._items: Deque[T] = deque(items)

    # -- core operations ------------------------------------------------- #
    def enqueue(self, item: T) -> None:
        """Insert at the rear. O(1)."""
        self._items.append(item)

    def dequeue(self) -> T:
        """Remove and return the front item. O(1)."""
        if not self._items:
            raise QueueEmptyError("dequeue from an empty queue")
        return self._items.popleft()

    def peek(self) -> T:
        """Return (without removing) the front item. O(1)."""
        if not self._items:
            raise QueueEmptyError("peek at an empty queue")
        return self._items[0]

    # -- helpers --------------------------------------------------------- #
    def is_empty(self) -> bool:
        return not self._items

    def to_list(self) -> List[T]:
        """Snapshot front -> rear (does not mutate the queue)."""
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[T]:
        return iter(self._items)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"FifoQueue({list(self._items)!r})"


@dataclass(frozen=True)
class QueueProcessingResult(Generic[T]):
    served: Tuple[T, ...]
    remaining: Tuple[T, ...]


def serve_from_front(queue: FifoQueue[T], seats: int) -> QueueProcessingResult[T]:
    """Dequeue up to ``seats`` items from the front, preserving arrival order.

    Pure helper used by the Admin insights page to show queue state before and
    after processing; it works on a copy so the original queue is untouched.
    O(min(seats, n)) dequeues + O(n) copy.
    """
    work = FifoQueue(queue.to_list())
    served: List[T] = []
    while seats > 0 and not work.is_empty():
        served.append(work.dequeue())
        seats -= 1
    return QueueProcessingResult(tuple(served), tuple(work.to_list()))
