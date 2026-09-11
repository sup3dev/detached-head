"""Speedrun leaderboard for DETACHED HEAD.

A speedrun route is a string of move tokens (F, B, L, R, X) describing the
emoji links a player clicked. This module replays a route against the game
graph (data/graph.json), accepts or rejects it, and records accepted runs in
the markdown table inside LEADERBOARD.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

BOARD_BEGIN = "<!-- LEADERBOARD:BEGIN -->"
BOARD_END = "<!-- LEADERBOARD:END -->"

# Anti-spam guard for issue-submitted routes: the optimum is ~60 clicks,
# so anything longer than this is trolling, not speedrunning.
MAX_ROUTE_TOKENS = 10_000

# Competition categories:
#   any    - shortest route to WIN (solved by tools/solve.py, the tutorial)
#   bugs   - shortest route that also kills every wing bug and the oldest bug
#   scenic - the LONGEST valid route to WIN (capped), ranked descending
CATEGORIES = ("any", "bugs", "scenic")
SCENIC_CAP = 666


def _markers(category: str) -> tuple[str, str]:
    if category == "any":
        return BOARD_BEGIN, BOARD_END
    return f"<!-- LEADERBOARD:{category}:BEGIN -->", f"<!-- LEADERBOARD:{category}:END -->"

TABLE_HEADER = "| # | Player | Clicks | Date |"
TABLE_SEPARATOR = "|---|---|---|---|"

# Whitespace and commas are ignored inside routes: "f, x" == "FX".
_SEPARATOR_RE = re.compile(r"[\s,]+")


def load_graph(path: str | Path) -> dict:
    """Load data/graph.json and check the keys the validator relies on."""
    data = json.loads(Path(path).read_bytes().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("graph root must be a JSON object")
    for key in ("start", "win", "nodes"):
        if key not in data:
            raise ValueError(f"graph is missing required key '{key}'")
    return data


def _tokenize(route: str) -> list[str]:
    """Split a route into uppercase one-character tokens."""
    return list(_SEPARATOR_RE.sub("", route).upper())


def validate_run(graph: dict, route: str, category: str = "any") -> dict:
    """Replay a route through the graph, starting at graph["start"].

    Token indexes in error messages are 0-based. On failure "clicks" counts
    the tokens applied before the run broke. ok=True requires the run to end
    exactly on graph["win"], plus the category's extra demands:
    bugs% needs every wing bug and the oldest bug dead; scenic% needs the
    route within SCENIC_CAP clicks (longest is best).
    """
    if category not in CATEGORIES:
        return {"ok": False, "error": f"unknown category '{category}' (use {'/'.join(CATEGORIES)})", "clicks": 0}
    tokens = _tokenize(route)
    if not tokens:
        return {"ok": False, "error": "route is empty", "clicks": 0}
    if len(tokens) > MAX_ROUTE_TOKENS:
        return {
            "ok": False,
            "error": f"route exceeds {MAX_ROUTE_TOKENS} clicks (spam guard)",
            "clicks": 0,
        }
    if category == "scenic" and len(tokens) > SCENIC_CAP:
        return {
            "ok": False,
            "error": f"scenic% routes are capped at {SCENIC_CAP} clicks",
            "clicks": 0,
        }

    valid_moves = list(graph.get("meta", {}).get("moves", []))
    valid = set(valid_moves)
    nodes = graph["nodes"]
    current = graph["start"]
    if current not in nodes:
        return {"ok": False, "error": f"start node '{current}' is not in nodes", "clicks": 0}

    imp_kills = 0
    oldest_kills = 0
    for i, token in enumerate(tokens):
        if token not in valid:
            return {
                "ok": False,
                "error": (
                    f"token {i} '{token}' is not a valid move "
                    f"(valid moves: {'/'.join(valid_moves)})"
                ),
                "clicks": i,
            }
        target = nodes[current].get("moves", {}).get(token)
        if target is None:
            return {
                "ok": False,
                "error": (
                    f"token {i} '{token}' moves into a wall at node "
                    f"'{current}' (no link)"
                ),
                "clicks": i,
            }
        if target not in nodes:
            return {
                "ok": False,
                "error": f"token {i} '{token}' leads to unknown node '{target}'",
                "clicks": i,
            }
        nxt = nodes[target]
        if token == "X" and target != current:  # a hit landed
            cur = nodes[current]
            if cur["kind"] == "shrine" and cur.get("hp") and nxt["kind"] == "shrine" and nxt["hp"] == 0:
                oldest_kills += 1
            elif cur["kind"] == "normal" and cur.get("imp_dead") == 0 and nxt.get("imp_dead") == 1:
                imp_kills += 1
        current = target

    if current != graph["win"]:
        return {"ok": False, "error": "run did not reach WIN", "clicks": len(tokens)}
    if category == "bugs":
        need = graph.get("meta", {}).get("bugs_required", 5)
        if imp_kills < need or oldest_kills < 1:
            return {
                "ok": False,
                "error": (
                    f"bugs% requires {need} wing bugs and the oldest bug dead "
                    f"(saw {imp_kills} wing kills, oldest bug: {'yes' if oldest_kills else 'no'})"
                ),
                "clicks": len(tokens),
            }
    return {
        "ok": True,
        "clicks": len(tokens),
        "end": current,
        "category": category,
        "imp_kills": imp_kills,
        "oldest_kills": oldest_kills,
    }


def _board_rows(text: str, begin_marker: str = BOARD_BEGIN, end_marker: str = BOARD_END) -> list[dict]:
    """Extract data rows from the given leaderboard markdown table."""
    rows = []
    begin = text.find(begin_marker)
    end = text.find(end_marker)
    section = text[begin + len(begin_marker):end] if begin != -1 and end > begin else text
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        # Skips the header ("#"), the separator ("---") and foreign lines.
        if len(cells) != 4 or not cells[0].isdigit():
            continue
        rows.append({"player": cells[1], "clicks": int(cells[2]), "date": cells[3]})
    return rows


def _render_table(rows: list[dict], descending: bool = False) -> str:
    ordered = sorted(rows, key=lambda r: (-r["clicks"] if descending else r["clicks"], r["date"], r["player"]))
    lines = [TABLE_HEADER, TABLE_SEPARATOR]
    for place, row in enumerate(ordered, start=1):
        lines.append(f"| {place} | {row['player']} | {row['clicks']} | {row['date']} |")
    return "\n".join(lines)


def _merge_entry(rows: list[dict], entry: dict, descending: bool = False) -> list[dict]:
    """Combine existing rows with a new entry, keeping each player's best run.

    Best = fewest clicks (most, for scenic); on a tie the recorded run stays.
    """
    merged: dict[str, dict] = {}

    def better(new: dict, old: dict) -> bool:
        return new["clicks"] > old["clicks"] if descending else new["clicks"] < old["clicks"]

    for row in rows + [entry]:
        best = merged.get(row["player"])
        if best is None or better(row, best):
            merged[row["player"]] = row
    return list(merged.values())


def update_leaderboard(board_path: str | Path, entry: dict, category: str = "any") -> None:
    """Record an entry in the category's markdown leaderboard table.

    The table lives between the category's BEGIN/END markers; everything
    outside the markers is preserved byte-for-byte. Markers are appended if
    the file or the markers are missing.
    """
    path = Path(board_path)
    raw = path.read_bytes() if path.exists() else b""
    text = raw.decode("utf-8")

    begin_marker, end_marker = _markers(category)
    descending = category == "scenic"
    table = _render_table(_merge_entry(_board_rows(text, begin_marker, end_marker), entry, descending), descending)

    begin = text.find(begin_marker)
    end = text.find(end_marker)
    if begin != -1 and end != -1 and end > begin:
        text = text[: begin + len(begin_marker)] + "\n" + table + "\n" + text[end:]
    else:
        prefix = "" if not text or text.endswith("\n") else "\n"
        text = f"{text}{prefix}{begin_marker}\n{table}\n{end_marker}\n"

    path.write_bytes(text.encode("utf-8"))


def player_place(board_path: str | Path, player: str, category: str = "any") -> int | None:
    """Return the player's place (1-based) in the category's board, if present."""
    begin_marker, end_marker = _markers(category)
    rows = _board_rows(Path(board_path).read_bytes().decode("utf-8"), begin_marker, end_marker)
    ordered = sorted(rows, key=lambda r: (-r["clicks"] if category == "scenic" else r["clicks"], r["date"], r["player"]))
    for place, row in enumerate(ordered, start=1):
        if row["player"] == player:
            return place
    return None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detached_head.leaderboard",
        description="Validate DETACHED HEAD speedrun routes and update the leaderboard.",
    )
    parser.add_argument(
        "route",
        help="route tokens, e.g. FFRRFX (case-insensitive, spaces/commas ignored)",
    )
    parser.add_argument(
        "--graph",
        default="data/graph.json",
        help="path to graph.json (default: %(default)s)",
    )
    parser.add_argument(
        "--board",
        default="LEADERBOARD.md",
        help="path to the leaderboard markdown (default: %(default)s)",
    )
    parser.add_argument(
        "--submit",
        metavar="PLAYER",
        help="validate the route and record PLAYER's result in the leaderboard",
    )
    parser.add_argument(
        "--category",
        choices=CATEGORIES,
        default="any",
        help="competition category (default: %(default)s)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        graph = load_graph(args.graph)
    except (OSError, ValueError) as exc:
        print(f"error: cannot load graph '{args.graph}': {exc}")
        return 2

    result = validate_run(graph, args.route, category=args.category)
    if not result["ok"]:
        print(f"FAIL: {result['error']}")
        return 1

    if args.submit is None:
        label = f"{args.category}% " if args.category != "any" else ""
        print(f"OK: {label}{result['clicks']} clicks, reached {result['end']}")
        return 0

    entry = {
        "player": args.submit,
        "route": "".join(_tokenize(args.route)),
        "clicks": result["clicks"],
        "date": date.today().isoformat(),
    }
    update_leaderboard(args.board, entry, category=args.category)
    place = player_place(args.board, args.submit, category=args.category)
    label = f"{args.category}% " if args.category != "any" else ""
    print(f"Run accepted: {label}{result['clicks']} clicks, reached WIN.")
    print(f"@{args.submit} is #{place} on the leaderboard.")
    print()
    board_text = Path(args.board).read_bytes().decode("utf-8")
    print(_render_table(_board_rows(board_text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
