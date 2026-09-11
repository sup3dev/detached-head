"""Graph invariant and integration tests (rendering kept to a smoke minimum)."""

from __future__ import annotations

from pathlib import Path

import pytest

from detached_head import emit
from detached_head.graph import WIN, arena_id, build_graph, normal_id, validate
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
    assert 3000 <= len(graph["nodes"]) <= 6000, f"node count {len(graph['nodes'])} outside budget"


def test_gate_is_solid_without_key(graph, lvl):
    gx, gy = lvl.gate
    below = normal_id(gx, gy + 1, "N", False)
    assert below in graph["nodes"]
    assert graph["nodes"][below]["moves"]["F"] is None, "keyless player walks through the merge gate"
    assert all(
        n["key"] == 1 for n in graph["nodes"].values()
        if n["kind"] == "normal" and n["cell"] == [gx, gy]
    )


def test_key_pickup_on_step(graph, lvl):
    kx, ky = lvl.key
    east = normal_id(kx + 1, ky, "W", False)
    assert east in graph["nodes"]
    assert graph["nodes"][east]["moves"]["F"] == normal_id(kx, ky, "W", True)


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
    assert some_normal["moves"]["X"] == nid  # dry fire outside the arena


def test_arena_exit_and_regeneration(graph, lvl):
    gx, gy = lvl.gate
    entry = arena_id(gx, gy - 1, "S", 3)  # hurt monolith, facing back to the gate
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
    frame = r.frame(*lvl.spawn, "N", key=False, hp=None, sprites=[])
    assert frame.size == (960, 600)


def test_markdown_emission(graph, lvl):
    nid, node = next(iter(graph["nodes"].items()))
    md = emit.node_md(nid, node, lvl)
    assert f"![frame](../assets/{nid}.webp)" in md
    assert "[\u2302 index](../README.md)" in md
    win = emit.win_md()
    assert "DEPLOYED" in win and "LEADERBOARD" in win
