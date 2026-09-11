# Shortest-route guide

The leaderboard ranks **routes by clicks**, not seconds. This game has no
JavaScript and no state, so nothing about a playthrough can be recorded —
instead, the contest is the artifact itself: you submit a route, like a list
of chess moves, and the repository replays it.

## Tokens

Every click is one token:

| emoji | token | meaning |
|---|---|---|
| ⬆️ | `F` | step forward |
| ⬇️ | `B` | step back |
| ⬅️ | `L` | turn left 90° |
| ➡️ | `R` | turn right 90° |
| 💥 | `X` | fire (only hits what the crosshair covers) |

## Submitting

1. Plan a route from the first screen to `YOU ESCAPED` (the README has the
   full map) and write it as tokens, e.g. `FFRRRFFXFF...`.
2. Open an issue titled `/run FFRRFX...` (case-insensitive, spaces/commas
   ignored).
3. The Action ([.github/workflows/leaderboard.yml](../.github/workflows/leaderboard.yml))
   replays the route from the start node, rejects any move that hits a wall,
   fires at nothing or never reaches WIN (naming the exact 0-based click
   where the route broke), then writes your time into the markers of
   [LEADERBOARD.md](../LEADERBOARD.md) — best result per player — and closes
   the issue with your place.

## Solvers are legal

`data/graph.json` is the whole game state machine, public. BFS it, Dijkstra
it, throw simulated annealing at it — the first person to beat the current
best (62 clicks) will almost certainly do it with code, and that is the
sport, not cheating. Pull requests with a `tools/solve.py` are welcome.

## Testing locally

```
PYTHONPATH=src python -m detached_head.leaderboard "FFRRFX..."   # validate a route
PYTHONPATH=src python -m detached_head.leaderboard --submit YOU "FFRRFX..."  # + write LEADERBOARD.md
```

Spam guards: routes over 10,000 tokens are rejected; one best result per
player; issues are closed after processing.
