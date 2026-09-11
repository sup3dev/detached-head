"""The stateless game graph for DETACHED HEAD.

Every node is one quantised game state (see docs/DESIGN.md):

- normal nodes: (cell, angle, has-key)
- arena nodes:  (cell, angle, boss-hp)   -- THE DEBT, hp 4..1
- shrine nodes: (cell, angle, warden-hp, has-key) -- wardens, hp 2..0

Edges are the five player moves. Walls are missing edges. State that would
multiply the whole graph (boss HP, warden HP) lives only inside its confined
sub-graph; leaving resets it (the debt regrows, the wardens return).
Unreachable states are pruned so the emitted repo is exactly the playable
graph.
"""

from __future__ import annotations

from collections import deque

from .level import DIRS, LEFT, RIGHT, Level

MOVES = ("F", "B", "L", "R", "X")
WIN = "WIN"
ARENA_HP = (4, 3, 2, 1)
SHRINE_HP = (2, 1, 0)


def normal_id(cx: int, cy: int, ang: str, key: bool) -> str:
    return f"x{cx:02d}y{cy:02d}{ang}" + ("k" if key else "")


def arena_id(cx: int, cy: int, ang: str, hp: int) -> str:
    return f"x{cx:02d}y{cy:02d}{ang}h{hp}"


def shrine_id(cx: int, cy: int, ang: str, hp: int, key: bool) -> str:
    return f"x{cx:02d}y{cy:02d}{ang}w{hp}" + ("k" if key else "")


def build_graph(lvl: Level) -> dict:
    start = normal_id(*lvl.spawn, "N", False)
    nodes: dict[str, dict] = {}
    seen: set[str] = set()
    queue: deque[str] = deque([start])

    def add(nid: str, node: dict) -> str:
        if nid not in nodes:
            nodes[nid] = node
        return nid

    def add_normal(cx: int, cy: int, ang: str, key: bool) -> str:
        return add(normal_id(cx, cy, ang, key), {
            "cell": [cx, cy], "angle": ang, "zone": lvl.zone(cx, cy),
            "kind": "normal", "key": int(key), "hp": None, "moves": {},
        })

    def add_arena(cx: int, cy: int, ang: str, hp: int) -> str:
        return add(arena_id(cx, cy, ang, hp), {
            "cell": [cx, cy], "angle": ang, "zone": lvl.zone(cx, cy),
            "kind": "arena", "key": 1, "hp": hp, "moves": {},
        })

    def add_shrine(cx: int, cy: int, ang: str, hp: int, key: bool) -> str:
        return add(shrine_id(cx, cy, ang, hp, key), {
            "cell": [cx, cy], "angle": ang, "zone": lvl.zone(cx, cy),
            "kind": "shrine", "key": int(key), "hp": hp, "moves": {},
        })

    def normal_step(cx: int, cy: int, ang: str, key: bool, forward: bool):
        """Step target from a normal node, or None. Entering shrine floor
        spawns its warden at full health (the shrine keeps your key)."""
        dx, dy = DIRS[ang]
        if not forward:
            dx, dy = -dx, -dy
        tx, ty = cx + dx, cy + dy
        c = lvl.char(tx, ty)
        if c == "q":
            return ("shrine", tx, ty, ang, SHRINE_HP[0], key)
        if c in "KT" or not lvl.passable(tx, ty, key):
            return None
        if lvl.is_arena(tx, ty):
            return ("arena", tx, ty, ang, ARENA_HP[0])
        new_key = key or (tx, ty) == lvl.key
        return ("normal", tx, ty, ang, new_key)

    add_normal(*lvl.spawn, "N", False)
    while queue:
        nid = queue.popleft()
        if nid in seen:
            continue
        seen.add(nid)
        node = nodes[nid]
        cx, cy = node["cell"]
        ang = node["angle"]

        moves: dict[str, str | None] = {}

        if node["kind"] == "normal":
            key = bool(node["key"])
            for token, forward in (("F", True), ("B", False)):
                t = normal_step(cx, cy, ang, key, forward)
                if t is None:
                    moves[token] = None
                elif t[0] == "arena":
                    moves[token] = add_arena(t[1], t[2], t[3], t[4])
                elif t[0] == "shrine":
                    moves[token] = add_shrine(t[1], t[2], t[3], t[4], t[5])
                else:
                    moves[token] = add_normal(t[1], t[2], t[3], t[4])
            moves["L"] = add_normal(cx, cy, LEFT[ang], key)
            moves["R"] = add_normal(cx, cy, RIGHT[ang], key)
            moves["X"] = nid  # dry fire

        elif node["kind"] == "arena":
            hp = node["hp"]
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

        elif node["kind"] == "shrine":
            hp = node["hp"]
            key = bool(node["key"])
            shrine = lvl.shrine_at(cx, cy)
            for token, forward in (("F", True), ("B", False)):
                dx, dy = DIRS[ang]
                if not forward:
                    dx, dy = -dx, -dy
                tx, ty = cx + dx, cy + dy
                c = lvl.char(tx, ty)
                if (tx, ty) in shrine.cells:
                    if c in "KT" and hp > 0:
                        moves[token] = None  # the warden guards it
                    elif c == "K":
                        # the pickup: take the key, back to the normal world
                        moves[token] = add_normal(tx, ty, ang, True)
                    elif c == "T":
                        moves[token] = add_shrine(tx, ty, ang, hp, key)  # stand by the trophy
                    else:
                        moves[token] = add_shrine(tx, ty, ang, hp, key)
                elif lvl.passable(tx, ty, key):
                    moves[token] = add_normal(tx, ty, ang, key)  # leave, key kept
                else:
                    moves[token] = None
            moves["L"] = add_shrine(cx, cy, LEFT[ang], hp, key)
            moves["R"] = add_shrine(cx, cy, RIGHT[ang], hp, key)
            if hp > 0:
                moves["X"] = shrine_id(cx, cy, ang, hp - 1, key)
                add_shrine(cx, cy, ang, hp - 1, key)
            else:
                moves["X"] = nid  # nothing left to shoot at

        node["moves"] = moves
        for target in moves.values():
            if target and target != WIN and target not in seen:
                queue.append(target)

    nodes[WIN] = {"cell": None, "angle": None, "zone": "win", "kind": "win", "key": None, "hp": None, "moves": {}}
    return {
        "meta": {"name": "DETACHED HEAD", "level": "repo-01", "moves": list(MOVES)},
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

    # shrine semantics: while a warden stands, no move enters the guarded cell
    for cell, shrine in lvl.shrines.items():
        anchor = [shrine.anchor[0], shrine.anchor[1]]
        for nid, node in nodes.items():
            if node["kind"] != "shrine" or node["hp"] <= 0:
                continue
            for token, target in node["moves"].items():
                if target and nodes[target]["cell"] == anchor and nodes[target]["kind"] == "shrine":
                    errors.append(f"{nid}: walks onto guarded {shrine.name} anchor while warden stands")

    # the key must be reachable: some cleared shrine node steps onto 'K'
    key_cell = [lvl.key[0], lvl.key[1]]
    key_reachable = any(
        node["kind"] == "shrine" and node["hp"] == 0
        and any(t and nodes[t]["cell"] == key_cell and nodes[t]["kind"] == "normal" and nodes[t]["key"] == 1
                for t in node["moves"].values())
        for node in nodes.values()
    )
    if not key_reachable:
        errors.append("the golden key is never reachable")
    return errors
