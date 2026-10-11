import pytest

from app.algorithms.fifo_queue import FifoQueue, QueueEmptyError, serve_from_front
from app.algorithms.greedy_faculty_allocation import (
    Candidate,
    GreedyConfig,
    Preference,
    rank_candidates,
    select_best,
)


# ------------------------------- FIFO ---------------------------------- #
def test_fifo_dequeues_in_exact_arrival_order():
    q = FifoQueue()
    for i in [5, 1, 9, 3]:
        q.enqueue(i)
    assert [q.dequeue() for _ in range(4)] == [5, 1, 9, 3]  # never sorted


def test_fifo_peek_does_not_remove_and_len_tracks():
    q = FifoQueue(["a", "b"])
    assert q.peek() == "a" and len(q) == 2
    q.dequeue()
    assert q.peek() == "b" and len(q) == 1


def test_fifo_empty_raises():
    q = FifoQueue()
    with pytest.raises(QueueEmptyError):
        q.dequeue()
    with pytest.raises(QueueEmptyError):
        q.peek()


def test_serve_from_front_is_pure_and_ordered():
    q = FifoQueue([10, 20, 30, 40])
    res = serve_from_front(q, 2)
    assert res.served == (10, 20) and res.remaining == (30, 40)
    assert q.to_list() == [10, 20, 30, 40]  # original untouched
    assert serve_from_front(q, 99).remaining == ()


# ------------------------------ Greedy --------------------------------- #
def cand(cid, fid, remaining, queue=0, open_=True, compat=True):
    return Candidate(cid, fid, f"F{fid}", remaining, queue, open_, compat)


def test_greedy_keeps_available_preferred_class_even_if_not_roomiest():
    cs = [cand(1, 10, 2), cand(2, 20, 30)]
    res = select_best(cs, Preference(class_id=1))
    assert res.selected.class_id == 1 and res.preferred_honoured


def test_greedy_honours_preferred_faculty():
    cs = [cand(1, 10, 2), cand(2, 20, 30)]
    assert select_best(cs, Preference(faculty_id=10)).selected.class_id == 1


def test_greedy_falls_back_to_most_remaining_capacity_when_preferred_full():
    cs = [cand(1, 10, 0), cand(2, 20, 3), cand(3, 30, 9), cand(4, 40, 5)]
    res = select_best(cs, Preference(class_id=1))
    assert res.selected.class_id == 3 and not res.preferred_honoured


def test_greedy_skips_closed_and_full():
    cs = [cand(1, 10, 5, open_=False), cand(2, 20, 0), cand(3, 30, 1)]
    assert select_best(cs).selected.class_id == 3


def test_greedy_none_when_nothing_available():
    res = select_best([cand(1, 10, 0), cand(2, 20, 4, open_=False)])
    assert res.selected is None and len(res.considered) == 2


def test_greedy_slot_compatibility_outranks_capacity():
    cs = [cand(1, 10, 20, compat=False), cand(2, 20, 2, compat=True)]
    assert select_best(cs).selected.class_id == 2


def test_greedy_tie_breaks_on_shorter_queue_then_lowest_id():
    cs = [cand(7, 1, 5, queue=3), cand(6, 2, 5, queue=1), cand(5, 3, 5, queue=1)]
    assert select_best(cs).selected.class_id == 5
    assert select_best(list(reversed(cs))).selected.class_id == 5  # deterministic


def test_greedy_config_is_configurable():
    cs = [cand(1, 10, 9, queue=8), cand(2, 20, 4, queue=0)]
    default = select_best(cs).selected.class_id
    queue_first = select_best(cs, config=GreedyConfig(("short_queue", "remaining_capacity"))).selected.class_id
    assert (default, queue_first) == (1, 2)
    with pytest.raises(ValueError):
        GreedyConfig(("bogus",))


def test_rank_candidates_puts_best_first_and_unavailable_last():
    cs = [cand(1, 10, 0), cand(2, 20, 3), cand(3, 30, 9)]
    ranked = rank_candidates(cs)
    assert [r.candidate.class_id for r in ranked] == [3, 2, 1]
    assert ranked[-1].available is False
