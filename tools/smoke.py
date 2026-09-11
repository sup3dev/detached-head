"""Smoke-render a handful of representative frames to PNG for visual inspection."""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from detached_head.art import make_sprites, make_textures
from detached_head.level import load, visible_sprites
from detached_head.render import Renderer

lvl = load(ROOT / "level" / "map.txt")
r = Renderer(lvl, make_textures(), make_sprites())
out = ROOT / "tools" / "_scratch"
out.mkdir(exist_ok=True)

boss = lvl.boss
cases = [
    ("hub_n", 20, 21, "N", False, None, None),
    ("hub_e", 20, 21, "E", False, None, None),
    ("gate_locked", 20, 11, "N", False, None, None),
    ("gate_open", 20, 11, "N", True, None, None),
    ("arena_boss4", 20, 5, "N", True, 4, "arena"),
    ("arena_boss1", 20, 5, "N", True, 1, "arena"),
    ("shrine_warden2", 5, 12, "W", False, 2, "shrine"),
    ("shrine_warden1", 5, 12, "W", False, 1, "shrine"),
    ("shrine_cleared", 4, 11, "S", False, 0, "shrine"),
    ("bug", 6, 11, "E", False, None, None),
]
for name, x, y, a, key, hp, kind in cases:
    sprites = visible_sprites(lvl, key)
    bar = None
    if kind == "arena":
        sprites = [(*boss, "boss" if hp == 4 else f"boss{hp}")]
        bar = ("THE DEBT", hp, 4)
    elif kind == "shrine":
        shrine = lvl.shrine_at(x, y)
        ax, ay = shrine.anchor
        if hp > 0:
            sprites.append((ax, ay, "warden2" if hp == 2 else "warden1"))
            bar = ("THE WARDEN", hp, 2)
        else:
            sprites.append((ax, ay, "key" if shrine.kind == "key" else "trophy"))
    img = r.frame(x, y, a, key=key, sprites=sprites, bar=bar)
    img.save(out / f"{name}.png")
    print("ok", name)
