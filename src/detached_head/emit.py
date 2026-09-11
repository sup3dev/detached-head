"""Emit the playable repository: markdown graph, graph.json, README, leaderboard."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from .level import Level

EMOJI = {"F": "\u2b06\ufe0f", "B": "\u2b07\ufe0f", "L": "\u2b05\ufe0f", "R": "\u27a1\ufe0f", "X": "\U0001F4A5"}

# frames shown on the front page (id, caption)
TEASERS = [
    ("x20y21N", "spawn \u00b7 branch main"),
    ("x06y12W", "the shrine of the key \u00b7 THE OLDEST BUG"),
    ("x20y11N", "the gate \u00b7 locked"),
    ("x20y05Nh4", "THE DEBT \u00b7 behind the gate"),
]


def _header(nid: str, node: dict, lvl: Level) -> str:
    zone = node["zone"]
    branch = {"win": "deployed"}.get(zone, zone)
    if node["kind"] == "win":
        return "### `branch: prod` \u00b7 the way out \u00b7 all checks passed"
    pos = f"\U0001f4cd ({node['cell'][0]}, {node['cell'][1]})"
    facing = f"facing {node['angle']}"
    if node["kind"] == "arena":
        bar = "\u2588" * node["hp"] + "\u2591" * (4 - node["hp"])
        return f"### `branch: prod` \u00b7 {pos} \u00b7 {facing} \u00b7 \u2694 THE DEBT [{bar} {node['hp']}/4]"
    if node["kind"] == "shrine":
        if node["hp"] > 0:
            bar = "\u2588" * node["hp"] + "\u2591" * (3 - node["hp"])
            suffix = f"\u2694 THE OLDEST BUG [{bar} {node['hp']}/3]"
        else:
            suffix = "\u2721 cleared \u00b7 the key is yours to take"
        return f"### {zone} \u00b7 {pos} \u00b7 {facing} \u00b7 {suffix}"
    key = "\U0001f511 THE KEY" if node["key"] else "\U0001f511 \u2014"
    suffix = ""
    if node["imp_dead"]:
        suffix = " \u00b7 \u2716 bug deleted (it will be back)"
    return f"### `branch: {branch}` \u00b7 {pos} \u00b7 {facing} \u00b7 {key}{suffix}"


def node_md(nid: str, node: dict, lvl: Level, fmt: str = "webp") -> str:
    if node["kind"] == "win":
        return win_md(fmt)
    moves = node["moves"]
    up = _link(moves.get("F"), "F")
    left = _link(moves.get("L"), "L")
    fire = _link(moves.get("X"), "X")
    right = _link(moves.get("R"), "R")
    down = _link(moves.get("B"), "B")
    return f"""<!-- node:{nid} -->
{_header(nid, node, lvl)}

![frame](../assets/{nid}.{fmt})

|      |      |      |
|:----:|:----:|:----:|
|      | {up} |      |
| {left} | {fire} | {right} |
|      | {down} |      |

[\u2302 index](../README.md)
"""


def _link(target: str | None, token: str) -> str:
    if target is None:
        return "\u26d4\ufe0f"  # a wall (or a locked gate): no link
    return f"[{EMOJI[token]}]({target}.md)"


def win_md(fmt: str = "webp") -> str:
    return f"""<!-- node:WIN -->
### `branch: prod` \u00b7 the way out \u00b7 all checks passed

![victory](../assets/win.{fmt})

# \u2714 YOU ESCAPED

**THE DEBT** is deleted. The build is green, the tests pass, the way home is
open. You may go home now.

\U0001f3c6 Think a shorter escape exists? Write it down like chess moves
(\u2b06\ufe0f`F` \u2b07\ufe0f`B` \u2b05\ufe0f`L` \u27a1\ufe0f`R` \U0001F4A5`X`) and open an issue titled `/run FFRRFX...`.
The route to beat: **62 clicks** \u2014 [LEADERBOARD.md](../LEADERBOARD.md).
Solvers welcome: `data/graph.json` is public, code is legal.

