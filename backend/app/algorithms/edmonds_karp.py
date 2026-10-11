"""PHASE 1 / ALGORITHM 4 - Edmonds-Karp maximum flow.

Edmonds-Karp is Ford-Fulkerson where every augmenting path is found with
**breadth-first search**, i.e. always the *shortest* augmenting path (fewest edges).

Network representation
----------------------
Every edge is stored together with its reverse edge at the next index
(``edge ^ 1``).  The reverse edge starts with capacity 0 and gains residual
capacity as flow is pushed forward, which lets later augmentations *cancel* earlier
decisions.  Residual capacity of edge e = ``cap[e] - flow[e]``; pushing ``d`` along e
does ``flow[e] += d`` and ``flow[e ^ 1] -= d``.

Application in this system
--------------------------
source -> (student, subject) demand  [cap 1]
       -> class sections of that subject [cap 1]
       -> sink [cap = free seats]
The max-flow value is the largest number of students that *could* be seated
simultaneously.  It is a planning tool for Admin; actual acceptance stays FCFS.

Complexity
----------
Each BFS is O(E); at most O(V*E) augmentations occur, so the total is O(V * E^2).
(For this unit-capacity bipartite-style network the practical cost is far lower.)
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Hashable, List, Optional, Set, Tuple

Node = Hashable


@dataclass
class AugmentingPath:
    nodes: List[Node]
    bottleneck: int


@dataclass
class FlowResult:
    max_flow: int
    augmenting_paths: List[AugmentingPath]
    # forward edges only: (u, v, capacity, flow)
    edge_flows: List[Tuple[Node, Node, int, int]]
    # nodes reachable from the source in the final residual graph (source side of a min cut)
    source_side: Set[Node]
    # saturated forward edges crossing the min cut: (u, v, capacity)
    min_cut_edges: List[Tuple[Node, Node, int]] = field(default_factory=list)


class FlowNetwork:
    def __init__(self) -> None:
        self._index: Dict[Node, int] = {}
        self._nodes: List[Node] = []
        self._adj: List[List[int]] = []  # node index -> outgoing edge ids (insertion order)
        self._to: List[int] = []
        self._cap: List[int] = []
        self._flow: List[int] = []

    # -- construction ---------------------------------------------------- #
    def add_node(self, node: Node) -> int:
        if node not in self._index:
            self._index[node] = len(self._nodes)
            self._nodes.append(node)
            self._adj.append([])
        return self._index[node]

    def add_edge(self, u: Node, v: Node, capacity: int) -> int:
        """Add u->v with ``capacity`` plus its zero-capacity reverse edge. Returns forward edge id."""
        if capacity < 0:
            raise ValueError("capacity must be non-negative")
        ui, vi = self.add_node(u), self.add_node(v)
        eid = len(self._to)
        self._to.extend([vi, ui])
        self._cap.extend([capacity, 0])
        self._flow.extend([0, 0])
        self._adj[ui].append(eid)
        self._adj[vi].append(eid + 1)
        return eid

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._to) // 2

    def flow_on(self, edge_id: int) -> int:
        return self._flow[edge_id]

    # -- algorithm ------------------------------------------------------- #
    def _residual(self, e: int) -> int:
        return self._cap[e] - self._flow[e]

    def _bfs(self, s: int, t: int) -> Optional[List[int]]:
        """Shortest augmenting path as a list of edge ids, or None if t is unreachable."""
        parent_edge: List[int] = [-1] * len(self._nodes)
        seen = [False] * len(self._nodes)
        seen[s] = True
        q = deque([s])
        while q:
            u = q.popleft()
            for e in self._adj[u]:
                v = self._to[e]
                if not seen[v] and self._residual(e) > 0:
                    seen[v] = True
                    parent_edge[v] = e
                    if v == t:
                        path: List[int] = []
                        cur = t
                        while cur != s:
                            pe = parent_edge[cur]
                            path.append(pe)
                            cur = self._to[pe ^ 1]
                        path.reverse()
                        return path
                    q.append(v)
        return None

    def max_flow(self, source: Node, sink: Node) -> FlowResult:
        if source not in self._index or sink not in self._index:
            raise ValueError("source and sink must be nodes of the network")
        if source == sink:
            raise ValueError("source and sink must differ")
        s, t = self._index[source], self._index[sink]
        paths: List[AugmentingPath] = []
        total = 0

        while True:
            path = self._bfs(s, t)  # BFS for EVERY augmenting path
            if path is None:
                break
            bottleneck = min(self._residual(e) for e in path)
            for e in path:
                self._flow[e] += bottleneck
                self._flow[e ^ 1] -= bottleneck  # residual capacity of the reverse edge grows
            total += bottleneck
            nodes = [self._nodes[s]] + [self._nodes[self._to[e]] for e in path]
            paths.append(AugmentingPath(nodes, bottleneck))

        reachable = self._reachable(s)
        edge_flows = []
        cut = []
        for e in range(0, len(self._to), 2):
            u, v = self._to[e ^ 1], self._to[e]
            edge_flows.append((self._nodes[u], self._nodes[v], self._cap[e], self._flow[e]))
            if u in reachable and v not in reachable and self._cap[e] > 0:
                cut.append((self._nodes[u], self._nodes[v], self._cap[e]))
        return FlowResult(
            total, paths, edge_flows, {self._nodes[i] for i in reachable}, cut
        )

    def _reachable(self, s: int) -> Set[int]:
        seen = {s}
        q = deque([s])
        while q:
            u = q.popleft()
            for e in self._adj[u]:
                v = self._to[e]
                if v not in seen and self._residual(e) > 0:
                    seen.add(v)
                    q.append(v)
        return seen
