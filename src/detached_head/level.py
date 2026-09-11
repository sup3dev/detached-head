"""Level parsing for DETACHED HEAD.

The level is a hand-authored ASCII map (level/map.txt). Every character is
either a wall, a walkable floor cell (which also encodes its git-branch
zone), or a floor cell carrying a sprite. See docs/DESIGN.md for the legend.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Facing order is clockwise: N, E, S, W.
DIRS: dict[str, tuple[int, int]] = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "W": (-1, 0)}
ORDER = "NESW"
LEFT = {"N": "W", "W": "S", "S": "E", "E": "N"}
RIGHT = {"N": "E", "E": "S", "S": "W", "W": "N"}

# zone id -> branch name shown to the player
ZONES: dict[str, str] = {
    "main": "main",
    "feature": "feature/dark-mode",
    "hotfix": "hotfix/payroll",
    "refactor": "refactor/auth",
    "docs": "docs/README.md",
    "keyroom": "feature/approvals",
    "gate": "release",
    "arena": "prod",
}

FLOOR_CHARS = set("fhdkgrA@Knuvwp.GMq")
WALL_CHARS = set("#%~!")
SHRINE_CHARS = set("qK")  # shrine floor and the guarded key cell

# sprite char -> sprite kind (art.py keys)
SPRITE_KINDS = {
    "n": "bug_red",
    "u": "bug_amber",
    "v": "bug_purple",
    "w": "bug_green",
    "p": "bug_cyan",
    "K": "key",
    "M": "boss",
}


@dataclass
class Shrine:
    """A warden-guarded chamber. Entering from outside spawns the warden at
    full health; its state lives only inside this chamber's sub-graph."""

    name: str
    cells: set[tuple[int, int]]
    anchor: tuple[int, int]  # the guarded cell: 'K' (key) or 'T' (trophy)
    kind: str  # "key" | "trophy"


@dataclass
class Level:
    grid: list[str]
    width: int
    height: int
    spawn: tuple[int, int] = (0, 0)
    gate: tuple[int, int] = (0, 0)
    key: tuple[int, int] = (0, 0)
    boss: tuple[int, int] = (0, 0)
    sprites: list[tuple[int, int, str]] = field(default_factory=list)
    shrines: dict[tuple[int, int], Shrine] = field(default_factory=dict)  # cell -> shrine
    imps: dict[str, tuple[int, int, str]] = field(default_factory=dict)  # zone -> (x, y, kind)
    _tex_cache: dict[tuple[int, int], str] = field(default_factory=dict, repr=False)

    def imp_zone(self, x: int, y: int) -> str | None:
        """The wing whose bug can be shot from this cell (None elsewhere)."""
        return self.zone(x, y) if self.zone(x, y) in self.imps else None

    def char(self, x: int, y: int) -> str:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return "#"

    def is_floor(self, x: int, y: int) -> bool:
        return self.char(x, y) in FLOOR_CHARS

    def is_arena(self, x: int, y: int) -> bool:
        return self.char(x, y) in "AM"

    def passable(self, x: int, y: int, key: bool) -> bool:
        """Normal-world passability. Shrine mechanics (warden, guarded cells)
        are resolved by graph.py; here the guarded cells are simply closed."""
        c = self.char(x, y)
        if c not in FLOOR_CHARS or c in "KT":
            return False
        if c == "G":  # the gate only opens for the key holder
            return key
        return True

    def shrine_at(self, x: int, y: int) -> Shrine | None:
        return self.shrines.get((x, y))

    def zone(self, x: int, y: int) -> str:
        shrine = self.shrines.get((x, y))
        if shrine is not None:
            return shrine.name
        c = self.char(x, y)
        if c == "@":
            return "main"
        if c in "f":
            return "feature"
        if c == "h":
            return "hotfix"
        if c == "r":
            return "refactor"
        if c == "d":
            return "docs"
        if c == "k":
            return "keyroom"
        if c in "gG":
            return "gate"
        if c in "AM":
            return "arena"
        # sprite cells inherit a zone
        sprite_zone = {"n": "main", "u": "feature", "v": "hotfix", "w": "refactor", "p": "docs"}
        return sprite_zone.get(c, "main")

    def wall_texture(self, x: int, y: int) -> str:
        """Texture key for a wall cell, derived from what the wall encloses."""
        cached = self._tex_cache.get((x, y))
        if cached:
            return cached
        if self.char(x, y) in FLOOR_CHARS:
            return ""
        # sample the 8-neighbourhood: the wall borrows the mood of nearby zones
        zones = {self.zone(nx, ny) for nx, ny in _neighbours(x, y) if self.is_floor(nx, ny)}
        if "arena" in zones:
            tex = "conflict"
        elif "keyroom" in zones:
            tex = "log"
        elif "hotfix" in zones:
            tex = "warn"
        elif "gate" in zones:
            tex = "gate_wall"
        elif "feature" in zones or "docs" in zones:
            tex = "log"
        elif "refactor" in zones:
            tex = "conflict"
        else:
            tex = "code"
        self._tex_cache[(x, y)] = tex
        return tex


