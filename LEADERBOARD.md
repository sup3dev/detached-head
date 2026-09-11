# 🏁 Speedrun leaderboard

Fastest escape and slaying of **THE DEBT**, measured in clicks.
Shortest known run: **62 clicks**. Beat it.

## How to submit a run

1. Start from [the first screen](game/x20y21N.md) and play to the end.
2. Write down every click you make, as tokens:
   ⬆️ = `F` (forward) · ⬇️ = `B` (back) · ⬅️ = `L` (turn left) · ➡️ = `R` (turn right) · 💥 = `X` (fire)
   Your run looks like `FFRRRFFXFF...` — one letter per click, in order.
3. Open an issue in this repository titled `/run FFRRFX...` with your tokens.

A GitHub Action replays your route over `data/graph.json`, files your time
below, and closes the issue with your place. Bad routes (walking into walls,
shooting at nothing, not reaching the end) are rejected with the exact click
where you lied. One best result per player. Details: [docs/LEADERBOARD.md](docs/LEADERBOARD.md).

<!-- LEADERBOARD:BEGIN -->
| # | Player | Clicks | Date |
|---|--------|--------|------|
<!-- LEADERBOARD:END -->
