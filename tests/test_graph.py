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
    assert 4000 <= len(graph["nodes"]) <= 9000, f"node count {len(graph['nodes'])} outside budget"


def test_five_killable_bugs(graph, lvl):
    assert len(lvl.imps) == 5
    assert {z for z in lvl.imps} == {"main", "feature", "hotfix", "docs", "refactor"}


def test_bug_dies_to_one_aimed_shot(graph, lvl):
    node = graph["nodes"][normal_id(16, 22, "S", False)]  # facing the hub bug at (16,23)
    assert node["imp_dead"] == 0
    assert node["moves"]["X"] == normal_id(16, 22, "S", False, True)
    dead = graph["nodes"][normal_id(16, 22, "S", False, True)]
    assert dead["moves"]["X"] == normal_id(16, 22, "S", False, True)  # dry fire on a corpse


def test_unaimed_shot_is_dry_fire(graph, lvl):
    facing_away = graph["nodes"][normal_id(16, 22, "N", False)]  # bug behind the player
    assert facing_away["moves"]["X"] == normal_id(16, 22, "N", False)


def test_bug_regenerates_on_zone_return(graph, lvl):
    # hub -> feature corridor crosses a zone border: the hub bug is back
    hub_dead = normal_id(16, 22, "N", False, True)  # killed, standing north of it
    step_out = graph["nodes"][hub_dead]["moves"]
    # walk to the junction (same main zone) keeps the kill; leaving main revives it
    same_zone = graph["nodes"][normal_id(20, 17, "N", False, True)]  # main corridor, kill kept
    assert same_zone["imp_dead"] == 1
    release = graph["nodes"][normal_id(20, 12, "N", False)]  # gate corridor: main bug alive again
    assert release["imp_dead"] in (None, 0)


def test_gate_is_solid_without_key(graph, lvl):
    gx, gy = lvl.gate
    below = normal_id(gx, gy + 1, "N", False)
    assert below in graph["nodes"]
    assert graph["nodes"][below]["moves"]["F"] is None, "keyless player walks through the gate"
    assert all(
        n["key"] == 1 for n in graph["nodes"].values()
        if n["kind"] == "normal" and n["cell"] == [gx, gy]
    )


def test_shrine_entry_spawns_oldest_bug(graph, lvl):
    door = normal_id(6, 12, "W", False)
    assert door in graph["nodes"]
    assert graph["nodes"][door]["moves"]["F"] == shrine_id(5, 12, "W", 3, False)


def test_oldest_bug_guards_the_key(graph, lvl):
    guard = shrine_id(5, 12, "W", 3, False)
    assert graph["nodes"][guard]["moves"]["F"] is None


def test_oldest_bug_fall_opens_the_key(graph, lvl):
    hp2 = graph["nodes"][shrine_id(5, 12, "W", 3, False)]["moves"]["X"]
    assert hp2 == shrine_id(5, 12, "W", 2, False)
    hp1 = graph["nodes"][hp2]["moves"]["X"]
    cleared = graph["nodes"][hp1]["moves"]["X"]
    assert cleared == shrine_id(5, 12, "W", 0, False)
    assert graph["nodes"][cleared]["moves"]["F"] == normal_id(4, 12, "W", True)  # the pickup


def test_fleeing_shrine_resets_oldest_bug(graph, lvl):
    entry = shrine_id(5, 12, "E", 1, False)
    outside = graph["nodes"][entry]["moves"]["F"]
    assert outside == normal_id(6, 12, "E", False)
    back_in = graph["nodes"][normal_id(6, 12, "W", False)]["moves"]["F"]
    assert back_in == shrine_id(5, 12, "W", 3, False), "the oldest bug must return at full strength"


def test_oldest_bug_stays_dead_under_key_holder(graph, lvl):
    # once you hold the key, re-entering the shrine finds no resurrected bug
    enter = graph["nodes"][normal_id(6, 12, "W", True)]["moves"]["F"]
    assert enter == shrine_id(5, 12, "W", 0, True)
    cleared = graph["nodes"][enter]
    assert cleared["moves"]["X"] == enter  # nothing left to shoot
    leave = graph["nodes"][shrine_id(5, 12, "E", 0, True)]["moves"]["F"]
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


def test_arena_exit_and_regeneration(graph, lvl):
    gx, gy = lvl.gate
    entry = arena_id(gx, gy - 1, "S", 3)
    assert entry in graph["nodes"]
    assert graph["nodes"][entry]["moves"]["F"] == normal_id(gx, gy, "S", True)
    assert graph["nodes"][normal_id(gx, gy, "N", True)]["moves"]["F"] == arena_id(gx, gy - 1, "N", 4)


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
    frame = r.frame(5, 12, "W", key=False, sprites=[(4, 12, "ancient3")], bar=("THE OLDEST BUG", 3, 3))
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
    assert "THE OLDEST BUG" in hdr
    dead_node = next(n for n in graph["nodes"].values() if n["imp_dead"])
    assert "bug deleted" in emit._header("x", dead_node, lvl)


def test_rebuild_preserves_leaderboard_rows(tmp_path):
    from detached_head.emit import LEADERBOARD_MD, emit_leaderboard

    board = tmp_path / "LEADERBOARD.md"
    board.write_text(LEADERBOARD_MD.replace(
        "<!-- LEADERBOARD:END -->",
        "| 1 | someone | 58 | 2026-09-12 |\n<!-- LEADERBOARD:END -->",
    ), encoding="utf-8")
    emit_leaderboard(tmp_path)  # a rebuild must not wipe the CI-written row
    text = board.read_text(encoding="utf-8")
    assert "| someone | 58 |" in text
    assert "Leaderboards" in text and "bugs%" in text  # copy refreshed, categories intact
