"""The stateless game graph for DETACHED HEAD.

Every node is one quantised game state (see docs/DESIGN.md): normal nodes are
(cell, angle, has-key), arena nodes are (cell, angle, boss-hp). Edges are the
five player moves. Walls are missing edges. Unreachable states are pruned so
the emitted repository contains exactly the playable graph.
"""

from __future__ import annotations

from collections import deque

from .level import DIRS, LEFT, RIGHT, Level

MOVES = ("F", "B", "L", "R", "X")
WIN = "WIN"
ARENA_HP = (4, 3, 2, 1)


def normal_id(cx: int, cy: int, ang: str, key: bool) -> str:
    return f"x{cx:02d}y{cy:02d}{ang}" + ("k" if key else "")


def arena_id(cx: int, cy: int, ang: str, hp: int) -> str:
    return f"x{cx:02d}y{cy:02d}{ang}h{hp}"


def _step_target(lvl: Level, cx: int, cy: int, ang: str, key: bool, forward: bool):
    """Where does a forward/backward step from a normal state lead, or None."""
    dx, dy = DIRS[ang]
    if not forward:
        dx, dy = -dx, -dy
    tx, ty = cx + dx, cy + dy
    if not lvl.passable(tx, ty, key):
        return None
    if lvl.is_arena(tx, ty):
        return ("arena", tx, ty, ang, ARENA_HP[0])
    new_key = key or (tx, ty) == lvl.key
    return ("normal", tx, ty, ang, new_key)


def build_graph(lvl: Level) -> dict:
    start = normal_id(*lvl.spawn, "N", False)
    nodes: dict[str, dict] = {}
    seen: set[str] = set()
    queue: deque[str] = deque([start])

    def add_normal(cx: int, cy: int, ang: str, key: bool) -> str:
        nid = normal_id(cx, cy, ang, key)
        if nid not in nodes:
            nodes[nid] = {
                "cell": [cx, cy],
                "angle": ang,
                "zone": lvl.zone(cx, cy),
                "kind": "normal",
                "key": int(key),
                "hp": None,
                "moves": {},
            }
        return nid

    def add_arena(cx: int, cy: int, ang: str, hp: int) -> str:
        nid = arena_id(cx, cy, ang, hp)
        if nid not in nodes:
            nodes[nid] = {
                "cell": [cx, cy],
                "angle": ang,
                "zone": lvl.zone(cx, cy),
                "kind": "arena",
                "key": 1,
                "hp": hp,
                "moves": {},
            }
        return nid

    add_normal(*lvl.spawn, "N", False)
    while queue:
        nid = queue.popleft()
        if nid in seen:
            continue
        seen.add(nid)
        node = nodes[nid]
        cx, cy = node["cell"]
        ang = node["angle"]
        if node["kind"] == "win":
            continue

        if node["kind"] == "normal":
            key = bool(node["key"])
            moves = {}
            for token, forward in (("F", True), ("B", False)):
                t = _step_target(lvl, cx, cy, ang, key, forward)
                if t is None:
                    moves[token] = None
                elif t[0] == "arena":
                    moves[token] = add_arena(t[1], t[2], t[3], t[4])
                else:
                    moves[token] = add_normal(t[1], t[2], t[3], t[4])
            moves["L"] = add_normal(cx, cy, LEFT[ang], key)
            moves["R"] = add_normal(cx, cy, RIGHT[ang], key)
            moves["X"] = nid  # a dry fire outside the arena changes nothing
            node["moves"] = moves
        else:  # arena
            hp = node["hp"]
            moves = {}
            for token, forward in (("F", True), ("B", False)):
                dx, dy = DIRS[ang]
                if not forward:
                    dx, dy = -dx, -dy
                tx, ty = cx + dx, cy + dy
                if lvl.is_arena(tx, ty):
                    moves[token] = add_arena(tx, ty, ang, hp)
                elif lvl.passable(tx, ty, True):
                    moves[token] = add_normal(tx, ty, ang, True)
                else:
                    moves[token] = None
            moves["L"] = add_arena(cx, cy, LEFT[ang], hp)
            moves["R"] = add_arena(cx, cy, RIGHT[ang], hp)
            moves["X"] = arena_id(cx, cy, ang, hp - 1) if hp > 1 else WIN
            if hp > 1:
                add_arena(cx, cy, ang, hp - 1)
            node["moves"] = moves

        for target in node["moves"].values():
            if target and target != WIN and target not in seen:
                queue.append(target)

    nodes[WIN] = {"cell": None, "angle": None, "zone": "win", "kind": "win", "key": None, "hp": None, "moves": {}}
    return {
        "meta": {
            "name": "DETACHED HEAD",
            "level": "repo-01",
            "moves": list(MOVES),
        },
        "start": start,
        "win": WIN,
        "nodes": nodes,
    }


def validate(graph: dict, lvl: Level) -> list[str]:
    """Graph invariants; returns a list of human-readable violations."""
    errors = []
    nodes = graph["nodes"]

    for nid, node in nodes.items():
        for token, target in node["moves"].items():
            if token not in MOVES:
                errors.append(f"{nid}: unknown move token {token!r}")
            if target is not None and target not in nodes:
                errors.append(f"{nid}: move {token} points at missing node {target!r}")

    # WIN must be reachable from start (BFS over the move graph)
    seen = {graph["start"]}
    q = deque([graph["start"]])
    while q:
        nid = q.popleft()
        for target in nodes[nid]["moves"].values():
            if target and target not in seen:
                seen.add(target)
                q.append(target)
    unreachable = [nid for nid in nodes if nid not in seen]
    if unreachable:
        errors.append(f"{len(unreachable)} unreachable nodes, e.g. {sorted(unreachable)[:3]}")
    if WIN not in seen:
        errors.append("WIN is not reachable from start")

    # gate semantics: no keyless node sits on the gate cell
    gx, gy = lvl.gate
    for nid, node in nodes.items():
        if node["kind"] == "normal" and not node["key"] and node["cell"] == [gx, gy]:
            errors.append(f"{nid}: keyless node on the gate cell")
    return errors