def _neighbours(x: int, y: int):
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                yield x + dx, y + dy


def _discover_shrines(lvl: Level) -> None:
    """Flood-fill shrine chambers (q/K/T cells) and classify them."""
    visited: set[tuple[int, int]] = set()
    found: list[Shrine] = []
    for y in range(lvl.height):
        for x in range(lvl.width):
            if (x, y) in visited or lvl.char(x, y) not in SHRINE_CHARS:
                continue
            comp: set[tuple[int, int]] = set()
            stack = [(x, y)]
            while stack:
                cx, cy = stack.pop()
                if (cx, cy) in comp or lvl.char(cx, cy) not in SHRINE_CHARS:
                    continue
                comp.add((cx, cy))
                stack.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
            visited |= comp
            key_cells = [c for c in comp if lvl.char(*c) == "K"]
            trophy_cells = [c for c in comp if lvl.char(*c) == "T"]
            if key_cells:
                found.append(Shrine("the shrine of the key", comp, key_cells[0], "key"))
            elif trophy_cells:
                found.append(Shrine("", comp, trophy_cells[0], "trophy"))
    trophy_names: list[str] = []
    trophy_idx = 0
    found.sort(key=lambda s: (s.anchor[1], s.anchor[0]))
    for shrine in found:
        if shrine.kind == "trophy":
            shrine.name = trophy_names[min(trophy_idx, len(trophy_names) - 1)]
            trophy_idx += 1
        for cell in shrine.cells:
            lvl.shrines[cell] = shrine


def load(path) -> Level:
    rows = [line.rstrip("\n") for line in open(path, encoding="utf-8") if line.strip()]
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ValueError(f"map rows must all be {width} chars wide")
    lvl = Level(grid=rows, width=width, height=len(rows))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "@":
                lvl.spawn = (x, y)
            elif c == "G":
                lvl.gate = (x, y)
            if c in SPRITE_KINDS and c not in "KM":
                lvl.sprites.append((x, y, SPRITE_KINDS[c]))
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "K":
                lvl.key = (x, y)
            elif c == "M":
                lvl.boss = (x, y)
                lvl.sprites.append((x, y, "boss"))
    _discover_shrines(lvl)
    for x, y, kind in lvl.sprites:
        if kind.startswith("bug"):
            lvl.imps[lvl.zone(x, y)] = (x, y, kind)
    return lvl


def visible_sprites(lvl: Level, key: bool) -> list[tuple[int, int, str]]:
    """Static world sprites for a frame (bugs; the boss, the oldest bug, the
    key and corpses are placed by the arena/shrine/imp renderers)."""
    return [s for s in lvl.sprites if s[2].startswith("bug")]
