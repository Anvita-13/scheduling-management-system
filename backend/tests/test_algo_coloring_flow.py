import itertools

from app.algorithms.backtracking_graph_coloring import (
    backtracking_color,
    build_conflict_graph,
    color_with_min_slots,
    find_conflicts,
    is_valid_coloring,
)
from app.algorithms.edmonds_karp import FlowNetwork


# --------------------------- conflict graph ----------------------------- #
def test_conflict_graph_detects_faculty_student_and_extra_conflicts():
    g = build_conflict_graph(
        class_ids=[1, 2, 3, 4, 5],
        faculty_of={1: "A", 2: "A", 3: "B", 4: "C", 5: "D"},
        student_classes={"s1": [3, 4], "s2": [4]},
        extra_conflicts=[(1, 5, "shared lab")],
    )
    assert g.adjacency[1] == {2, 5}
    assert g.adjacency[3] == {4}
    assert g.adjacency[4] == {3}
    assert g.edge_reasons[(1, 2)] == ["same faculty (A)"]
    assert g.edge_reasons[(3, 4)] == ["shared student (s1)"]
    assert g.edge_reasons[(1, 5)] == ["shared lab"]
    assert g.edges() == [(1, 2), (1, 5), (3, 4)]


def test_conflict_graph_ignores_unknown_classes():
    g = build_conflict_graph([1, 2], {1: "A", 2: "B"}, {"s": [1, 2, 99]})
    assert g.adjacency == {1: {2}, 2: {1}}


# ------------------------------ colouring ------------------------------- #
def _adj(edges, n):
    adj = {v: set() for v in range(n)}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    return adj


def test_triangle_needs_three_colors():
    adj = _adj([(0, 1), (1, 2), (0, 2)], 3)
    assert not backtracking_color(adj, 2).success
    res = color_with_min_slots(adj, 5)
    assert res.success and res.colors_used == 3 and is_valid_coloring(adj, res.assignment)


def test_bipartite_cycle_uses_two_colors():
    adj = _adj([(0, 1), (1, 2), (2, 3), (3, 0)], 4)
    res = color_with_min_slots(adj, 4)
    assert res.colors_used == 2 and not find_conflicts(adj, res.assignment)


def test_odd_cycle_requires_backtracking_and_three_colors():
    # C5 with a chord-free structure: lower bound (clique) is 2 but chromatic number is 3,
    # so the k=2 attempt must fail after exploring/backtracking.
    adj = _adj([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)], 5)
    res = color_with_min_slots(adj, 4)
    assert res.success and res.colors_used == 3
    assert res.lower_bound == 2
    assert res.backtracking_required and res.total_backtracks > 0
    assert [a.k for a in res.attempts] == [2, 3]


def test_impossible_when_too_few_slots():
    k4 = _adj(list(itertools.combinations(range(4), 2)), 4)
    res = color_with_min_slots(k4, 3)
    assert res.status == "INFEASIBLE" and res.assignment == {}
    assert "4" in res.message


def test_impossible_even_though_clique_bound_passes():
    # Petersen graph has chromatic number 3; with 2 slots it must be infeasible (found by search).
    outer = [(i, (i + 1) % 5) for i in range(5)]
    spokes = [(i, i + 5) for i in range(5)]
    inner = [(5 + i, 5 + (i + 2) % 5) for i in range(5)]
    adj = _adj(outer + spokes + inner, 10)
    assert color_with_min_slots(adj, 2).status == "INFEASIBLE"
    assert color_with_min_slots(adj, 3).colors_used == 3


def test_empty_graph_and_isolated_vertices():
    assert color_with_min_slots({}, 3).success
    res = color_with_min_slots(_adj([], 4), 3)
    assert res.colors_used == 1


def test_color_capacity_models_limited_rooms():
    adj = _adj([], 6)  # no conflicts at all, but only 2 rooms per slot
    res = color_with_min_slots(adj, 10, color_capacity=2)
    assert res.success and res.colors_used == 3
    per_color = {}
    for color in res.assignment.values():
        per_color[color] = per_color.get(color, 0) + 1
    assert max(per_color.values()) <= 2


def test_step_budget_is_enforced():
    outer = [(i, (i + 1) % 5) for i in range(5)]
    spokes = [(i, i + 5) for i in range(5)]
    inner = [(5 + i, 5 + (i + 2) % 5) for i in range(5)]
    adj = _adj(outer + spokes + inner, 10)
    assert backtracking_color(adj, 2, max_steps=3).status == "LIMIT_REACHED"