[\u2302 index](../README.md)
"""


def emit_graph_json(graph: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph, indent=1, ensure_ascii=False), encoding="utf-8")


def emit_markdown(graph: dict, lvl: Level, root: Path, fmt: str = "webp") -> None:
    game = root / "game"
    if game.exists():
        shutil.rmtree(game)
    game.mkdir(parents=True)
    for nid, node in graph["nodes"].items():
        (game / f"{nid}.md").write_text(node_md(nid, node, lvl, fmt), encoding="utf-8", newline="\n")
    emit_graph_json(graph, root / "data" / "graph.json")


def emit_leaderboard(root: Path) -> None:
    root.joinpath("LEADERBOARD.md").write_text(LEADERBOARD_MD, encoding="utf-8", newline="\n")


LEADERBOARD_MD = """# \U0001f3c1 Shortest-route leaderboard

The escape, measured in **clicks**. Route to beat: **62 clicks**
(7 aimed shots: THE OLDEST BUG \u00d73, THE DEBT \u00d74).

## How to compete

No recordings, no timers \u2014 this game has no JavaScript, so nothing can be
tracked. You submit a **route**, like a list of chess moves:

1. Plan your escape on the map in the README and write it as tokens, one
   letter per click: \u2b06\ufe0f `F` forward \u00b7 \u2b07\ufe0f `B` back \u00b7 \u2b05\ufe0f `L` turn left \u00b7 \u27a1\ufe0f `R` turn right \u00b7 \U0001F4A5 `X` fire.
   A route looks like `FFRRRFFXFF...`.
2. Open an issue titled `/run FFRRFX...` with your route.
3. A GitHub Action replays it over `data/graph.json`. Broken routes are
   rejected naming the exact click where they die \u2014 fix and resubmit.

`graph.json` is public and **writing a solver is legal** \u2014 the first to beat
62 will probably do it with code. That is not cheating; that is the sport.
One best result per player.

<!-- LEADERBOARD:BEGIN -->
| # | Player | Clicks | Date |
|---|--------|--------|------|
<!-- LEADERBOARD:END -->
"""


def emit_readme(graph: dict, lvl: Level, root: Path, fmt: str = "webp") -> None:
    start = graph["start"]
    teasers = "\n".join(
        f'<p align="center"><img src="assets/{nid}.{fmt}" width="45%" alt="{cap}"><img src="assets/{nid}.{fmt}" width="0.1%"></p>'
        for nid, cap in TEASERS
    )
    # two teasers per row, GitHub-friendly
    rows = [TEASERS[i : i + 2] for i in range(0, len(TEASERS), 2)]
    teasers = "\n".join(
        '<p align="center">'
        + "".join(f'<img src="assets/{nid}.{fmt}" width="46%" alt="{cap}">' for nid, cap in row)
        + "</p>"
        for row in rows
    )
    text = f"""<!-- DETACHED HEAD -->
<p align="center"><img src="assets/title.{fmt}" width="100%" alt="DETACHED HEAD"></p>

<p align="center">
<a href="game/{start}.md"><img src="https://img.shields.io/badge/%E2%96%B6_PLAY-run_away_from_work-brightgreen?style=for-the-badge" alt="PLAY"></a>
&nbsp;<a href="LEADERBOARD.md"><img src="https://img.shields.io/badge/%F0%9F%8F%81_speedrun-leaderboard-yellow?style=for-the-badge" alt="leaderboard"></a>
</p>

---

You fell asleep at your desk and woke up **inside a repository** \u2014 a dungeon
made of code, frozen half-remembered decisions, and bugs.

The little **bugs** squatting in every wing die to one shot of your blaster
\u2014 and always crawl back by the time you return. It's a legacy codebase;
that's what the bugs do. Your way home needs three things:

1. **THE OLDEST BUG** hunches over the golden key in its shrine. Three hits.
   Then the key is yours.
2. **The gate** \u2014 it only opens for the key.
3. **THE DEBT** behind the gate: the ancient thing growing in the dark since
   2009, grinning, with a burning `$` in its chest. Four hits. It does not
   stay down if you run.

Slay the oldest bug. Take the key. Open the gate. End THE DEBT. Go home.

*(Devs: yes, the wings are branches, the walls are logs and merge conflicts,
and the victory screen credits `git blame` as the cleanup crew. That layer
is yours. Everyone else gets a dungeon, bugs, a key, a gate and a monster.)*

{teasers}

## How to play

Every screen is one markdown file. One click = one move. The letter after
each emoji is your speedrun token \u2014 write them down as you go.

