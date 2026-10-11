from app.algorithms.backtracking_graph_coloring import backtracking_slot_assignment, intervals_overlap

# day 0, minutes from midnight
MON9 = [(0, 540, 590)]
MON10 = [(0, 600, 650)]
MON9_LONG = [(0, 540, 640)]  # overlaps both MON9 and MON10
TUE9 = [(1, 540, 590)]
SLOTS = {"A": MON9, "B": MON10, "C": MON9_LONG, "D": TUE9}


def test_interval_overlap_is_by_time_not_identity():
    assert intervals_overlap(MON9, MON9_LONG) and intervals_overlap(MON10, MON9_LONG)
    assert not intervals_overlap(MON9, MON10)  # adjacent, no overlap
    assert not intervals_overlap(MON9, TUE9)  # different day


def test_hard_edge_pairs_get_non_overlapping_slots():
    res = backtracking_slot_assignment([1, 2], {1: ["A", "B"], 2: ["A", "B"]}, {1: {2}, 2: {1}}, SLOTS)
    assert res.success and res.assignment[1] != res.assignment[2]
    # A and C overlap each other, so with only those two choices the pair cannot be placed at all
    bad = backtracking_slot_assignment([1, 2], {1: ["A", "C"], 2: ["A", "C"]}, {1: {2}, 2: {1}}, SLOTS)
    assert bad.status == "INFEASIBLE"


def test_overlapping_packages_clash_even_if_different():
    # vertex 1 is fixed in the long slot; vertex 2 cannot take A or B (both overlap it), only D
    res = backtracking_slot_assignment(
        [1, 2], {2: ["A", "B", "D"]}, {1: {2}, 2: {1}}, SLOTS, fixed={1: "C"}
    )
    assert res.success and res.assignment[2] == "D" and res.assignment[1] == "C"


def test_fixed_vertices_are_kept_and_domains_respected():
    res = backtracking_slot_assignment([1, 2, 3], {2: ["A", "B"], 3: ["D"]}, {}, SLOTS, fixed={1: "A"})
    assert res.assignment[1] == "A" and res.assignment[3] == "D" and res.assignment[2] in ("A", "B")


def test_impossible_when_domain_exhausted():
    res = backtracking_slot_assignment(
        [1, 2, 3], {v: ["A", "B"] for v in (1, 2, 3)}, {1: {2, 3}, 2: {1, 3}, 3: {1, 2}}, SLOTS
    )
    assert res.status == "INFEASIBLE" and res.assignment == {}


def test_backtracking_is_needed_and_succeeds():
    # 1 prefers A (first in domain) but 2 and 3 then cannot both fit -> must undo
    hard = {1: {2, 3}, 2: {1}, 3: {1}}
    domains = {1: ["A", "B"], 2: ["A"], 3: ["B", "D"]}
    # 2 must take A, so 1 cannot be A -> forced to B; 3 then must avoid B -> D
    res = backtracking_slot_assignment([1, 2, 3], domains, hard, SLOTS)
    assert res.success and res.assignment == {1: "B", 2: "A", 3: "D"}


def test_resource_capacity_limits_parallel_classes():
    # only one "room": two unrelated classes may not share the identical period
    res = backtracking_slot_assignment(
        [1, 2], {1: ["A", "D"], 2: ["A", "D"]}, {}, SLOTS,
        resource={1: "LECTURE", 2: "LECTURE"}, resource_capacity={"LECTURE": 1},
    )
    assert res.success and res.assignment[1] != res.assignment[2]
    two = backtracking_slot_assignment(
        [1, 2], {1: ["A"], 2: ["A"]}, {}, SLOTS,
        resource={1: "LECTURE", 2: "LECTURE"}, resource_capacity={"LECTURE": 1},
    )
    assert two.status == "INFEASIBLE"


def test_soft_edges_are_avoided_when_possible_and_counted_when_not():
    soft = {1: {2}, 2: {1}}
    res = backtracking_slot_assignment([1, 2], {1: ["A"], 2: ["A", "D"]}, {}, SLOTS, soft=soft)
    assert res.assignment[2] == "D" and res.soft_overlaps == 0  # preferred non-overlapping option
    forced = backtracking_slot_assignment([1, 2], {1: ["A"], 2: ["A"]}, {}, SLOTS, soft=soft)
    assert forced.success and forced.soft_overlaps == 1  # allowed, but reported


def test_deterministic_and_step_budget():
    kw = dict(hard={1: {2}, 2: {1}}, intervals=SLOTS)
    a = backtracking_slot_assignment([1, 2], {1: ["A", "B", "D"], 2: ["A", "B", "D"]}, **kw)
    b = backtracking_slot_assignment([1, 2], {1: ["A", "B", "D"], 2: ["A", "B", "D"]}, **kw)
    assert a.assignment == b.assignment
    limited = backtracking_slot_assignment(
        [1, 2, 3], {v: ["A", "B"] for v in (1, 2, 3)}, {1: {2, 3}, 2: {1, 3}, 3: {1, 2}}, SLOTS, max_steps=1
    )
    assert limited.status == "LIMIT_REACHED"
