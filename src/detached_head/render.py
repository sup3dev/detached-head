"""Raycasting renderer for DETACHED HEAD.

Textured Wolfenstein-style raycast at 320x200 (vectorised with numpy over all
screen columns at once), billboard sprites with a depth test, then a x3
nearest-neighbour upscale to 960x600 and a PIL-drawn HUD (minimap, key slot,
boss health bar, CRT scanlines).
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image, ImageDraw

from . import art
from .level import DIRS, Level

RW, RH = 480, 300  # internal render resolution
SCALE = 2
FOV = 0.66  # camera plane half-width (classic ~66 degrees)

ANGLE = {"N": -math.pi / 2, "E": 0.0, "S": math.pi / 2, "W": math.pi}

# scale = sprite height as a fraction of wall height; vshift anchors sprites
# on the floor: vshift = 0.5 - scale/2 puts the sprite bottom on the floor line
SPRITE_SCALE = {
    "key": 0.5, "trophy": 0.62,
    "warden2": 1.05, "warden1": 1.05,
    "boss": 1.75, "boss3": 1.75, "boss2": 1.75, "boss1": 1.75,
}
SPRITE_VSHIFT = {
    "key": 0.12,
    "trophy": 0.5 - 0.62 / 2,
    "warden2": 0.5 - 1.05 / 2, "warden1": 0.5 - 1.05 / 2,
    "boss": 0.5 - 1.75 / 2, "boss3": 0.5 - 1.75 / 2, "boss2": 0.5 - 1.75 / 2, "boss1": 0.5 - 1.75 / 2,
}


def _bug_scale(kind: str) -> tuple[float, float]:
    if kind.startswith("bug"):
        return 0.55, 0.5 - 0.55 / 2
    return SPRITE_SCALE.get(kind, 0.6), SPRITE_VSHIFT.get(kind, 0.0)


class Renderer:
    def __init__(self, lvl: Level, textures: dict[str, np.ndarray], sprites: dict[str, Image.Image]):
        self.lvl = lvl
        self.sprites = sprites
        self.tex_names = sorted(textures)
        self.tex_index = {n: i for i, n in enumerate(self.tex_names)}
        self.tex_stack = np.stack([textures[n] for n in self.tex_names])  # (N,64,64,3)

        # floor / ceiling gradients (terminal green-grey over near-black)
        top, bottom = np.array([14, 20, 26]), np.array([24, 34, 42])
        t = np.linspace(0, 1, RH // 2)[:, None]
        self.ceiling = (top * (1 - t) + bottom * t).astype(np.uint8)
        ft, fb = np.array([40, 52, 40]), np.array([12, 16, 13])
        self.floor = (ft * (1 - t) + fb * t).astype(np.uint8)[::-1]

        yy, xx = np.mgrid[0:RH, 0:RW]
        r = np.sqrt(((xx - RW / 2) / (RW / 2)) ** 2 + ((yy - RH / 2) / (RH / 2)) ** 2)
        self.vignette = np.clip(1.08 - 0.45 * r, 0.55, 1.0).astype(np.float32)[..., None]

        self.font_hud = art._font(22, bold=True)
        self.font_small = art._font(18)
        self.font_bar = art._font(20, bold=True)

    # ------------------------------------------------------------ wall casting

    def _cast(self, px: float, py: float, ang_key: str, key: bool):
        a = ANGLE[ang_key]
        dx, dy = math.cos(a), math.sin(a)
        planex, planey = -dy * FOV, dx * FOV

        camx = 2.0 * np.arange(RW) / RW - 1.0
        rdx = dx + planex * camx
        rdy = dy + planey * camx

        mapx = np.full(RW, int(px), np.int64)
        mapy = np.full(RW, int(py), np.int64)
        with np.errstate(divide="ignore"):
            ddx = np.where(rdx == 0, 1e30, np.abs(1.0 / rdx))
            ddy = np.where(rdy == 0, 1e30, np.abs(1.0 / rdy))
        stepx = np.sign(rdx).astype(np.int64)
        stepy = np.sign(rdy).astype(np.int64)
        sdx = np.where(rdx < 0, (px - mapx) * ddx, (mapx + 1.0 - px) * ddx)
        sdy = np.where(rdy < 0, (py - mapy) * ddy, (mapy + 1.0 - py) * ddy)

        hit = np.zeros(RW, bool)
        side = np.zeros(RW, np.int8)
        texcol = np.zeros(RW, np.int64)

        grid = self.lvl
        for _ in range(96):
            moved_x = (~hit) & (sdx < sdy)
            moved_y = (~hit) & ~moved_x
            if not (moved_x.any() or moved_y.any()):
                break
            mapx = mapx + moved_x * stepx
            mapy = mapy + moved_y * stepy
            sdx = sdx + moved_x * ddx
            sdy = sdy + moved_y * ddy
            fresh = moved_x | moved_y
            tex = np.full(RW, "", dtype=object)
            for i in np.nonzero(fresh)[0]:
                cx_, cy_ = int(mapx[i]), int(mapy[i])
                c = grid.char(cx_, cy_)
                if c == "#":
                    tex[i] = grid.wall_texture(cx_, cy_)
                elif c == "G" and not key:
                    tex[i] = "gate_wall"
            newly = fresh & (tex != "")
            hit |= newly
            side[newly] = np.where(moved_x[newly], 0, 1)
            for i in np.nonzero(newly)[0]:
                texcol[i] = self.tex_index[tex[i]]
            if hit.all():
                break

        perp = np.where(side == 0, sdx - ddx, sdy - ddy)
        perp = np.clip(perp, 1e-4, 1e6)
        return perp, side, texcol, rdx, rdy

    # ------------------------------------------------------------ frame

    def frame(
        self,
        cx: int,
        cy: int,
        ang: str,
        *,
        key: bool,
        sprites: list[tuple[int, int, str]] | None = None,
        bar: tuple[str, int, int] | None = None,
    ) -> Image.Image:
        px, py = cx + 0.5, cy + 0.5
        perp, side, texcol, rdx, rdy = self._cast(px, py, ang, key)

        line_h = (RH / perp).astype(np.int64)
        half = line_h // 2
        ds = np.maximum(RH // 2 - half, 0)  # draw start per column
        de = np.minimum(RH // 2 + half, RH - 1)  # draw end per column

        wallx = np.where(side == 0, py + perp * rdy, px + perp * rdx)
        wallx = wallx - np.floor(wallx)
        texx = (wallx * art.TEX).astype(np.int64) % art.TEX
        texx = np.where((side == 0) & (rdx > 0), art.TEX - texx - 1, texx)
        texx = np.where((side == 1) & (rdy < 0), art.TEX - texx - 1, texx)

        ys = np.arange(RH)[None, :]
        span = np.clip(de[:, None] - ds[:, None] + 1, 0, None)
        texy = ((ys - ds[:, None]) * art.TEX / np.maximum(span, 1)).astype(np.int64)
        texy = np.clip(texy, 0, art.TEX - 1)
        visible = (ys >= ds[:, None]) & (ys <= de[:, None])

        sampled = self.tex_stack[texcol[:, None], texy, texx[:, None]]  # (RW,RH,3)
        sampled_t = sampled.transpose(1, 0, 2)  # -> (RH,RW,3)
        visible_t = visible.T[..., None]

        img = np.where(visible_t, sampled_t, 0).astype(np.float32)

        # floor and ceiling
        bg_rows = np.zeros((RH, 3), np.float32)
        bg_rows[: RH // 2] = self.ceiling
        bg_rows[RH // 2 :] = self.floor
        img = np.where(visible_t, img, bg_rows[:, None, :])

        fog = np.clip(1.0 - perp / 22.0, 0.40, 1.0)
        fog = np.where(side == 1, fog * 0.82, fog)
        img *= fog[None, :, None]
        img *= self.vignette
        img[2::3] *= 0.78  # CRT scanlines

        # sprites
        a = ANGLE[ang]
        dx, dy = math.cos(a), math.sin(a)
        planex, planey = -dy * FOV, dx * FOV
        for sx, sy, kind in sprites or []:
            spr = self.sprites[kind]
            sw, sh = spr.size
            sc, vshift = _bug_scale(kind)
            relx, rely = sx + 0.5 - px, sy + 0.5 - py
            invdet = 1.0 / (planex * dy - dx * planey)
            tdepth = invdet * (-planey * relx + planex * rely)
            if tdepth <= 0.12:
                continue
            tpos = invdet * (dy * relx - dx * rely)
            screen_x = int(RW / 2 * (1 + tpos / tdepth))
            spr_h = int(abs(RH / tdepth) * sc)
            spr_w = int(spr_h * sw / sh)
            if spr_h < 2 or spr_w < 2:
                continue
            center_y = RH // 2 + int(vshift * RH / tdepth)
            x0, x1 = max(0, screen_x - spr_w // 2), min(RW, screen_x - spr_w // 2 + spr_w)
            y0, y1 = max(0, center_y - spr_h // 2), min(RH, center_y - spr_h // 2 + spr_h)
            if x1 <= x0 or y1 <= y0:
                continue
            cols = np.arange(x0, x1)
            src_x = ((cols - (screen_x - spr_w // 2)) * sw / spr_w).astype(np.int64).clip(0, sw - 1)
            rows_ = np.arange(y0, y1)
            src_y = ((rows_ - (center_y - spr_h // 2)) * sh / spr_h).astype(np.int64).clip(0, sh - 1)
            rgba = np.asarray(spr, dtype=np.uint8)[src_y[:, None], src_x]  # (rows,cols,4)
            alpha = rgba[..., 3:4] > 128
            depth_ok = tdepth < perp[x0:x1]
            mask = alpha & depth_ok[None, :, None]
            sub = rgba[..., :3].astype(np.float32) * np.clip(1.0 - tdepth / 22.0, 0.40, 1.0)
            img[y0:y1, x0:x1] = np.where(mask, sub, img[y0:y1, x0:x1])

        frame = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").resize(
            (RW * SCALE, RH * SCALE), Image.NEAREST
        )
        self._hud(frame, cx, cy, ang, key, bar)
        return frame

    # ------------------------------------------------------------ HUD

    def _hud(self, frame: Image.Image, cx: int, cy: int, ang: str, key: bool, bar: tuple[str, int, int] | None) -> None:
        d = ImageDraw.Draw(frame)
        W, H = frame.size
        lvl = self.lvl

        # branch label
        d.text((16, 12), f"branch: {lvl.zone(cx, cy) if lvl.is_floor(cx, cy) else '?'}",
               font=self.font_small, fill=(139, 148, 158))

        # minimap, bottom-left
        cell = 6
        mw, mh = lvl.width * cell, lvl.height * cell
        mimg = Image.new("RGBA", (mw, mh), (13, 17, 23, 235))
        md = ImageDraw.Draw(mimg)
        tint = {"arena": (70, 20, 22, 255), "keyroom": (64, 52, 14, 255), "gate": (64, 58, 26, 255)}
        for y in range(lvl.height):
            for x in range(lvl.width):
                if not lvl.is_floor(x, y):
                    continue
                if lvl.shrine_at(x, y) is not None:
                    color = (44, 30, 64, 255)
                else:
                    color = tint.get(lvl.zone(x, y), (27, 33, 41, 255))
                if lvl.char(x, y) == "G":
                    color = (63, 185, 80, 255) if key else (248, 81, 73, 255)
                md.rectangle([x * cell, y * cell, x * cell + cell - 1, y * cell + cell - 1], fill=color)
        kx, ky = lvl.key
        if not key:
            md.rectangle([kx * cell + 1, ky * cell + 1, kx * cell + cell - 2, ky * cell + cell - 2], fill=art.AMBER)
        bx, by = lvl.boss
        md.rectangle([bx * cell, by * cell, bx * cell + cell - 1, by * cell + cell - 1], fill=art.RED)
        for cellxy, shrine in lvl.shrines.items():  # shrine anchors
            sx, sy = shrine.anchor
            color = art.AMBER if shrine.kind == "key" else (163, 113, 247)
            md.rectangle([sx * cell, sy * cell, sx * cell + cell - 1, sy * cell + cell - 1], fill=color)
        for sx, sy, kind in lvl.sprites:
            if not kind.startswith("bug"):
                continue
            md.point((sx * cell + cell // 2, sy * cell + cell // 2), fill=(200, 80, 70))
        # player: view cone + arrow pointing where the player looks
        ddx_, ddy_ = DIRS[ang]
        px_, py_ = -ddy_, ddx_  # perpendicular
        cxs, cys = cx * cell + cell // 2, cy * cell + cell // 2
        reach = cell * 5
        cone = [
            (cxs + ddx_ * reach + (px_ + ddx_) * cell, cys + ddy_ * reach + (py_ + ddy_) * cell),
            (cxs + ddx_ * (reach + cell), cys + ddy_ * (reach + cell)),
            (cxs + ddx_ * reach + (-px_ + ddx_) * cell, cys + ddy_ * reach + (-py_ + ddy_) * cell),
        ]
        md.polygon([(cxs, cys), *cone], fill=(63, 185, 80, 70))
        md.polygon(
            [(cxs + ddx_ * 7, cys + ddy_ * 7),          # tip: forward, into the view cone
             (cxs - ddx_ * 3 + px_ * 3, cys - ddy_ * 3 + py_ * 3),
             (cxs - ddx_ * 3 - px_ * 3, cys - ddy_ * 3 - py_ * 3)],
            fill=(63, 185, 80),
        )
        mx, my = 16, H - mh - 16
        frame.paste(mimg, (mx, my))
        d.rectangle([mx - 1, my - 1, mx + mw, my + mh], outline=(48, 54, 61))

        # the gun: plain pixel blaster, dead center, iron sight instead of text
        gun = Image.new("RGBA", (72, 30), (0, 0, 0, 0))
        gd = ImageDraw.Draw(gun)
        gd.rectangle([14, 4, 66, 22], fill=(58, 66, 77), outline=(88, 99, 112))
        gd.rectangle([40, 8, 71, 13], fill=(44, 51, 60))
        gd.rectangle([18, 17, 34, 29], fill=(48, 55, 65))
        gd.rectangle([46, 6, 51, 8], fill=art.GREEN)
        gd.rectangle([52, 2, 56, 5], fill=(120, 130, 142))  # iron sight
        gun_big = gun.resize((72 * 6, 30 * 6), Image.NEAREST)
        frame.paste(gun_big, ((W - 72 * 6) // 2, H - 30 * 6 + 12), gun_big)

        # key slot, bottom-right
        box_w = 210
        d.rounded_rectangle([W - box_w - 16, H - 56, W - 16, H - 16], 8,
                            fill=(13, 17, 23, 235), outline=(48, 54, 61))
        if key:
            badge = self.sprites["key"].resize((40, 46), Image.NEAREST)
            frame.paste(badge, (W - box_w + 2, H - 54), badge)
            d.text((W - box_w + 52, H - 44), "THE KEY", font=self.font_hud, fill=art.GREEN)
        else:
            d.text((W - box_w + 12, H - 44), "no key", font=self.font_hud, fill=(90, 98, 106))

        # enemy bar (arena boss / shrine warden)
        if bar is not None:
            label, hp, hp_max = bar
            bw, bh = 460, 44
            bx, by = (W - bw) // 2, 14
            d.rounded_rectangle([bx, by, bx + bw, by + bh], 8, fill=(13, 17, 23, 235), outline=art.RED)
            d.text((W // 2, by + 12), label, font=self.font_bar, fill=art.RED, anchor="ma")
            seg_w = (bw - 40 - (hp_max - 1) * 3) // hp_max
            for i in range(hp_max):
                sx0 = bx + 20 + i * (seg_w + 3)
                d.rectangle([sx0, by + 30, sx0 + seg_w, by + 38],
                            fill=art.RED if i < hp else (60, 28, 26))