| click | move | | click | move |
|---|---|---|---|---|
| \u2b06\ufe0f `F` | step forward | | \u2b05\ufe0f `L` / \u27a1\ufe0f `R` | turn left / right |
| \u2b07\ufe0f `B` | step back | | \U0001F4A5 `X` | fire (aimed only) |

\U0001f41b Bugs die to one aimed \U0001F4A5 \u2014 put the crosshair on them (they
regenerate when you leave the wing; it's a legacy codebase).
\U0001f511 The key picks itself up once the OLDEST BUG is down \u2014 and with the
key in hand, the oldest bug stays dead for good.
\U0001f6ab \u26d4\ufe0f means a wall, a locked gate, or the oldest bug still standing his ground.

**This is turn-based by nature.** Every click is a page load on github.com \u2014
the repository chrome blinks, then your new frame arrives. That is not a bug
to fix, it is the medium's metronome: play it like chess with a raycaster,
not like Quake. (There is also no sound. The repo is very quiet.)

## The map

<p align="center"><img src="assets/map.{fmt}" width="70%" alt="repo-01 map"></p>

## How this works (no, there is no engine)

- The whole game is **{len(graph["nodes"])} markdown files** hyperlinked into a stateless graph: one file per (position \u00d7 facing \u00d7 world state).
- Walls are **missing links**. The boss has health because its HP lives only inside the arena sub-graph \u2014 that trick is why this game can do things a "Doom in a README" cannot.
- Frames are raycast-rendered by a ~100%-numpy Wolfenstein-style renderer, with procedurally generated textures, sprites, HUD and minimap. Zero external assets.
- The contest is **shortest route, not reflexes**: nothing can be tracked in a
  game with no JavaScript, so you submit a route like a list of chess moves —
  open an issue `/run FFRRX...` and a GitHub Action replays it over
  `data/graph.json`. Solvers are legal. [LEADERBOARD.md](LEADERBOARD.md)

Design math and pipeline internals: [docs/DESIGN.md](docs/DESIGN.md) \u00b7
speedrun guide: [docs/LEADERBOARD.md](docs/LEADERBOARD.md)

## Rebuild from source

```
python build.py            # regenerates every frame and the whole graph
pytest                     # graph invariants
```

MIT License. Everything in this repo \u2014 code, textures, sprites, the level \u2014
is generated by this repo.
"""
    root.joinpath("README.md").write_text(text, encoding="utf-8", newline="\n")


def emit_preview(graph: dict, lvl: Level, root: Path, fmt: str = "webp") -> None:
    """A static HTML mirror of the graph so the game is playable locally from disk."""
    pv = root / "_preview"
    if pv.exists():
        shutil.rmtree(pv)
    pv.mkdir(parents=True)
    tpl = """<!doctype html><html><head><meta charset="utf-8"><title>{nid}</title>
<style>body{{background:#0d1117;color:#8b949e;font-family:Consolas,monospace;text-align:center}}
img{{max-width:100%;image-rendering:pixelated}}td{{padding:14px 22px;font-size:28px}}
a{{text-decoration:none}}</style></head><body>
<h3>{hdr}</h3><img src="../assets/{nid}.{fmt}"><table><tr><td></td><td>{up}</td><td></td></tr>
<tr><td>{left}</td><td>{fire}</td><td>{right}</td></tr><tr><td></td><td>{down}</td><td></td></tr></table>
<p><a href="../README.md#readme">index</a></p></body></html>"""
    for nid, node in graph["nodes"].items():
        if node["kind"] == "win":
            html = tpl.format(nid=nid, fmt=fmt, hdr="\u2714 DEPLOYED", up="", left="", right="", fire="", down="")
        else:
            m = node["moves"]

            def a(t, glyph):
                return f'<a href="{t}.html">{glyph}</a>' if t else "\u26d4\ufe0f"

            html = tpl.format(
                nid=nid,
                fmt=fmt,
                hdr=_header(nid, node, lvl),
                up=a(m.get("F"), EMOJI["F"]),
                left=a(m.get("L"), EMOJI["L"]),
                fire=a(m.get("X"), EMOJI["X"]),
                right=a(m.get("R"), EMOJI["R"]),
                down=a(m.get("B"), EMOJI["B"]),
            )
        (pv / f"{nid}.html").write_text(html, encoding="utf-8")
    (pv / "index.html").write_text(
        f'<meta http-equiv="refresh" content="0;url={graph["start"]}.html">', encoding="utf-8"
    )
