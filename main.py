#!/usr/bin/env python3
"""make.fun daily news-image entry.

Renders a 1024x1024 cream editorial front page ("broadsheet") as an RGB PNG
using only the Python standard library.  Uses fntdata.DATA_B64 (glyph atlas)
and land.json (world land polygons) read-only.

Run:  MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import base64
import json
import os
import sys
import zlib

# Ensure this script's own directory is importable regardless of the current
# working directory and even under the -P (PYTHONSAFEPATH) flag, which does
# not add the script directory to sys.path.
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from fntdata import DATA_B64

W = 1024
H = 1024

# --------------------------------------------------------------------------
# palette
# --------------------------------------------------------------------------
PAPER = (247, 244, 236)
INK = (22, 24, 28)
INK2 = (84, 86, 92)
DECK_INK = (58, 60, 66)
RULES = (32, 34, 38)
RED = (176, 30, 38)
OCEAN = (208, 222, 231)
LAND = (205, 200, 185)
LAND_EDGE = (126, 123, 112)
GOLD = (231, 199, 112)
WHITE = (255, 255, 255)
GREEN = (26, 112, 74)
ORANGE = (196, 106, 22)
BLUE_SEA = (30, 74, 122)
TEAL = (42, 96, 118)
GREY = (118, 120, 126)
DARKGREY = (60, 62, 68)
YELLOW = (238, 200, 74)
SMOKE = (150, 152, 158)


# --------------------------------------------------------------------------
# font / atlas
# --------------------------------------------------------------------------
def load_atlas():
    return json.loads(zlib.decompress(base64.b64decode(DATA_B64)))


def prep_fonts(atlas):
    fonts = {}
    for key, f in atlas.items():
        gw = {}
        gh = {}
        for ch, b64 in f["g"].items():
            gw[ch] = zlib.decompress(base64.b64decode(b64))
            gh[ch] = f["m"][ch]
        fonts[key] = {
            "px": f["px"],
            "asc": f["asc"],
            "desc": f["desc"],
            "lh": f["asc"] + f["desc"],
            "m": f["m"],
            "g": gw,
            "gm": gh,
        }
    return fonts


# --------------------------------------------------------------------------
# canvas
# --------------------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.buf = bytearray(bg * (w * h))

    # ---- flat fills -------------------------------------------------------
    def fill_rect(self, x, y, w, h, color):
        if w <= 0 or h <= 0:
            return
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x0 >= x1 or y0 >= y1:
            return
        r, g, b = color
        buf = self.buf
        row = bytes((r, g, b)) * (x1 - x0)
        off = y0 * self.w * 3 + x0 * 3
        span = (x1 - x0) * 3
        for _ in range(y0, y1):
            buf[off:off + span] = row
            off += self.w * 3

    def hline(self, x, y, w, color, thick=1):
        self.fill_rect(x, y, w, thick, color)

    def vline(self, x, y, h, color, thick=1):
        self.fill_rect(x, y, thick, h, color)

    def frame(self, x, y, w, h, color):
        self.fill_rect(x, y, w, 1, color)
        self.fill_rect(x, y + h - 1, w, 1, color)
        self.fill_rect(x, y, 1, h, color)
        self.fill_rect(x + w - 1, y, 1, h, color)

    def rounded_panel(self, x, y, w, h, color, radius=10):
        self.fill_rect(x + radius, y, w - 2 * radius, h, color)
        self.fill_rect(x, y + radius, w, h - 2 * radius, color)
        for i in range(radius):
            dy = radius - i
            dx = int(round(radius - (radius * radius - dy * dy) ** 0.5))
            self.fill_rect(x + dx, y + i, w - 2 * dx, 1, color)
            self.fill_rect(x + dx, y + h - 1 - i, w - 2 * dx, 1, color)

    # ---- alpha blits ------------------------------------------------------
    def blit(self, bm, bw, bh, px, py, color):
        """Blit an 8-bit alpha bitmap blended with fg=color."""
        if px >= self.w or py >= self.h or px + bw <= 0 or py + bh <= 0:
            return
        cx0 = 0 if px >= 0 else -px
        cy0 = 0 if py >= 0 else -py
        cx1 = min(bw, self.w - px) if px + bw > self.w else bw
        cy1 = min(bh, self.h - py) if py + bh > self.h else bh
        if cx0 >= cx1 or cy0 >= cy1:
            return
        fr, fg, fb = color
        buf = self.buf
        stride = self.w * 3
        for yy in range(cy0, cy1):
            brow = yy * bw
            o = (py + yy) * stride + (px + cx0) * 3
            for xx in range(cx0, cx1):
                a = bm[brow + xx]
                if a:
                    if a == 255:
                        buf[o] = fr
                        buf[o + 1] = fg
                        buf[o + 2] = fb
                    else:
                        ia = 255 - a
                        buf[o] = (fr * a + buf[o] * ia) // 255
                        buf[o + 1] = (fg * a + buf[o + 1] * ia) // 255
                        buf[o + 2] = (fb * a + buf[o + 2] * ia) // 255
                o += 3

    # ---- circles / lines --------------------------------------------------
    def disc(self, cx, cy, r, color):
        r2 = r * r
        for yy in range(cy - r, cy + r + 1):
            if yy < 0 or yy >= self.h:
                continue
            dy = yy - cy
            dxmax = int((r2 - dy * dy) ** 0.5)
            self.fill_rect(cx - dxmax, yy, 2 * dxmax + 1, 1, color)

    def ring(self, cx, cy, r, color, thick=1):
        ri = r - thick
        ri2 = ri * ri
        r2 = r * r
        for yy in range(cy - r, cy + r + 1):
            if yy < 0 or yy >= self.h:
                continue
            dy = yy - cy
            dxo = int((r2 - dy * dy) ** 0.5)
            if abs(dy) < ri:
                dxi = int((ri2 - dy * dy) ** 0.5)
                self.fill_rect(cx - dxo, yy, dxo - dxi + 1, 1, color)
                self.fill_rect(cx + dxi, yy, dxo - dxi + 1, 1, color)
            else:
                self.fill_rect(cx - dxo, yy, 2 * dxo + 1, 1, color)

    def line(self, x0, y0, x1, y1, color, thick=1):
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy))
        if steps == 0:
            self.fill_rect(x0, y0, thick, thick, color)
            return
        for i in range(steps + 1):
            x = x0 + dx * i // steps
            y = y0 + dy * i // steps
            self.fill_rect(x, y, thick, thick, color)

    def scanline_polygon(self, pts, color, edge=None, clip=None):
        """Even-odd scanline polygon fill over the polygon bbox only."""
        n = len(pts)
        if n < 3:
            return
        ys = [p[1] for p in pts]
        y0 = max(0, int(min(ys)))
        y1 = min(self.h - 1, int(max(ys)) + 1)
        if clip is not None:
            cx0, cy0, cx1, cy1 = clip
            y0 = max(y0, cy0)
            y1 = min(y1, cy1)
        edges = []
        for i in range(n):
            ax, ay = pts[i]
            bx, by = pts[(i + 1) % n]
            if ay != by:
                edges.append((ax, ay, bx, by))
        r, g, b = color
        for yy in range(y0, y1 + 1):
            sy = yy + 0.5
            xs = []
            for ax, ay, bx, by in edges:
                if (ay <= sy < by) or (by <= sy < ay):
                    t = (sy - ay) / (by - ay)
                    xs.append(ax + t * (bx - ax))
            if not xs:
                continue
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                xa = int(xs[i] + 0.5)
                xb = int(xs[i + 1] + 0.5)
                if clip is not None:
                    cx0, cy0, cx1, cy1 = clip
                    if xa < cx0:
                        xa = cx0
                    if xb > cx1:
                        xb = cx1
                if xb <= xa:
                    xb = xa + 1
                self.fill_rect(xa, yy, xb - xa, 1, color)
                if edge is not None:
                    self.fill_rect(xa, yy, 1, 1, edge)
                    self.fill_rect(xb - 1, yy, 1, 1, edge)


# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------
class Text:
    def __init__(self, fonts):
        self.fonts = fonts

    def width(self, font, s):
        m = self.fonts[font]["m"]
        return sum(m[c][4] for c in s if c in m)

    def draw(self, cv, font, s, x, ytop, color):
        f = self.fonts[font]
        m = f["m"]
        g = f["g"]
        gm = f["gm"]
        pen = float(x)
        for ch in s:
            info = m.get(ch)
            if info is None:
                continue
            bm = g.get(ch)
            if bm is not None:
                gw, gh, bx, by, adv = info
                cv.blit(bm, gw, gh, int(round(pen)) + bx, ytop + by, color)
            pen += info[4]

    def fit(self, font, s, maxw):
        """Wrap a string to the given pixel width at word boundaries.

        Never inserts an ellipsis and never drops words: if a single word is
        wider than maxw it is still kept whole on its own line (the caller is
        responsible for resolving any resulting overflow, not by cutting text).
        Returns a list of lines covering every word of s.
        """
        if maxw <= 0:
            return [s]
        m = self.fonts[font]["m"]

        def word_w(ws):
            acc = 0.0
            for ch in ws:
                acc += m[ch][4] if ch in m else 0.0
            return acc

        words = s.split(" ")
        lines = []
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            if not cur or word_w(trial) <= maxw:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        return lines

    def fit_lines(self, font, s, widths):
        """Wrap a string where line i uses widths[i] (last width repeats).

        Wraps purely at word boundaries; never inserts an ellipsis and never
        drops a word.  Used so a card headline's first line can stop short of
        the icon while later lines use the full column width.
        """
        if not widths:
            return self.fit(font, s, 40)
        m = self.fonts[font]["m"]

        def word_w(ws):
            acc = 0.0
            for ch in ws:
                acc += m[ch][4] if ch in m else 0.0
            return acc

        words = s.split(" ")
        lines = []
        cur = ""
        for word in words:
            trial = word if not cur else cur + " " + word
            limit = widths[min(len(lines), len(widths) - 1)]
            if not cur or word_w(trial) <= limit:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        return lines

    def wrap(self, font, s, maxw, maxlines):
        """Wrap to at most maxlines at word boundaries (no ellipsis, no cut).

        Content may only be preserved up to maxlines as requested; this helper
        never truncates with an ellipsis.  Callers that must show every word
        pass a maxlines large enough to hold the full wrap.
        """
        lines = self.fit(font, s, maxw)
        if maxlines and len(lines) > maxlines:
            lines = lines[:maxlines]
        return lines

    def layout_block(self, font, s, x, maxw, ytop, max_bottom,
                     maxlines=3, leading=None, min_leading=None):
        """Plan a wrapped text block that fits inside a card's bottom edge.

        Words are never dropped.  To avoid overflow the line spacing (leading)
        is reduced from `leading` (default the font line height) down to
        `min_leading` (default asc+desc-3).  Returns (lines, leading, bottom).
        """
        if leading is None:
            leading = self.fonts[font]["lh"]
        if min_leading is None:
            min_leading = self.fonts[font]["lh"] - 3
        lines = self.fit(font, s, maxw)
        if maxlines and len(lines) > maxlines:
            lines = lines[:maxlines]
        n = len(lines)
        lead = float(leading)
        if n > 1 and max_bottom is not None:
            avail = max_bottom - ytop
            if avail < n * lead:
                lead = max(min_leading, avail / n)
        bottom = ytop + n * lead
        return lines, lead, bottom

    def draw_block(self, cv, font, lines, x, ytop, leading, color):
        """Draw already-wrapped lines; returns the bottom edge of the block."""
        for i, ln in enumerate(lines):
            self.draw(cv, font, ln, x, int(round(ytop + i * leading)), color)
        return ytop + len(lines) * leading

    def block_overflow(self, font, s, x, maxw, ytop, max_bottom,
                       maxlines=3, leading=None):
        """Programmatic check: returns (overflowed, last_right, bottom, box_r)."""
        lines, lead, bottom = self.layout_block(
            font, s, x, maxw, ytop, max_bottom, maxlines=maxlines,
            leading=leading)
        last_right = x + (self.width(font, lines[-1]) if lines else 0)
        bad = (last_right > x + maxw) or (max_bottom is not None and bottom > max_bottom)
        return bad, last_right, bottom, x + maxw

# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------
def star(cv, cx, cy, ro, ri, points, color):
    pts = []
    for i in range(points * 2):
        ang = -1.5707963 + i * 3.14159265 / points
        r = ro if i % 2 == 0 else ri
        pts.append((cx + r * __import__("math").cos(ang), cy + r * __import__("math").sin(ang)))
    cv.scanline_polygon(pts, color)


def chip_with_text(cv, txt, font, s, x, ytop, padx, pady, bg, fg):
    w = txt.width(font, s)
    fh = txt.fonts[font]["lh"]
    box_h = fh + 2 * pady
    cv.fill_rect(x, ytop, int(w + 2 * padx), box_h, bg)
    txt.draw(cv, font, s, x + padx, ytop + pady, fg)
    return box_h


# --------------------------------------------------------------------------
# map
# --------------------------------------------------------------------------
def load_land(path):
    with open(path, "r") as fh:
        return json.load(fh)


def draw_map(cv, txt, land, x, y, w, h):
    cv.rounded_panel(x, y, w, h, OCEAN, radius=14)
    cv.frame(x, y, w, h, LAND_EDGE)
    mw = w - 2
    mh = h - 2
    # ocean rectangle bounds (inside the frame)
    ox0, oy0 = x + 1, y + 1
    ox1, oy1 = x + w - 1, y + h - 1
    for poly in land:
        lats = [lat for _lon, lat in poly]
        if not lats:
            continue
        # skip any polygon whose points are all below latitude -58
        if max(lats) < -58.0:
            continue
        pts = []
        for lon, lat in poly:
            mx = x + 1 + (lon + 170.0) / 350.0 * mw
            my = y + 1 + (72.0 - lat) / 128.0 * mh
            pts.append((mx, my))
        if len(pts) >= 3:
            cv.scanline_polygon(pts, LAND, edge=LAND_EDGE,
                                clip=(ox0, oy0, ox1, oy1))
    return mw, mh


PINS = [
    (1, 36.5, 45.3), (2, 30.5, 50.45), (3, 121.0, 14.6), (4, 114.06, 22.54),
    (5, 56.5, 26.5), (6, 50.5, 26.2), (7, -80.6, 28.5), (8, 139.7, 35.7),
    (9, -77.0, -12.0), (10, 30.7, 36.9), (11, 28.0, -26.2), (12, -77.04, 38.9),
]

PIN_RED = RED
PIN_RED_EDGE = (122, 18, 24)


def draw_pins(cv, txt, x, y, w, h):
    mw = w - 2
    mh = h - 2
    lh = txt.fonts["micro"]["lh"]
    proj = []
    for num, lon, lat in PINS:
        px = x + 1 + (lon + 170.0) / 350.0 * mw
        py = y + 1 + (72.0 - lat) / 128.0 * mh
        proj.append([num, px, py, px, py])
    for _ in range(24):
        moved = False
        for i in range(len(proj)):
            for j in range(i + 1, len(proj)):
                ax, ay = proj[i][1], proj[i][2]
                bx, by = proj[j][1], proj[j][2]
                dx = bx - ax
                dy = by - ay
                d2 = dx * dx + dy * dy
                if d2 < 400.0:
                    d = d2 ** 0.5
                    if d < 0.01:
                        dx, dy, d = 1.0, 0.0, 1.0
                    push = (20.0 - d) / 2.0 + 1.0
                    ux, uy = dx / d, dy / d
                    proj[i][1] -= ux * push
                    proj[i][2] -= uy * push
                    proj[j][1] += ux * push
                    proj[j][2] += uy * push
                    moved = True
        if not moved:
            break
    for num, sx, sy, tx, ty in proj:
        cxi = int(round(sx))
        cyi = int(round(sy))
        txi = int(round(tx))
        tyi = int(round(ty))
        if abs(cxi - txi) > 1 or abs(cyi - tyi) > 1:
            cv.line(cxi, cyi, txi, tyi, INK, 1)
    for num, sx, sy, tx, ty in proj:
        cxi = int(round(sx))
        cyi = int(round(sy))
        cv.disc(cxi, cyi, 8, RED)
        cv.ring(cxi, cyi, 8, PIN_RED_EDGE, 1)
        s = str(num)
        sw = txt.width("micro", s)
        txt.draw(cv, "micro", s, cxi - sw / 2, cyi - lh // 2, WHITE)


# --------------------------------------------------------------------------
# icons (flat vector, ~46px, top-right of each card)
# --------------------------------------------------------------------------
def icon_flags(cv, x, y, s):
    pole_top = y + 6
    for i, col in enumerate((GREEN, RED, GREEN)):
        px = x + i * (s // 3) + 4
        cv.fill_rect(px, pole_top, 2, s - 12, DARKGREY)
        cv.fill_rect(px + 2, pole_top + 2, s // 4, s // 4, col)
        cv.fill_rect(px + 2, pole_top + 2, s // 4, 1, INK)


def icon_table(cv, x, y, s):
    cx = x + s // 2
    cy = y + s // 2 + 4
    r = s // 5
    pos = [(-s // 3, -s // 4), (0, -s // 3), (s // 3, -s // 4)]
    for dx, dy in pos:
        hx = cx + dx
        hy = cy + dy
        cv.disc(hx, hy - r, r - 2, INK2)
        cv.fill_rect(hx - r + 2, hy - 2, 2 * (r - 2), 2 * (r - 2), INK)
    cv.fill_rect(x + 4, cy + 8, s - 8, 4, GREY)


def icon_ship(cv, x, y, s):
    hull_y = y + s - 18
    pts = [(x + 4, hull_y), (x + s - 4, hull_y),
           (x + s - 12, hull_y + 12), (x + 12, hull_y + 12)]
    cv.scanline_polygon(pts, INK)
    cv.fill_rect(x + s // 2 - 4, hull_y - 12, 8, 12, INK2)
    cv.fill_rect(x + s // 2 - 8, hull_y - 16, 16, 4, RED)
    cv.fill_rect(x + 4, hull_y + 14, s - 8, 2, BLUE_SEA)
    mine_x = x + s - 10
    mine_y = y + 12
    cv.disc(mine_x, mine_y, 6, DARKGREY)
    for i in range(8):
        import math as _m
        a = i * 0.785398
        ex = mine_x + int(9 * _m.cos(a))
        ey = mine_y + int(9 * _m.sin(a))
        cv.line(mine_x, mine_y, ex, ey, INK, 1)


def icon_radar(cv, x, y, s):
    cx = x + s // 2
    cy = y + s - 10
    cv.disc(cx, cy, s // 2 - 6, GREY)
    cv.disc(cx, cy, s // 2 - 8, DARKGREY)
    r = s // 2 - 6
    for i in range(3):
        import math as _m
        a = 0.5 + i * 0.6
        cv.line(cx, cy, cx + int(r * _m.cos(-a)), cy + int(r * _m.sin(-a)), GOLD, 1)
    cv.fill_rect(cx - 3, cy - r - 6, 6, 6, INK)


def icon_rocket(cv, x, y, s):
    bx = x + 8
    by = y + s - 8
    tx = x + s - 14
    ty = y + 8
    cv.line(bx, by, tx, ty, GREY, 6)
    cv.line(bx + 6, by + 4, tx + 6, ty + 4, INK, 2)
    hp = [(tx, ty - 6), (tx + 8, ty + 4), (tx - 2, ty + 6)]
    cv.scanline_polygon(hp, RED)
    for i in range(6):
        import math as _m
        a = i * 1.047
        cv.line(bx, by, bx + int(10 * _m.cos(a)), by + int(10 * _m.sin(a)), GOLD if i % 2 else ORANGE, 2)


def icon_jets(cv, x, y, s):
    def jet(jx, jy, sc, col):
        pts = [(jx, jy - 6 * sc), (jx + 3 * sc, jy - 2 * sc), (jx + 14 * sc, jy + 2 * sc),
               (jx + 14 * sc, jy + 4 * sc), (jx + 2 * sc, jy + 2 * sc),
               (jx + 4 * sc, jy + 8 * sc), (jx, jy + 7 * sc), (jx - 4 * sc, jy + 8 * sc),
               (jx - 2 * sc, jy + 2 * sc), (jx - 14 * sc, jy + 4 * sc),
               (jx - 14 * sc, jy + 2 * sc), (jx - 3 * sc, jy - 2 * sc)]
        cv.scanline_polygon(pts, col)

    jet(x + 8, y + 14, 1.0, INK)
    jet(x + s - 12, y + s - 12, 0.7, INK2)


ICON_FNS = [icon_flags, icon_table, icon_ship, icon_radar, icon_rocket, icon_jets]


# --------------------------------------------------------------------------
# illustration (hero)
# --------------------------------------------------------------------------
def draw_illustration(cv, txt, x, y, w, h):
    cap_h = 22
    body_h = h - cap_h
    cv.fill_rect(x, y, w, body_h, BLUE_SEA)
    # subtle sky bands on the upper part
    for i in range(4):
        cv.fill_rect(x, y + int(i * body_h * 0.55 / 4), w, 2, (40, 86, 134))
    # water occupies the lower 45%
    water_top = y + int(body_h * 0.55)
    cv.fill_rect(x, water_top, w, y + body_h - water_top, TEAL)
    cv.fill_rect(x, water_top, w, 2, (58, 116, 140))
    # three thin horizontal wave lines on the water
    for k in range(3):
        wy = water_top + 12 + k * 12
        dash = 0
        while dash < w:
            seg = 14 if (dash // 14) % 2 == 0 else 8
            cv.fill_rect(x + dash, wy, min(seg, w - dash), 1, (86, 140, 162))
            dash += seg + 6
    # suspension bridge spanning the full width at the upper-middle
    deck_y = y + int(body_h * 0.42)
    cv.fill_rect(x, deck_y, w, 6, GREY)
    cv.fill_rect(x, deck_y, w, 2, (176, 178, 184))
    pylon_xs = [x + int(w * 0.22), x + int(w * 0.78)]
    pylon_top = deck_y - 78
    for tx in pylon_xs:
        cv.fill_rect(tx - 6, pylon_top, 12, deck_y - pylon_top + 30, DARKGREY)
        cv.fill_rect(tx - 10, pylon_top, 20, 6, GREY)
    # curved deck sag + vertical cable lines from the pylon tops
    span = pylon_xs[1] - pylon_xs[0]
    nsus = 22
    for i in range(nsus + 1):
        t = i / nsus
        sx = pylon_xs[0] + int(t * span)
        sag = int(26 * (1 - (2 * t - 1) ** 2))
        cv.line(sx, pylon_top + 2, sx, deck_y - sag, (196, 198, 204), 1)
        cv.fill_rect(sx, deck_y - sag, 1, sag, (196, 198, 204))
    cv.line(pylon_xs[0], pylon_top, pylon_xs[1], pylon_top, GREY, 1)
    # three grey smoke puffs rising from a red starburst at the centre span
    ccx = x + w // 2
    ccy = deck_y - 4
    for i, r in enumerate((26, 34, 40)):
        cv.disc(ccx, ccy - 18 - i * 16, r, SMOKE)
    for i in range(3):
        cv.disc(ccx - 18 + i * 18, ccy - 42 - (i % 2) * 14, 20, SMOKE)
    star(cv, ccx, ccy, 30, 12, 8, RED)
    star(cv, ccx, ccy, 18, 7, 8, (240, 150, 60))
    star(cv, ccx, ccy, 9, 4, 8, YELLOW)
    # two small black bird "V" glyphs in the sky
    for bx0, by0, bs in ((x + int(w * 0.16), y + int(body_h * 0.16), 7),
                         (x + int(w * 0.30), y + int(body_h * 0.26), 5)):
        cv.line(bx0 - bs, by0, bx0, by0 + bs, INK, 1)
        cv.line(bx0, by0 + bs, bx0 + bs, by0, INK, 1)
    # yellow sun smaller, top-right corner
    sun_x = x + w - 34
    sun_y = y + 30
    cv.disc(sun_x, sun_y, 14, YELLOW)
    cv.ring(sun_x, sun_y, 16, GOLD, 1)
    # caption bar at the bottom
    cv.fill_rect(x, y + body_h, w, cap_h, INK)
    cap = "THE KERCH BRIDGE AFTER TUESDAY'S STRIKE"
    cw = txt.width("micro", cap)
    txt.draw(cv, "micro", cap, x + (w - cw) / 2, y + body_h + 5, WHITE)


# --------------------------------------------------------------------------
# story cards
# --------------------------------------------------------------------------
CARDS = [
    ("AMERICAS · MANILA", GREEN, "TRUMP LANDS FOR ASEAN",
     "Summit opens his Asia trip; a Thailand trade pact is signed", 0),
    ("ASIA · SHENZHEN", ORANGE, "XI, TRUMP, PUTIN TO MEET",
     "First three-way summit, Thursday, on APEC's sidelines", 1),
    ("MIDDLE EAST · HORMUZ", RED, "TANKERS HIT MINES",
     "Two ships ablaze; a third US carrier arrives; Brent crude $92.76", 2),
    ("MIDDLE EAST · BAHRAIN", RED, "DRONES HIT US RADAR",
     "IRGC fires on the Sheikh Isa base; all intercepted, no casualties", 3),
    ("AMERICAS · CANAVERAL", GREEN, "VULCAN ROCKET FAILS",
     "40 Amazon Leo satellites are lost minutes after liftoff", 4),
    ("ASIA · TOKYO", ORANGE, "JAPAN SCRAMBLES JETS",
     "Russian aircraft breach airspace at dawn; Tokyo protests", 5),
]


def draw_card(cv, txt, x, y, w, h, card):
    tag, tagcol, headline, deck, icon_idx = card
    cv.fill_rect(x, y, w, h, PAPER)
    cv.frame(x, y, w, h, RULES)
    pad = 12
    margin = 8
    icon_sz = 50
    ix = x + w - icon_sz - margin
    iy = y + margin
    ICON_FNS[icon_idx](cv, ix, iy, icon_sz)
    tx = x + pad
    icon_bottom = iy + icon_sz
    # lines that sit beside the icon (top of the first block) must stop short
    # of the icon square; lines below it may use the full column width
    cw_icon = max(60, ix - tx)
    cw = max(60, x + w - pad - tx)
    box_bottom = y + h - pad

    tag_lh = txt.fonts["tag"]["lh"]
    tag_lines = txt.wrap("tag", tag, cw, 1)
    txt.draw(cv, "tag", tag_lines[0] if tag_lines else "", tx, y + 8, tagcol)
    hy = y + 8 + tag_lh + 6

    # headline: up to 3 wrapped lines at word boundaries, never cut. The first
    # line stops before the icon square when it overlaps vertically.
    hlh = txt.fonts["card"]["lh"]
    hlead = hlh
    widths = [cw_icon if hy < icon_bottom else cw, cw]
    hlines = txt.fit_lines("card", headline, widths)
    if len(hlines) > 3:
        hlines = hlines[:3]
    if len(hlines) > 1:
        avail = box_bottom - hy
        if avail < len(hlines) * hlead:
            hlead = max(hlh - 4, avail / len(hlines))
    hy_last = hy + len(hlines) * hlead
    for i, ln in enumerate(hlines):
        txt.draw(cv, "card", ln, tx, int(round(hy + i * hlead)), INK)

    dy = hy_last + 6
    # deck: up to 3 wrapped lines; reduce leading (never cut text) to fit the
    # card's bottom edge down to a floor of asc+desc-3.
    dlines = txt.fit("deck", deck, cw)
    if len(dlines) > 3:
        dlines = dlines[:3]
    dlh = txt.fonts["deck"]["lh"]
    min_dlh = txt.fonts["deck"]["asc"] + txt.fonts["deck"]["desc"] - 3
    dlead = dlh
    if len(dlines) > 1:
        avail = box_bottom - dy
        if avail < len(dlines) * dlead:
            dlead = max(min_dlh, avail / len(dlines))
    for i, ln in enumerate(dlines):
        txt.draw(cv, "deck", ln, tx, int(round(dy + i * dlead)), DECK_INK)

    # programmatic overflow verification: last line's pen x must stay within
    # the box right edge and each block bottom must stay within the card.
    h_last_r = tx + (txt.width("card", hlines[-1]) if hlines else 0)
    h_last_bottom = hy + len(hlines) * hlead
    h_hard_r = tx + (cw_icon if len(hlines) == 1 and hy < icon_bottom else cw)
    if h_last_r > h_hard_r or h_last_bottom > box_bottom:
        sys.stderr.write(
            "WARN overflow card headline@(%d,%d): last_x=%.1f box_r=%.1f "
            "bottom=%.1f box_bottom=%d text=%r\n" % (
                x, y, h_last_r, h_hard_r, h_last_bottom, box_bottom, headline))
    d_last_r = tx + (txt.width("deck", dlines[-1]) if dlines else 0)
    d_last_bottom = dy + len(dlines) * dlead
    if d_last_r > tx + cw or d_last_bottom > box_bottom:
        sys.stderr.write(
            "WARN overflow deck card@(%d,%d): last_x=%.1f box_r=%.1f "
            "bottom=%.1f box_bottom=%d text=%r\n" % (
                x, y, d_last_r, tx + cw, d_last_bottom, box_bottom, deck))


# --------------------------------------------------------------------------
# layout
# --------------------------------------------------------------------------
def draw_masthead(cv, txt):
    txt.draw(cv, "tag", "THE WORLD IN ONE DAY", 26, 26, RED)
    right = "ONE IMAGE · EVERY CONTINENT"
    rw = txt.width("tag", right)
    txt.draw(cv, "tag", right, 998 - rw, 26, INK2)
    mast = "17 NOVEMBER 2026"
    mw = txt.width("mast", mast)
    txt.draw(cv, "mast", mast, (W - mw) / 2, 40, INK)
    datel = "TUESDAY · THE WORLD'S NEWS IN ONE IMAGE"
    dlw = txt.width("date", datel)
    txt.draw(cv, "date", datel, (W - dlw) / 2, 100, INK2)
    cv.fill_rect(26, 127, W - 52, 3, INK)
    cv.fill_rect(26, 132, W - 52, 1, INK)


def draw_hero(cv, txt):
    x0, x1 = 26, 590
    y0 = 150
    hero_bottom = 150 + 248
    bx = chip_with_text(cv, txt, "tag", "LEAD · EUROPE", x0, y0, 7, 4, RED, WHITE)
    hy = y0 + bx + 12
    hlw = x1 - x0
    hlines = txt.fit("hero", "UKRAINE BLOWS A GAP IN THE KERCH BRIDGE", hlw)
    if len(hlines) > 3:
        hlines = hlines[:3]
    lh = txt.fonts["hero"]["lh"] - 6
    for i, ln in enumerate(hlines):
        txt.draw(cv, "hero", ln, x0, hy + i * lh, INK)
    dy = hy + len(hlines) * lh + 8
    deck = ("The road span to occupied Crimea collapses in an 'unprecedented "
            "operation'. Russia answers by striking bridges in Kyiv.")
    dlines = txt.fit("hero2", deck, hlw)
    if len(dlines) > 3:
        dlines = dlines[:3]
    dlh = txt.fonts["hero2"]["lh"] + 2
    min_dlh = txt.fonts["hero2"]["asc"] + txt.fonts["hero2"]["desc"] - 3
    dlead = dlh
    if len(dlines) > 1:
        avail = hero_bottom - dy
        if avail < len(dlines) * dlead:
            dlead = max(min_dlh, avail / len(dlines))
    for i, ln in enumerate(dlines):
        txt.draw(cv, "hero2", ln, x0, int(round(dy + i * dlead)), DECK_INK)
    for font, s, ytop, lead in (("hero", "UKRAINE BLOWS A GAP IN THE KERCH BRIDGE",
                                 hy, lh), ("hero2", deck, dy, dlead)):
        bad, last_right, bottom, box_r = txt.block_overflow(
            font, s, x0, hlw, ytop, hero_bottom, maxlines=3, leading=lead)
        if bad:
            sys.stderr.write(
                "WARN overflow hero/%s: last_x=%.1f box_r=%.1f bottom=%.1f "
                "box_bottom=%d\n" % (font, last_right, box_r, bottom, hero_bottom))
    draw_illustration(cv, txt, 610, 150, 388, 248)


def draw_grid(cv, txt):
    gx = 26
    gw = W - 52
    cols = 3
    gutter = 10
    cell_w = (gw - (cols - 1) * gutter) // cols
    row_h = 132
    y0 = 415
    for i, card in enumerate(CARDS):
        r = i // cols
        c = i % cols
        x = gx + c * (cell_w + gutter)
        y = y0 + r * (row_h + gutter)
        draw_card(cv, txt, x, y, cell_w, row_h, card)


BRIEFS = [
    "West urges Israel to open Gaza's aid crossings",
    "UK sanctions Israeli settlement firms",
    "Houthis advance as government troops fall back",
    "EU charges Temu under its digital rules",
    "Geneva debates a ban on killer robots",
    "Le Pen pledges an earlier retirement age",
    "NVIDIA's first earnings since Huang's exit",
    "JPMorgan: the outage was a software bug",
    "COP31 draft urges an end to fossil fuels",
    "Pope Leo draws 1.5m to a Lima Mass",
]

LEGEND_L1 = "1 KYIV · 2 KERCH · 3 MANILA · 4 SHENZHEN · 5 HORMUZ · 6 BAHRAIN"
LEGEND_L2 = ("7 CANAVERAL · 8 TOKYO · 9 LIMA · 10 ANTALYA · 11 JOHANNESBURG "
             "· 12 WASHINGTON")


def draw_bottom(cv, txt, land):
    y0 = 700
    lx0 = 26
    # "ALSO TODAY" tag and the map panel top share the same y (y0)
    chip_with_text(cv, txt, "tag", "ALSO TODAY", lx0, y0, 7, 4, RED, WHITE)
    fh = txt.fonts["brief"]["lh"]

    # map panel x 477..998 (width 521); occupies y0..y0+mh
    mx, my, mw, mh = 477, y0, 998 - 477, 178
    panel_bottom = my + mh

    # legend strip lives inside the panel, below the ocean rectangle
    llh = txt.fonts["micro"]["lh"]
    legend_gap = 8          # space above the legend (4px base + 4px requested)
    legend_h = legend_gap + 2 * llh + 6

    # ocean rectangle is the panel inset from the top down to the legend strip
    ox, oy = mx, my
    ow, oh = mw, mh - legend_h
    draw_map(cv, txt, land, ox, oy, ow, oh)
    draw_pins(cv, txt, ox, oy, ow, oh)

    # two centered legend lines in full ink, inside the panel bottom edge
    ly1 = oy + oh + legend_gap
    l1w = txt.width("micro", LEGEND_L1)
    txt.draw(cv, "micro", LEGEND_L1, mx + (mw - l1w) / 2, ly1, INK)
    l2w = txt.width("micro", LEGEND_L2)
    txt.draw(cv, "micro", LEGEND_L2, mx + (mw - l2w) / 2, ly1 + llh, INK)

    # ten briefs fill from y0 down to (panel bottom - 4px); reduce line
    # spacing if needed but never drop a brief
    ly = y0
    n = len(BRIEFS)
    target_bottom = panel_bottom - 4
    if n > 1:
        lh = (target_bottom - fh - ly) / (n - 1)
    else:
        lh = fh
    min_lh = txt.fonts["brief"]["asc"] + txt.fonts["brief"]["desc"] - 3
    lh = max(min_lh, lh)
    for i, b in enumerate(BRIEFS):
        yy = int(round(ly + i * lh))
        cv.fill_rect(lx0, yy + fh // 2 - 2, 5, 5, RED)
        txt.draw(cv, "brief", b, lx0 + 12, yy, INK)

def draw_footer(cv, txt):
    cv.fill_rect(26, 930, W - 52, 1, RULES)
    bar_y = 940
    bar_h = 20
    cv.fill_rect(26, bar_y, W - 52, bar_h, INK)
    ticker = ("MARKETS ON EDGE · NVIDIA'S FIRST EARNINGS SINCE HUANG'S EXIT · "
              "JPMORGAN OUTAGE A SOFTWARE BUG · BRENT $92.76")
    tw = txt.width("brief", ticker)
    txt.draw(cv, "brief", ticker, 26 + (W - 52 - tw) / 2, bar_y + 3, GOLD)
    ly = bar_y + bar_h + 8
    txt.draw(cv, "micro", "COMPILED FROM WIRE REPORTS · ALL STORIES FROM TUESDAY 17 NOVEMBER 2026",
             26, ly, INK2)
    right = "AN ENTRY FOR MAKE.FUN'S DAILY WORLD-NEWS BOUNTY"
    rw = txt.width("micro", right)
    txt.draw(cv, "micro", right, 998 - rw, ly, INK2)


# --------------------------------------------------------------------------
# PNG encode
# --------------------------------------------------------------------------
def _chunk(tag, data):
    return (len(data).to_bytes(4, "big") + tag + data +
            (zlib.crc32(tag + data) & 0xffffffff).to_bytes(4, "big"))


def write_png(path, cv):
    w = cv.w
    h = cv.h
    buf = cv.buf
    stride = w * 3
    raw = bytearray((stride + 1) * h)
    o = 0
    for y in range(h):
        raw[o] = 0  # filter type 0
        o += 1
        raw[o:o + stride] = buf[y * stride:(y + 1) * stride]
        o += stride
    ihdr = (w.to_bytes(4, "big") + h.to_bytes(4, "big") +
            bytes((8, 2, 0, 0, 0)))
    png = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) +
           _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


# --------------------------------------------------------------------------
# layout verification
# --------------------------------------------------------------------------
def _words_cover(font, txt, s, lines):
    """True if the wrapped lines preserve every word of s in order."""
    return " ".join(lines).split() == s.split()


def verify_layout(txt):
    """After layout, assert every card text block fits and keeps every word.

    A headline may use up to 3 lines and a deck up to 3 lines; nothing may be
    dropped or ellipsised. Prints a warning to stderr for any block whose last
    line crosses the box right edge or whose bottom crosses the box bottom.
    """
    warn = 0
    pad = 12
    margin = 8
    icon_sz = 50
    gx = 26
    gw = W - 52
    cols = 3
    gutter = 10
    cell_w = (gw - (cols - 1) * gutter) // cols
    row_h = 132
    y0 = 415
    hlh = txt.fonts["card"]["lh"]
    dlh = txt.fonts["deck"]["lh"]
    min_dlh = txt.fonts["deck"]["asc"] + txt.fonts["deck"]["desc"] - 3
    for i, (tag, _col, headline, deck, _icon) in enumerate(CARDS):
        r, c = divmod(i, cols)
        x = gx + c * (cell_w + gutter)
        y = y0 + r * (row_h + gutter)
        w, h = cell_w, row_h
        ix = x + w - icon_sz - margin
        tx = x + pad
        icon_bottom = (y + margin) + icon_sz
        cw_icon = max(60, ix - tx)
        cw = max(60, x + w - pad - tx)
        box_bottom = y + h - pad

        tag_lh = txt.fonts["tag"]["lh"]
        hy = y + 8 + tag_lh + 6
        widths = [cw_icon if hy < icon_bottom else cw, cw]
        hlines = txt.fit_lines("card", headline, widths)[:3]
        if len(hlines) > 1:
            avail = box_bottom - hy
            hlead = hlh if avail >= len(hlines) * hlh else max(hlh - 4, avail / len(hlines))
        else:
            hlead = hlh
        dy = hy + len(hlines) * hlead + 6
        dlines = txt.fit("deck", deck, cw)[:3]
        if len(dlines) > 1:
            avail = box_bottom - dy
            dlead = dlh if avail >= len(dlines) * dlh else max(min_dlh, avail / len(dlines))
        else:
            dlead = dlh

        for label, s, lines, ytop, lead, right in (
                ("headline", headline, hlines, hy, hlead, tx + cw),
                ("deck", deck, dlines, dy, dlead, tx + cw)):
            if not _words_cover("card" if label == "headline" else "deck", txt, s, lines):
                warn += 1
                sys.stderr.write("WARN dropped words in %s card@(%d,%d): %r\n"
                                 % (label, x, y, s))
            last_right = tx + (txt.width("card" if label == "headline" else "deck",
                                         lines[-1]) if lines else 0)
            bottom = ytop + len(lines) * lead
            if last_right > right or bottom > box_bottom:
                warn += 1
                sys.stderr.write(
                    "WARN overflow %s card@(%d,%d): last_x=%.1f box_r=%.1f "
                    "bottom=%.1f box_bottom=%d text=%r\n" % (
                        label, x, y, last_right, right, bottom, box_bottom, s))
    # hero headline + deck (drawn on the left of the masthead illustration)
    hx0, hx1 = 26, 590
    hero_bottom = 150 + 248
    hero_hlw = hx1 - hx0
    hero_head = "UKRAINE BLOWS A GAP IN THE KERCH BRIDGE"
    hero_deck = ("The road span to occupied Crimea collapses in an 'unprecedented "
                 "operation'. Russia answers by striking bridges in Kyiv.")
    hy0 = 150 + (txt.fonts["tag"]["lh"] + 8) + 12
    hh_lines = txt.fit("hero", hero_head, hero_hlw)[:3]
    hh_lead = txt.fonts["hero"]["lh"] - 6
    hh_bottom = hy0 + len(hh_lines) * hh_lead
    hero_dy = hh_bottom + 8
    hd_lines = txt.fit("hero2", hero_deck, hero_hlw)[:3]
    hd_min = txt.fonts["hero2"]["asc"] + txt.fonts["hero2"]["desc"] - 3
    hd_lh = txt.fonts["hero2"]["lh"] + 2
    if len(hd_lines) > 1:
        avail = hero_bottom - hero_dy
        hd_lead = hd_lh if avail >= len(hd_lines) * hd_lh else max(hd_min, avail / len(hd_lines))
    else:
        hd_lead = hd_lh
    hero_checks = [
        ("hero headline", "hero", hero_head, hh_lines, hy0, hh_lead),
        ("hero deck", "hero2", hero_deck, hd_lines, hero_dy, hd_lead),
    ]
    for label, font, s, lines, ytop, lead in hero_checks:
        if not _words_cover(font, txt, s, lines):
            warn += 1
            sys.stderr.write("WARN dropped words in %s: %r\n" % (label, s))
        last_right = hx0 + (txt.width(font, lines[-1]) if lines else 0)
        bottom = ytop + len(lines) * lead
        if last_right > hx1 or bottom > hero_bottom:
            warn += 1
            sys.stderr.write(
                "WARN overflow %s: last_x=%.1f box_r=%.1f bottom=%.1f "
                "box_bottom=%d text=%r\n" % (
                    label, last_right, float(hx1), bottom, hero_bottom, s))

    # legend lines and briefs must stay inside the map panel bottom edge
    panel_bottom = 700 + 178
    micro = txt.fonts["micro"]["lh"]
    brief_lh_f = txt.fonts["brief"]["lh"]
    legend_lines = [LEGEND_L1, LEGEND_L2]
    for i, ltext in enumerate(legend_lines):
        lw = txt.width("micro", ltext)
        if 477 + lw / 2 > 998:
            warn += 1
            sys.stderr.write("WARN legend line wider than panel: %r\n" % ltext)
    n = len(BRIEFS)
    blh = max(txt.fonts["brief"]["asc"] + txt.fonts["brief"]["desc"] - 3,
              (panel_bottom - 4 - brief_lh_f - 700) / (n - 1))
    last_brief_bottom = 700 + (n - 1) * blh + brief_lh_f
    if last_brief_bottom > panel_bottom - 4:
        warn += 1
        sys.stderr.write("WARN briefs overflow panel: bottom=%.1f limit=%.1f\n"
                         % (last_brief_bottom, panel_bottom - 4))

    if not warn:
        sys.stderr.write("layout verification passed: all text blocks fit, no words dropped\n")


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    here = os.path.dirname(os.path.abspath(__file__))
    atlas = load_atlas()
    fonts = prep_fonts(atlas)
    txt = Text(fonts)
    land = load_land(os.path.join(here, "land.json"))

    cv = Canvas(W, H, PAPER)
    draw_masthead(cv, txt)
    draw_hero(cv, txt)
    draw_grid(cv, txt)
    draw_bottom(cv, txt, land)
    draw_footer(cv, txt)

    verify_layout(txt)

    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    n = write_png(path, cv)
    print("bytes written:", n)


if __name__ == "__main__":
    main()