def test_exhausted_budget_at_small_k_moves_on_instead_of_failing(monkeypatch):
    from app.algorithms import backtracking_graph_coloring as bgc

    real = bgc.backtracking_color

    def fake(adjacency, k, **kw):
        if k == 3:  # pretend proving k=3 impossible blew the budget
            return bgc.ColoringAttempt(3, "LIMIT_REACHED", {}, 999, 999)
        return real(adjacency, k, **kw)

    monkeypatch.setattr(bgc, "backtracking_color", fake)
    adj = _adj([(0, 1), (1, 2), (0, 2)], 3)  # triangle: lower bound 3
    res = bgc.color_with_min_slots(adj, 5)
    assert res.success and res.colors_used == 4  # skipped k=3, found k=4
    assert not res.proven_minimal and "not proven" in res.message
    # a normal run is proven minimal
    monkeypatch.setattr(bgc, "backtracking_color", real)
    assert bgc.color_with_min_slots(adj, 5).proven_minimal


def test_coloring_is_deterministic():
    adj = _adj([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0), (0, 2)], 5)
    assert color_with_min_slots(adj, 5).assignment == color_with_min_slots(adj, 5).assignment


# ---------------------------- Edmonds-Karp ------------------------------ #
def test_clrs_textbook_network_has_max_flow_23():
    net = FlowNetwork()
    for u, v, c in [
        ("s", "v1", 16), ("s", "v2", 13), ("v1", "v3", 12), ("v2", "v1", 4),
        ("v2", "v4", 14), ("v3", "v2", 9), ("v3", "t", 20), ("v4", "v3", 7), ("v4", "t", 4),
    ]:
        net.add_edge(u, v, c)
    res = net.max_flow("s", "t")
    assert res.max_flow == 23
    assert sum(c for _, _, c in res.min_cut_edges) == 23  # max-flow == min-cut


def test_flow_conservation_and_capacity_respected():
    net = FlowNetwork()
    for u, v, c in [("s", "a", 3), ("s", "b", 2), ("a", "b", 1), ("a", "t", 2), ("b", "t", 3)]:
        net.add_edge(u, v, c)
    res = net.max_flow("s", "t")
    assert res.max_flow == 5
    balance = {}
    for u, v, cap, flow in res.edge_flows:
        assert 0 <= flow <= cap
        balance[u] = balance.get(u, 0) - flow
        balance[v] = balance.get(v, 0) + flow
    assert balance["s"] == -5 and balance["t"] == 5 and balance["a"] == 0 and balance["b"] == 0


def test_reverse_edges_allow_rerouting():
    # Classic case where a greedy first path blocks the optimum: the flow must be rerouted
    # through a reverse (residual) edge to reach 2.
    net = FlowNetwork()
    for u, v in [("s", "a"), ("s", "b"), ("a", "c"), ("a", "d"), ("b", "c"), ("c", "t"), ("d", "t")]:
        net.add_edge(u, v, 1)
    assert net.max_flow("s", "t").max_flow == 2


def test_disconnected_sink_gives_zero_flow():
    net = FlowNetwork()
    net.add_edge("s", "a", 5)
    net.add_node("t")
    assert net.max_flow("s", "t").max_flow == 0


def test_bfs_picks_shortest_augmenting_path_first():
    net = FlowNetwork()
    net.add_edge("s", "a", 1)
    net.add_edge("a", "b", 1)
    net.add_edge("b", "t", 1)
    net.add_edge("s", "t", 1)
    res = net.max_flow("s", "t")
    assert res.max_flow == 2
    assert res.augmenting_paths[0].nodes == ["s", "t"]  # fewest edges first


def test_student_class_allocation_network():
    # 3 students want subject X; classes have 1 and 1 seat => only 2 accommodated.
    net = FlowNetwork()
    for s in ("s1", "s2", "s3"):
        net.add_edge("S", s, 1)
        net.add_edge(s, "c1", 1)
        net.add_edge(s, "c2", 1)
    net.add_edge("c1", "T", 1)
    net.add_edge("c2", "T", 1)
    res = net.max_flow("S", "T")
    assert res.max_flow == 2
    assert {u for u, _, _ in res.min_cut_edges} == {"c1", "c2"}  # the bottleneck classes
