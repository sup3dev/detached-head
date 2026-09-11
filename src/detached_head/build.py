"""Build orchestration: level -> graph -> frames -> playable repository."""

from __future__ import annotations

import argparse
import os
import time
from multiprocessing import get_context
from pathlib import Path

from . import art, emit
from .graph import build_graph, validate
from .level import load, visible_sprites
from .render import Renderer

_R: Renderer | None = None


def _init_worker(map_path: str) -> None:
    global _R
    lvl = load(map_path)
    _R = Renderer(lvl, art.make_textures(), art.make_sprites())


def _render_job(job: tuple) -> str:
    nid, cx, cy, ang, key, hp, kind, out_path, fmt = job
    lvl = _R.lvl
    sprites = visible_sprites(lvl, bool(key))
    bar = None
    if kind == "arena":
        sprites = [(*lvl.boss, "boss" if hp == 4 else f"boss{hp}")]
        bar = ("THE DEBT", hp, 4)
    elif kind == "shrine":
        shrine = lvl.shrine_at(cx, cy)
        ax, ay = shrine.anchor
        if hp > 0:
            sprites.append((ax, ay, "warden2" if hp == 2 else "warden1"))
            bar = ("THE WARDEN", hp, 2)
        else:
            sprites.append((ax, ay, "key" if shrine.kind == "key" else "trophy"))
    img = _R.frame(cx, cy, ang, key=bool(key), sprites=sprites, bar=bar)
    if fmt == "webp":
        img.save(out_path, "WEBP", quality=82, method=4)
    else:
        img.save(out_path)
    return nid


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build the DETACHED HEAD repository")
    ap.add_argument("--out", default=".", help="repository root to emit into")
    ap.add_argument("--map", default=None, help="path to level/map.txt (default: <out>/level/map.txt)")
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument("--limit", type=int, default=0, help="render only the first N frames (smoke run)")
    ap.add_argument("--format", choices=("webp", "png"), default="webp")
    ap.add_argument("--no-preview", action="store_true", help="skip the _preview HTML mirror")
    ap.add_argument("--skip-render", action="store_true", help="emit markdown only, frames must exist")
    args = ap.parse_args(argv)

    root = Path(args.out).resolve()
    map_path = Path(args.map).resolve() if args.map else root / "level" / "map.txt"
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)

    lvl = load(map_path)
    graph = build_graph(lvl)
    errors = validate(graph, lvl)
    if errors:
        for e in errors:
            print("GRAPH ERROR:", e)
        return 1
    n_nodes = len(graph["nodes"])
    print(f"graph ok: {n_nodes} nodes (start {graph['start']})")

    fmt = args.format
    art.make_title().save(assets / f"title.{fmt}", "WEBP" if fmt == "webp" else None, quality=88, method=4)
    art.make_win().save(assets / f"win.{fmt}", "WEBP" if fmt == "webp" else None, quality=88, method=4)
    art.make_minimap_banner(lvl).save(assets / f"map.{fmt}", "WEBP" if fmt == "webp" else None, quality=88, method=4)

    todo = [
        (nid, n["cell"][0], n["cell"][1], n["angle"], n["key"], n["hp"], n["kind"],
         assets / f"{nid}.{fmt}", fmt)
        for nid, n in graph["nodes"].items()
        if n["kind"] != "win"
    ]
    if args.limit:
        todo = todo[: args.limit]

    if not args.skip_render:
        t0 = time.time()
        ctx = get_context("spawn")
        done = 0
        with ctx.Pool(args.workers, initializer=_init_worker, initargs=(str(map_path),)) as pool:
            for _ in pool.imap_unordered(_render_job, todo, chunksize=16):
                done += 1
                if done % 500 == 0:
                    print(f"  rendered {done}/{len(todo)} ({time.time() - t0:.0f}s)")
        print(f"rendered {len(todo)} frames in {time.time() - t0:.1f}s")

    emit.emit_markdown(graph, lvl, root, fmt)
    emit.emit_leaderboard(root)
    emit.emit_readme(graph, lvl, root, fmt)
    if not args.no_preview:
        emit.emit_preview(graph, lvl, root, fmt)
    print(f"emitted game/, data/graph.json, README.md, LEADERBOARD.md"
          f"{'' if args.no_preview else ', _preview/'}")

    total = sum(f.stat().st_size for f in assets.iterdir() if f.is_file())
    print(f"assets: {len(list(assets.iterdir()))} files, {total / 1e6:.1f} MB")
    print(f"play locally: open _preview/{graph['start']}.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
