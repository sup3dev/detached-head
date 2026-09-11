# 🏁 Leaderboards

This game has no JavaScript and no state, so nothing about a playthrough can
be recorded — the contest is the **route** you submit, like a list of chess
moves. Tokens: ⬆️ `F` forward · ⬇️ `B` back · ⬅️ `L` left · ➡️ `R` right · 💥 `X` fire.

Open an issue titled `/run <tokens>` — or `/run bugs <tokens>`,
`/run scenic <tokens>` for the other categories. A GitHub Action replays
your route over `data/graph.json`; broken routes are rejected naming the
exact click where they die. Solvers are legal (`tools/solve.py` proves the
any% floor). One best result per player, per category.

## any% — the escape (fewest clicks)

`tools/solve.py` already proves **62** optimal here; this table is the
tutorial. The real fights are below.

<!-- LEADERBOARD:BEGIN -->
| # | Player | Clicks | Date |
|---|---|---|---|
| 1 | sup3dev | 62 | 2026-09-11 |
<!-- LEADERBOARD:END -->

## bugs% — the extermination (fewest clicks)

One route: kill **all five wing bugs**, **THE OLDEST BUG** and **THE DEBT**.
Wing bugs regenerate when you leave their wing, so order matters — this is
prize-collecting, not plain BFS. No solver shipped; that's the category.

<!-- LEADERBOARD:bugs:BEGIN -->
| # | Player | Clicks | Date |
|---|--------|--------|------|
<!-- LEADERBOARD:bugs:END -->

## scenic% — the long way home (most clicks, cap 666)

The **longest** valid route to the escape. Longest-path is NP-hard; iterate
through issues. Waste elegantly.

<!-- LEADERBOARD:scenic:BEGIN -->
| # | Player | Clicks | Date |
|---|--------|--------|------|
<!-- LEADERBOARD:scenic:END -->

Details and local testing: [docs/LEADERBOARD.md](docs/LEADERBOARD.md).
