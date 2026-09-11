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
    ("hub_n", 20, 21, "N", False, None),
    ("hub_e", 20, 21, "E", False, None),
    ("gate_locked", 20, 11, "N", False, None),
    ("gate_open", 20, 11, "N", True, None),
    ("arena_boss4", 20, 5, "N", True, 4),
    ("arena_boss1", 20, 5, "N", True, 1),
    ("keyroom", 6, 12, "W", False, None),
    ("bug", 5, 11, "E", False, None),
]
for name, x, y, a, key, hp in cases:
    sprites = visible_sprites(lvl, key)
    if hp is not None:
        sprites = [s for s in sprites if s[2] != "key"] + [(*boss, "boss" if hp == 4 else f"boss{hp}")]
    img = r.frame(x, y, a, key=key, hp=hp, sprites=sprites)
    img.save(out / f"{name}.png")
    print("ok", name)
