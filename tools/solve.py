#!/usr/bin/env python3
"""Solve the any% category: the provably shortest route from spawn to WIN.

This is the tutorial category — the floor is 62 clicks and this script
prints it. bugs% (prize-collecting) and scenic% (NP-hard longest path) are
the contested ones; no solver shipped for those on purpose.

Usage:
    python tools/solve.py                 # find the route, validate, print
    python tools/solve.py --title         # print just the ready issue title
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def solve(graph: dict) -> str:
    start, win, nodes = graph["start"], graph["win"], graph["nodes"]
    prev: dict[str, tuple[str, str]] = {start: ("", "")}
    queue: collections.deque[str] = collections.deque([start])
    while queue:
        nid = queue.popleft()
        if nid == win:
            break
        for token, target in nodes[nid]["moves"].items():
            if target and target in nodes and target not in prev:
                prev[target] = (nid, token)
                queue.append(target)
    if win not in prev:
        raise SystemExit("WIN is unreachable — the graph is broken")
    route: list[str] = []
    cursor = win
    while prev[cursor][0]:
        cursor, token = prev[cursor]
        route.append(token)
    return "".join(reversed(route))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", action="store_true", help="print only the issue title")
    args = ap.parse_args()

    graph = json.loads((ROOT / "data" / "graph.json").read_text(encoding="utf-8"))
    route = solve(graph)

    from detached_head.leaderboard import load_graph, validate_run

    result = validate_run(load_graph(ROOT / "data" / "graph.json"), route)
    if not result["ok"]:
        raise SystemExit(f"solver produced an invalid route?!\n{result['error']}")
    if args.title:
        print(f"/run {route}")
    else:
        print(f"optimal any% route: {result['clicks']} clicks")
        print(f"submit as issue title: /run {route}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
