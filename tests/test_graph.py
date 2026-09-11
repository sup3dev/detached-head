"""Graph invariant and integration tests (rendering kept to a smoke minimum)."""

from __future__ import annotations

from pathlib import Path

import pytest

from detached_head import emit
from detached_head.graph import WIN, arena_id, build_graph, normal_id, shrine_id, validate
from detached_head.level import load

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def lvl():
    return load(ROOT / "level" / "map.txt")


@pytest.fixture(scope="module")
def graph(lvl):
    return build_graph(lvl)


def test_graph_invariants(graph, lvl):
    assert validate(graph, lvl) == []


def test_budget(graph):
    assert 3000 <= len(graph["nodes"]) <= 7000, f"node count {len(graph['nodes'])} outside budget"


def test_three_shrines(graph, lvl):
    names = {s.name for s in lvl.shrines.values()}
    assert len(names) == 3
    assert any(s.kind == "key" for s in lvl.shrines.values())
    assert sum(1 for s in {id(s): s for s in lvl.shrines.values()}.values() if s.kind == "trophy") == 2


def test_gate_is_solid_without_key(graph, lvl):
    gx, gy = lvl.gate
    below = normal_id(gx, gy + 1, "N", False)
    assert below in graph["nodes"]
    assert graph["nodes"][below]["moves"]["F"] is None, "keyless player walks through the gate"
    assert all(
        n["key"] == 1 for n in graph["nodes"].values()
        if n["kind"] == "normal" and n["cell"] == [gx, gy]
    )


def test_shrine_entry_spawns_full_warden(graph, lvl):
    # stepping from the key shrine's doorway west onto shrine floor
    door = normal_id(6, 12, "W", False)
    assert door in graph["nodes"]
    assert graph["nodes"][door]["moves"]["F"] == shrine_id(5, 12, "W", 2, False)


def test_warden_guards_the_key(graph, lvl):
    # inside the shrine with the warden standing, forward onto the key is a wall
    guard = shrine_id(5, 12, "W", 2, False)
    assert graph["nodes"][guard]["moves"]["F"] is None


def test_warden_fall_opens_the_key(graph, lvl):
    hp1 = graph["nodes"][shrine_id(5, 12, "W", 2, False)]["moves"]["X"]
    assert hp1 == shrine_id(5, 12, "W", 1, False)
    cleared = graph["nodes"][hp1]["moves"]["X"]
    assert cleared == shrine_id(5, 12, "W", 0, False)
    assert graph["nodes"][cleared]["moves"]["F"] == normal_id(4, 12, "W", True)  # the pickup


def test_fleeing_shrine_resets_warden(graph, lvl):
    # leave the shrine from the entry cell facing back east, then re-enter
    entry = shrine_id(5, 12, "E", 1, False)  # hurt warden, facing the door
    outside = graph["nodes"][entry]["moves"]["F"]
    assert outside == normal_id(6, 12, "E", False)
    back_in = graph["nodes"][normal_id(6, 12, "W", False)]["moves"]["F"]
    assert back_in == shrine_id(5, 12, "W", 2, False), "warden must return at full strength"


def test_trophy_shrine_flow(graph, lvl):
    # hotfix shrine: door (33,13) east onto (34,13), trophy at (35,13)
    enter = graph["nodes"][normal_id(33, 13, "E", False)]["moves"]["F"]
    assert enter == shrine_id(34, 13, "E", 2, False)
    guarded = graph["nodes"][shrine_id(34, 13, "E", 2, False)]["moves"]["F"]
    assert guarded is None
    cleared = graph["nodes"][shrine_id(34, 13, "E", 0, False)]["moves"]["F"]
    assert cleared == shrine_id(35, 13, "E", 0, False)  # stand on the trophy


def test_shrine_exit_keeps_key(graph, lvl):
    # re-enter the cleared key shrine holding the key, then leave: key kept
    inside = shrine_id(5, 12, "W", 2, True)  # warden returns, key stays
    assert inside in graph["nodes"]
    leave = graph["nodes"][shrine_id(5, 12, "E", 2, True)]["moves"]["F"]
    assert leave == normal_id(6, 12, "E", True)


def test_arena_entry_full_hp(graph, lvl):
    gx, gy = lvl.gate
    on_gate = normal_id(gx, gy, "N", True)
    assert graph["nodes"][on_gate]["moves"]["F"] == arena_id(gx, gy - 1, "N", 4)


def test_fire_chain(graph):
    some_arena = next(n for n in graph["nodes"].values() if n["kind"] == "arena" and n["hp"] == 1)
    assert some_arena["moves"]["X"] == WIN
    hp3 = next(n for n in graph["nodes"].values() if n["kind"] == "arena" and n["hp"] == 3)
    nid_hp3 = next(k for k, v in graph["nodes"].items() if v is hp3)
    assert hp3["moves"]["X"] == nid_hp3.replace("h3", "h2")
    some_normal = next(n for n in graph["nodes"].values() if n["kind"] == "normal")
    nid = next(k for k, v in graph["nodes"].items() if v is some_normal)
    assert some_normal["moves"]["X"] == nid  # dry fire outside fights


def test_arena_exit_and_regeneration(graph, lvl):
    gx, gy = lvl.gate
    entry = arena_id(gx, gy - 1, "S", 3)
    assert entry in graph["nodes"]
    assert graph["nodes"][entry]["moves"]["F"] == normal_id(gx, gy, "S", True)
    assert graph["nodes"][normal_id(gx, gy, "N", True)]["moves"]["F"] == arena_id(gx, gy - 1, "N", 4)


def test_turns_are_reversible(graph):
    normals = [(k, n) for k, n in graph["nodes"].items() if n["kind"] == "normal"][:200]
    assert normals
    for nid, node in normals:
        left = node["moves"]["L"]
        if left:
            assert graph["nodes"][left]["moves"]["R"] == nid


def test_win_reachable_and_no_orphans(graph):
    seen = {graph["start"]}
    frontier = [graph["start"]]
    while frontier:
        nid = frontier.pop()
        for t in graph["nodes"][nid]["moves"].values():
            if t and t not in seen:
                seen.add(t)
                frontier.append(t)
    assert WIN in seen
    assert seen == set(graph["nodes"]), "emitted graph contains unreachable states"


def test_renderer_smoke(lvl):
    from detached_head.art import make_sprites, make_textures
    from detached_head.render import Renderer

    r = Renderer(lvl, make_textures(), make_sprites())
    frame = r.frame(*lvl.spawn, "N", key=False, sprites=[])
    assert frame.size == (960, 600)
    frame = r.frame(5, 12, "W", key=False, sprites=[(4, 12, "warden2")], bar=("THE WARDEN", 2, 2))
    assert frame.size == (960, 600)


def test_markdown_emission(graph, lvl):
    nid, node = next(iter(graph["nodes"].items()))
    md = emit.node_md(nid, node, lvl)
    assert f"![frame](../assets/{nid}.webp)" in md
    assert "[\u2302 index](../README.md)" in md
    win = emit.win_md()
    assert "YOU ESCAPED" in win and "LEADERBOARD" in win
    shrine_node = next(n for n in graph["nodes"].values() if n["kind"] == "shrine" and n["hp"] > 0)
    hdr = emit._header("x", shrine_node, lvl)
    assert "THE WARDEN" in hdr
