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
NIGHT = (18, 22, 40)
MOON_GLOW = (60, 66, 92)
MOON_CRATER = (206, 172, 64)
JET_GREY = (128, 132, 140)
JET_GREY2 = (104, 108, 118)
TRACER = (232, 182, 90)
DESERT = (150, 122, 82)
DESERT_EDGE = (120, 96, 62)
DESERT_DUNE = (168, 140, 98)
RADAR_GREY = (128, 118, 108)
FLAME = (240, 154, 44)


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


# pin place names: Qeshm, Kerch, Shenzhen, Bay of Bengal, Tallinn,
# Santa Clara, Jerusalem, Kyiv, Conakry, Kinshasa, Irkutsk, Tokyo
PINS = [
    (1, 55.9, 26.8), (2, 36.5, 45.3), (3, 114.06, 22.54),
    (4, 87.0, 17.0), (5, 24.75, 59.44), (6, -121.96, 37.35),
    (7, 35.2, 31.77), (8, 30.5, 50.45), (9, -13.68, 9.51),
    (10, 15.3, -4.32), (11, 104.3, 52.3), (12, 139.7, 35.7),
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


def icon_ship_escort(cv, x, y, s):
    # main cargo ship on the water
    hull_y = y + s - 20
    hull = [(x + 2, hull_y), (x + s - 18, hull_y),
            (x + s - 26, hull_y + 12), (x + 10, hull_y + 12)]
    cv.scanline_polygon(hull, INK)
    cv.fill_rect(x + s // 2 - 14, hull_y - 12, 12, 12, INK2)
    cv.fill_rect(x + s // 2 - 18, hull_y - 16, 20, 4, RED)
    cv.fill_rect(x + 2, hull_y + 14, s - 20, 2, BLUE_SEA)
    # small escort vessel escorting to the right
    ex = x + s - 12
    eh = y + s - 8
    ev = [(ex - 6, eh - 6), (ex + 6, eh - 6), (ex + 3, eh), (ex - 3, eh)]
    cv.scanline_polygon(ev, INK)
    cv.fill_rect(ex - 1, eh - 12, 2, 6, DARKGREY)
    cv.fill_rect(ex - 5, eh - 14, 10, 2, GOLD)

def icon_bridge_wrench(cv, x, y, s):
    # bridge deck on two piers with a suspension arc
    deck_y = y + s - 20
    cv.fill_rect(x + 4, deck_y, s - 8, 4, GREY)
    for px in (x + 10, x + s // 2, x + s - 12):
        cv.fill_rect(px, deck_y + 4, 3, 12, DARKGREY)
    arc_x0, arc_x1 = x + 6, x + s - 6
    arc_y = deck_y - 16
    n = 14
    for i in range(n + 1):
        t = i / n
        ax = arc_x0 + t * (arc_x1 - arc_x0)
        sag = int(10 * (1 - (2 * t - 1) ** 2))
        cv.fill_rect(int(ax), arc_y + sag, 1, deck_y - (arc_y + sag), GREY)
    cv.fill_rect(arc_x0, arc_y, arc_x1 - arc_x0, 2, GREY)
    # wrench overlaid at the lower-left corner
    wx = x + 12
    wy = y + s - 6
    cv.line(wx, wy, wx + 14, wy - 14, INK2, 3)
    cv.ring(wx + 16, wy - 16, 5, INK, 3)

def icon_columns(cv, x, y, s):
    # bank/parliament columns under a pediment
    base_y = y + s - 6
    top_y = y + 14
    ped = [(x + 6, top_y), (x + s // 2, y + 4), (x + s - 6, top_y)]
    cv.scanline_polygon(ped, INK)
    cv.fill_rect(x + 4, top_y, s - 8, 3, INK2)
    ncol = 4
    span = s - 20
    for i in range(ncol):
        cx = x + 12 + i * (span // (ncol - 1))
        cv.fill_rect(cx - 2, top_y + 4, 4, base_y - (top_y + 6), GREY)
        cv.fill_rect(cx - 3, top_y + 4, 6, 2, INK2)
    cv.fill_rect(x + 6, base_y, s - 12, 3, INK)

def icon_flags3(cv, x, y, s):
    pole_top = y + 6
    for i, col in enumerate((GREEN, RED, GREEN)):
        px = x + i * (s // 3) + 4
        cv.fill_rect(px, pole_top, 2, s - 12, DARKGREY)
        cv.fill_rect(px + 2, pole_top + 2, s // 4, s // 4, col)
        cv.fill_rect(px + 2, pole_top + 2, s // 4, 1, INK)

def icon_robot_gavel(cv, x, y, s):
    # robot silhouette on the left
    rx = x + 8
    ry = y + 10
    bw = s // 2 - 4
    bh = s - 20
    cv.fill_rect(rx, ry + 8, bw, bh - 8, DARKGREY)
    cv.fill_rect(rx + 4, ry, bw - 8, 10, INK)
    cv.fill_rect(rx + 5, ry + 3, 3, 3, GOLD)
    cv.fill_rect(rx + bw - 8, ry + 3, 3, 3, GOLD)
    cv.fill_rect(rx + 4, ry + bh - 4, bw - 8, 4, INK)
    # gavel to the right
    hx = x + s - 16
    hy = y + s - 18
    cv.line(hx - 8, hy + 8, hx + 8, hy - 8, INK2, 3)
    cv.fill_rect(hx + 2, hy - 14, 14, 8, INK)
    cv.fill_rect(hx + 4, hy + 8, 12, 3, GREY)

def icon_leaf(cv, x, y, s):
    cx = x + s // 2
    cy = y + s // 2
    r = s // 2 - 4
    cv.ring(cx, cy, r, GREEN, 2)
    # leaf shape inside the circle
    leaf = [(cx, cy - r + 6), (cx + r - 10, cy - 2),
            (cx + 4, cy + r - 8), (cx - r + 10, cy + 2)]
    cv.scanline_polygon(leaf, GREEN)
    cv.line(cx - r + 10, cy + 2, cx + r - 10, cy - 2, PAPER, 1)

def icon_bridge_burst(cv, x, y, s):
    # bridge deck on two piers with a suspension arc
    deck_y = y + s - 20
    cv.fill_rect(x + 4, deck_y, s - 8, 4, GREY)
    for px in (x + 10, x + s // 2, x + s - 12):
        cv.fill_rect(px, deck_y + 4, 3, 12, DARKGREY)
    arc_x0, arc_x1 = x + 6, x + s - 6
    arc_y = deck_y - 16
    n = 14
    for i in range(n + 1):
        t = i / n
        ax = arc_x0 + t * (arc_x1 - arc_x0)
        sag = int(10 * (1 - (2 * t - 1) ** 2))
        cv.fill_rect(int(ax), arc_y + sag, 1, deck_y - (arc_y + sag), GREY)
    cv.fill_rect(arc_x0, arc_y, arc_x1 - arc_x0, 2, GREY)
    # a red burst where the arch has been blown apart
    bx = x + s // 2
    by = arc_y + 2
    cv.fill_rect(bx - 8, by - 3, 16, 6, RED)
    cv.fill_rect(bx - 3, by - 8, 6, 16, RED)
    cv.fill_rect(bx - 6, by - 6, 12, 12, RED)
    cv.disc(bx, by, 3, (230, 70, 78))

def icon_three_flags(cv, x, y, s):
    pole_top = y + 6
    for i, col in enumerate((RED, BLUE_SEA, GREEN)):
        px = x + i * (s // 3) + 2
        cv.fill_rect(px, pole_top, 2, s - 12, DARKGREY)
        cv.fill_rect(px + 2, pole_top + 2, s // 4 + 2, s // 4, col)
        cv.fill_rect(px + 2, pole_top + 2, s // 4 + 2, 1, INK)

def icon_cyclone(cv, x, y, s):
    import math as _m
    cx = x + s // 2
    cy = y + s // 2
    for arm in range(3):
        a0 = arm * 2.0943951
        for i in range(30):
            t = i / 29.0
            r = (s // 2 - 6) * t
            a = a0 + t * 2.6
            px = cx + r * _m.cos(a)
            py = cy + r * _m.sin(a)
            cv.fill_rect(int(px), int(py), 2, 2, ORANGE)
    cv.disc(cx, cy, 3, RED)

def icon_fence(cv, x, y, s):
    top = y + 12
    bot = y + s - 8
    for i in range(4):
        px = x + 6 + i * ((s - 14) // 3)
        cv.fill_rect(px, top, 3, bot - top, GREY)
    cv.fill_rect(x + 4, top + 8, s - 8, 3, DARKGREY)
    cv.fill_rect(x + 4, bot - 14, s - 8, 3, DARKGREY)

def icon_chip(cv, x, y, s):
    cx = x + s // 2
    cy = y + s // 2
    half = s // 4
    cv.fill_rect(cx - half, cy - half, 2 * half, 2 * half, DARKGREY)
    cv.fill_rect(cx - half + 4, cy - half + 4, 2 * half - 8, 2 * half - 8, GREY)
    cv.fill_rect(cx - 4, cy - 4, 8, 8, GREEN)
    for i in range(3):
        off = -half + 4 + i * ((2 * half - 8) // 2)
        cv.fill_rect(cx - half - 5, cy + off, 5, 2, INK2)
        cv.fill_rect(cx + half, cy + off, 5, 2, INK2)
        cv.fill_rect(cx + off, cy - half - 5, 2, 5, INK2)
        cv.fill_rect(cx + off, cy + half, 2, 5, INK2)

def icon_podium(cv, x, y, s):
    base_y = y + s - 8
    # rostrum block
    cv.fill_rect(x + 6, base_y - 12, s - 12, 12, INK)
    cv.fill_rect(x + 6, base_y - 12, s - 12, 2, INK2)
    # a figure behind the lectern
    cv.disc(x + s // 2, y + 12, 6, INK2)
    cv.fill_rect(x + s // 2 - 7, y + 18, 14, 14, DARKGREY)
    # angled lectern top
    cv.scanline_polygon([(x + s // 2 - 12, y + 26), (x + s // 2 + 12, y + 22),
                         (x + s // 2 + 12, y + 28), (x + s // 2 - 12, y + 32)], GREY)

ICON_FNS = [icon_bridge_burst, icon_chip, icon_three_flags,
            icon_cyclone, icon_podium, icon_fence]


# --------------------------------------------------------------------------
# illustration (hero)
# --------------------------------------------------------------------------
def draw_illustration(cv, txt, x, y, w, h):
    cap_h = 22
    body_h = h - cap_h
    body_bottom = y + body_h
    # dark night sky
    cv.fill_rect(x, y, w, body_h, NIGHT)
    # a few faint stars
    for sx, sy in ((x + 30, y + 24), (x + 72, y + 14), (x + 210, y + 20),
                   (x + 258, y + 40), (x + 150, y + 34)):
        cv.fill_rect(sx, sy, 2, 2, (120, 130, 160))
    # yellow moon with a soft halo in the upper left
    cv.ring(x + 74, y + 66, 30, MOON_GLOW, 3)
    cv.disc(x + 74, y + 66, 20, YELLOW)
    cv.disc(x + 68, y + 60, 4, MOON_CRATER)
    cv.disc(x + 82, y + 74, 3, MOON_CRATER)
    # two grey jets banking diagonally across the sky, each trailing tracers
    def jet(cx, cy, col):
        # fuselage
        cv.fill_rect(cx - 14, cy - 3, 30, 6, col)
        # nose
        cv.scanline_polygon([(cx + 16, cy - 3), (cx + 24, cy), (cx + 16, cy + 3)], col)
        # swept wings as a single triangle through the body
        cv.scanline_polygon([(cx - 2, cy - 2), (cx + 12, cy - 16),
                             (cx + 2, cy - 2)], col)
        cv.scanline_polygon([(cx - 2, cy + 2), (cx + 12, cy + 16),
                             (cx + 2, cy + 2)], col)
        # tail fin
        cv.scanline_polygon([(cx - 16, cy - 2), (cx - 22, cy - 14),
                             (cx - 10, cy - 2)], col)
    # lower jet, banking up to the right with tracer lines behind it
    j1x, j1y = x + int(w * 0.42), y + int(body_h * 0.40)
    for i in range(3):
        tx = j1x - 30 - i * 16
        ty = j1y + 10 + i * 5
        cv.line(tx, ty, tx + 30, ty - 6, TRACER, 1)
    jet(j1x, j1y, JET_GREY)
    # upper jet, higher and nearer the right edge
    j2x, j2y = x + int(w * 0.72), y + int(body_h * 0.22)
    for i in range(2):
        tx = j2x - 28 - i * 16
        ty = j2y + 8 + i * 5
        cv.line(tx, ty, tx + 28, ty - 5, TRACER, 1)
    jet(j2x, j2y, JET_GREY2)
    # desert band across the lower part of the frame
    desert_top = y + int(body_h * 0.66)
    cv.fill_rect(x, desert_top, w, body_bottom - desert_top, DESERT)
    cv.fill_rect(x, desert_top, w, 2, DESERT_EDGE)
    # a couple of low dunes
    for dx, dw in ((x + 10, 120), (x + 200, 150)):
        cv.scanline_polygon([(dx, desert_top + 16), (dx + dw // 2, desert_top + 4),
                             (dx + dw, desert_top + 16)], DESERT_DUNE)
    # damaged radar dome on the right of the desert band, with flames
    rx = x + int(w * 0.74)
    ry = desert_top - 6
    # pedestal legs
    cv.fill_rect(rx - 14, ry + 4, 4, 22, DARKGREY)
    cv.fill_rect(rx + 10, ry + 4, 4, 22, DARKGREY)
    # dome, dented on top
    cv.scanline_polygon([(rx - 22, ry + 6), (rx - 16, ry - 12),
                         (rx - 4, ry - 20), (rx + 8, ry - 18),
                         (rx + 12, ry - 6), (rx + 22, ry + 6)], RADAR_GREY)
    cv.fill_rect(rx - 22, ry + 4, 44, 4, DARKGREY)
    # a gouge torn out of the dome
    cv.scanline_polygon([(rx + 2, ry - 18), (rx + 16, ry - 14),
                         (rx + 10, ry - 2), (rx - 2, ry - 6)], NIGHT)
    # orange flames licking out of the gouge
    cv.scanline_polygon([(rx - 2, ry - 16), (rx + 4, ry - 34),
                         (rx + 10, ry - 16)], ORANGE)
    cv.scanline_polygon([(rx + 6, ry - 14), (rx + 14, ry - 30),
                         (rx + 18, ry - 10)], FLAME)
    cv.fill_rect(rx - 2, ry - 8, 22, 4, ORANGE)
    # two grey smoke puffs drifting up off the flames
    cv.ring(rx + 2, ry - 44, 12, SMOKE, 4)
    cv.ring(rx + 10, ry - 30, 9, SMOKE, 3)
    # caption bar at the bottom
    cv.fill_rect(x, y + body_h, w, cap_h, INK)
    cap = "THE QESHM SITE AFTER THE US STRIKE, WEDNESDAY"
    cw = txt.width("micro", cap)
    txt.draw(cv, "micro", cap, x + (w - cw) / 2, y + body_h + 5, WHITE)

# --------------------------------------------------------------------------
# story cards
# --------------------------------------------------------------------------
CARDS = [
    ("EUROPE · KERCH", BLUE_SEA, "KERCH ROAD ARCH FALLS",
     "Ukraine's strikes toppled the road arch; Russia pounds Kyiv's bridges", 1),
    ("ASIA · SHENZHEN", ORANGE, "THURSDAY: THE THREE-WAY",
     "Xi, Trump and Putin arrive; a Kim meeting is dangled on the sidelines", 3),
    ("ASIA · BAY OF BENGAL", ORANGE, "CYCLONE AKVAN BUILDS",
     "Flights cancelled as the storm strengthens toward the coast", 3),
    ("EUROPE · TALLINN", BLUE_SEA, "ESTONIA SHUTS BORDER",
     "The move follows a 'sabotage' bid at a drone maker", 5),
    ("AMERICAS · SANTA CLARA", GREEN, "NVIDIA BEATS FORECASTS",
     "First earnings since the exit; the board refuses to reinstate Huang", 2),
    ("MIDDLE EAST · JERUSALEM", RED, "KNESSET PICKS KAHANA",
     "An Eisenkot ally becomes speaker, a blow to Netanyahu", 4),
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
    right = "21 STORIES · SIX CONTINENTS · ONE PAGE"
    rw = txt.width("tag", right)
    txt.draw(cv, "tag", right, 998 - rw, 26, INK2)
    mast = "18 NOVEMBER 2026"
    mw = txt.width("mast", mast)
    txt.draw(cv, "mast", mast, (W - mw) / 2, 40, INK)
    datel = "WEDNESDAY · THE WORLD'S NEWS IN ONE IMAGE"
    dlw = txt.width("date", datel)
    txt.draw(cv, "date", datel, (W - dlw) / 2, 100, INK2)
    cv.fill_rect(26, 127, W - 52, 3, INK)
    cv.fill_rect(26, 132, W - 52, 1, INK)


def draw_hero(cv, txt):
    x0, x1 = 26, 590
    y0 = 150
    hero_bottom = 150 + 248
    bx = chip_with_text(cv, txt, "tag", "LEAD · MIDDLE EAST", x0, y0, 7, 4, RED, WHITE)
    hy = y0 + bx + 12
    hlw = x1 - x0
    hero_head = "US AND IRAN TRADE FIRE"
    hlines = txt.fit("hero", hero_head, hlw)
    if len(hlines) > 3:
        hlines = hlines[:3]
    lh = txt.fonts["hero"]["lh"] - 6
    for i, ln in enumerate(hlines):
        txt.draw(cv, "hero", ln, x0, hy + i * lh, INK)
    dy = hy + len(hlines) * lh + 8
    deck = ("US jets hit a missile site on Qeshm Island after Iran's drones "
            "struck a US radar in Bahrain. No casualties reported on either "
            "side.")
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
    for font, s, ytop, lead in (("hero", hero_head,
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
    "Zelensky sets out a five-point peace plan",
    "Guinea jails 224 in a gold-mining crackdown",
    "DRC Ebola at record pace: 11,000 cases",
    "Russian jet crashes in Siberia, killing 19",
    "Intel investors sue after a 29% plunge",
    "US measles cases pass 5,400; ten dead",
    "Australia's pay gap falls below 20%",
    "Dhoni ends his IPL career; CSK make him mentor",
    "India beat Pakistan 2-1 for a 10th SAFF title",
    "Félix Gallardo, Mexican drug lord, dies at 80",
    "Pope Leo flies home after a 12-day tour",
    "Google signs a geothermal deal in Oregon",
    "US soldier held in Britain on spying suspicion",
    "Japan scrambles jets as Russian planes near",
]

LEGEND_L1 = ("1 QESHM · 2 KERCH · 3 SHENZHEN · 4 BENGAL · 5 TALLINN "
             "· 6 SANTA CLARA")
LEGEND_L2 = ("7 JERUSALEM · 8 KYIV · 9 CONAKRY · 10 KINSHASA · 11 IRKUTSK "
             "· 12 TOKYO")


def draw_bottom(cv, txt, land):
    y0 = 700
    lx0 = 26
    # "ALSO TODAY" tag sits on its own line; the briefs start below it with a
    # clear gap so the chip never overlaps the first brief row.
    chip_h = chip_with_text(cv, txt, "tag", "ALSO TODAY", lx0, y0, 7, 4, RED, WHITE)
    brief_top = y0 + chip_h + 6          # at least 6px clearance below the chip
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

    # ten briefs fill from brief_top down to (panel bottom - 4px); reduce line
    # spacing if needed but never drop a brief
    ly = brief_top
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
    ticker = "MARKETS: NVIDIA BEATS FORECASTS · INTEL SUITS AFTER A 29% PLUNGE · OIL UP ON THE QESHM STRIKES"
    tw = txt.width("brief", ticker)
    txt.draw(cv, "brief", ticker, 26 + (W - 52 - tw) / 2, bar_y + 3, GOLD)
    ly = bar_y + bar_h + 8
    txt.draw(cv, "micro", "COMPILED FROM WIRE REPORTS · ALL STORIES FROM WEDNESDAY 18 NOVEMBER 2026",
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
    hero_head = "US AND IRAN TRADE FIRE"
    hero_deck = ("US jets hit a missile site on Qeshm Island after Iran's drones "
                 "struck a US radar in Bahrain. No casualties reported on either "
                 "side.")
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
