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

FLOOR_CHARS = set("fhdkgrA@Knuvwp.GM")
WALL_CHARS = set("#%~!")

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
class Level:
    grid: list[str]
    width: int
    height: int
    spawn: tuple[int, int] = (0, 0)
    gate: tuple[int, int] = (0, 0)
    key: tuple[int, int] = (0, 0)
    boss: tuple[int, int] = (0, 0)
    sprites: list[tuple[int, int, str]] = field(default_factory=list)
    _tex_cache: dict[tuple[int, int], str] = field(default_factory=dict, repr=False)

    def char(self, x: int, y: int) -> str:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.grid[y][x]
        return "#"

    def is_floor(self, x: int, y: int) -> bool:
        return self.char(x, y) in FLOOR_CHARS

    def is_arena(self, x: int, y: int) -> bool:
        return self.char(x, y) in "AM"

    def passable(self, x: int, y: int, key: bool) -> bool:
        c = self.char(x, y)
        if c not in FLOOR_CHARS:
            return False
        if c == "G":  # the merge gate only opens for the key holder
            return key
        return True  # stepping onto the key cell is what grants the key

    def zone(self, x: int, y: int) -> str:
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
    # K is both a pickup target and a sprite anchor; M is the boss anchor
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if c == "K":
                lvl.key = (x, y)
                lvl.sprites.append((x, y, "key"))
            elif c == "M":
                lvl.boss = (x, y)
                lvl.sprites.append((x, y, "boss"))
    return lvl


def visible_sprites(lvl: Level, key: bool) -> list[tuple[int, int, str]]:
    """World sprites for a frame in the given key state (the key vanishes once taken)."""
    out = []
    for x, y, kind in lvl.sprites:
        if kind == "key" and key:
            continue
        if kind == "boss":
            continue  # the boss is drawn by the arena renderer, per hp state
        out.append((x, y, kind))
    return out
