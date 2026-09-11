# Speedrun guide

The leaderboard ranks runs by **clicks**, not seconds: a GitHub Action cannot
time you, but it can replay your exact route over `data/graph.json`.
For a turn-based game this is the honest clock.

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

1. Play from the first screen to `YOU ESCAPED`, writing down one token per click.
2. Open an issue titled `/run FFRRFX...` (case-insensitive, spaces/commas ignored).
3. The Action ([.github/workflows/leaderboard.yml](../.github/workflows/leaderboard.yml)):
   - tokenizes the route and replays it from the start node;
   - rejects it if any move hits a wall, fires at nothing, or never reaches WIN
     (the error names the exact 0-based click where the route broke);
   - writes your time into the markers in [LEADERBOARD.md](../LEADERBOARD.md),
     keeping only each player's best run, and closes the issue with your place.

Spam guards: routes over 10,000 tokens are rejected outright; one best result
per player; issues are closed after processing.

## Testing locally

```
PYTHONPATH=src python -m detached_head.leaderboard "FFRRFX..."   # validate a route
PYTHONPATH=src python -m detached_head.leaderboard --submit YOU "FFRRFX..."  # + write LEADERBOARD.md
```

Shortest known run: **62 clicks** (7 aimed shots: 3 for THE OLDEST BUG,
4 for THE DEBT).
