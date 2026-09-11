# 🏁 Shortest-route leaderboard

The escape, measured in **clicks**. Route to beat: **62 clicks**
(7 aimed shots: THE OLDEST BUG ×3, THE DEBT ×4).

## How to compete

No recordings, no timers — this game has no JavaScript, so nothing can be
tracked. You submit a **route**, like a list of chess moves:

1. Plan your escape on the map in the README and write it as tokens, one
   letter per click: ⬆️ `F` forward · ⬇️ `B` back · ⬅️ `L` turn left · ➡️ `R` turn right · 💥 `X` fire.
   A route looks like `FFRRRFFXFF...`.
2. Open an issue titled `/run FFRRFX...` with your route.
3. A GitHub Action replays it over `data/graph.json`. Broken routes are
   rejected naming the exact click where they die — fix and resubmit.

`graph.json` is public and **writing a solver is legal** — the first to beat
62 will probably do it with code. That is not cheating; that is the sport.
One best result per player.

<!-- LEADERBOARD:BEGIN -->
| # | Player | Clicks | Date |
|---|---|---|---|
| 1 | sup3dev | 62 | 2026-09-11 |
<!-- LEADERBOARD:END -->
