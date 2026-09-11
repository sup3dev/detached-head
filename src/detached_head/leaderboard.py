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


def validate_run(graph: dict, route: str) -> dict:
    """Replay a route through the graph, starting at graph["start"].

    Token indexes in error messages are 0-based. On failure "clicks" counts
    the tokens applied before the run broke. ok=True requires the run to end
    exactly on graph["win"].
    """
    tokens = _tokenize(route)
    if not tokens:
        return {"ok": False, "error": "route is empty", "clicks": 0}

    valid_moves = list(graph.get("meta", {}).get("moves", []))
    valid = set(valid_moves)
    nodes = graph["nodes"]
    current = graph["start"]
    if current not in nodes:
        return {"ok": False, "error": f"start node '{current}' is not in nodes", "clicks": 0}

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
        current = target

    if current != graph["win"]:
        return {"ok": False, "error": "run did not reach WIN", "clicks": len(tokens)}
    return {"ok": True, "clicks": len(tokens), "end": current}


def _board_rows(text: str) -> list[dict]:
    """Extract data rows from a leaderboard markdown table."""
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        # Skips the header ("#"), the separator ("---") and foreign lines.
        if len(cells) != 4 or not cells[0].isdigit():
            continue
        rows.append({"player": cells[1], "clicks": int(cells[2]), "date": cells[3]})
    return rows


def _render_table(rows: list[dict]) -> str:
    ordered = sorted(rows, key=lambda r: (r["clicks"], r["date"], r["player"]))
    lines = [TABLE_HEADER, TABLE_SEPARATOR]
    for place, row in enumerate(ordered, start=1):
        lines.append(f"| {place} | {row['player']} | {row['clicks']} | {row['date']} |")
    return "\n".join(lines)


def _merge_entry(rows: list[dict], entry: dict) -> list[dict]:
    """Combine existing rows with a new entry, keeping each player's best run.

    Best = strictly fewer clicks; on a tie the already recorded run stays.
    """
    merged: dict[str, dict] = {}
    for row in rows + [entry]:
        best = merged.get(row["player"])
        if best is None or row["clicks"] < best["clicks"]:
            merged[row["player"]] = row
    return list(merged.values())


def update_leaderboard(board_path: str | Path, entry: dict) -> None:
    """Record an entry in the markdown leaderboard.

    The table lives between BOARD_BEGIN and BOARD_END markers; everything
    outside the markers is preserved byte-for-byte. Markers are appended if
    the file or the markers are missing.
    """
    path = Path(board_path)
    raw = path.read_bytes() if path.exists() else b""
    text = raw.decode("utf-8")

    table = _render_table(_merge_entry(_board_rows(text), entry))

    begin = text.find(BOARD_BEGIN)
    end = text.find(BOARD_END)
    if begin != -1 and end != -1 and end > begin:
        text = text[: begin + len(BOARD_BEGIN)] + "\n" + table + "\n" + text[end:]
    else:
        prefix = "" if not text or text.endswith("\n") else "\n"
        text = f"{text}{prefix}{BOARD_BEGIN}\n{table}\n{BOARD_END}\n"

    path.write_bytes(text.encode("utf-8"))


def player_place(board_path: str | Path, player: str) -> int | None:
    """Return the player's place (1-based) in the board, if present."""
    rows = _board_rows(Path(board_path).read_bytes().decode("utf-8"))
    ordered = sorted(rows, key=lambda r: (r["clicks"], r["date"], r["player"]))
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        graph = load_graph(args.graph)
    except (OSError, ValueError) as exc:
        print(f"error: cannot load graph '{args.graph}': {exc}")
        return 2

    result = validate_run(graph, args.route)
    if not result["ok"]:
        print(f"FAIL: {result['error']}")
        return 1

    if args.submit is None:
        print(f"OK: {result['clicks']} clicks, reached {result['end']}")
        return 0

    entry = {
        "player": args.submit,
        "route": "".join(_tokenize(args.route)),
        "clicks": result["clicks"],
        "date": date.today().isoformat(),
    }
    update_leaderboard(args.board, entry)
    place = player_place(args.board, args.submit)
    print(f"Run accepted: {result['clicks']} clicks, reached WIN.")
    print(f"@{args.submit} is #{place} on the leaderboard.")
    print()
    board_text = Path(args.board).read_bytes().decode("utf-8")
    print(_render_table(_board_rows(board_text)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
