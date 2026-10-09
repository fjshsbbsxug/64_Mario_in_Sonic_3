"""
HUD lives icon, results screen nameplate, Data Select portrait and mod icons.

The "MARIO" texts are drawn with small bitmap fonts made for this mod, styled after
the Sonic 3 HUD and results screen texts.
"""

import os

import numpy as np
from PIL import Image


# --------------------------------------------------------------------------
# Lives icon: 16x16 head portrait + "MARIO" + small "x" (48x16 like the originals)
# --------------------------------------------------------------------------

HUD_FONT = {
    "M": ["10001", "11011", "10101", "10001", "10001", "10001"],
    "A": ["0110", "1001", "1001", "1111", "1001", "1001"],
    "R": ["1110", "1001", "1001", "1110", "1010", "1001"],
    "I": ["11", "11", "11", "11", "11", "11"],
    "O": ["0110", "1001", "1001", "1001", "1001", "0110"],
    "x": ["101", "010", "101"],
}

HUD_YELLOW = (252, 252, 0, 255)
HUD_WHITE = (252, 252, 252, 255)
HUD_SHADOW = (72, 72, 108, 255)
HUD_FRAME = (36, 36, 36, 255)


def _hud_glyph(rows, colors):
    h, w = len(rows), len(rows[0])
    out = np.zeros((h + 1, w + 1, 4), np.uint8)
    for y in range(h):
        for x in range(w):
            if rows[y][x] == "1":
                out[y, x] = colors(y)
    for y in range(h + 1):
        for x in range(w + 1):
            if out[y, x, 3] == 0:
                left = x > 0 and y < h and rows[y][x - 1] == "1"
                up = y > 0 and x < w and rows[y - 1][x] == "1"
                if left or up:
                    out[y, x] = HUD_SHADOW
    return out


def make_lives_icon(head):
    icon = np.zeros((16, 48, 4), np.uint8)

    # Portrait: white background framed by dark lines at top and bottom
    icon[0, 0:16] = HUD_FRAME
    icon[15, 0:16] = HUD_FRAME
    icon[1:15, 0:16] = HUD_WHITE
    hb = head.crop((0, 0, head.width, int(head.height * 0.40)))
    hb = hb.crop(hb.getbbox())
    scale = min(16.0 / hb.width, 14.0 / hb.height)
    hs = np.array(hb.resize((max(1, round(hb.width * scale)), max(1, round(hb.height * scale))), Image.LANCZOS))
    mask = hs[..., 3] >= 128
    oy, ox = 1 + 14 - hs.shape[0], (16 - hs.shape[1]) // 2
    head_only = np.zeros((14, 16, 4), np.uint8)
    region = head_only[oy - 1:oy - 1 + hs.shape[0], ox:ox + hs.shape[1]]
    region[mask] = hs[mask]
    region[mask, 3] = 255
    m = head_only[..., 3] > 0
    icon[1:15, 0:16][m] = head_only[m]

    # "MARIO"
    letters = [_hud_glyph(HUD_FONT[c], lambda y: HUD_WHITE if y in (2, 3) else HUD_YELLOW) for c in "MARIO"]
    x = 17 + max(0, (31 - sum(g.shape[1] for g in letters)) // 2)
    for g in letters:
        dst = icon[1:8, x:x + g.shape[1]]
        m = g[..., 3] > 0
        dst[m] = g[m]
        x += g.shape[1]

    # "x"
    g = _hud_glyph(HUD_FONT["x"], lambda y: HUD_WHITE)
    dst = icon[10:14, 22:26]
    m = g[..., 3] > 0
    dst[m] = g[m]

    return Image.fromarray(icon, "RGBA"), Image.fromarray(head_only, "RGBA")


# --------------------------------------------------------------------------
# Results screen nameplate ("MARIO GOT THROUGH")
# --------------------------------------------------------------------------

PLATE_FONT = {
    "M": ["1111.....1111",
          "11111...11111",
          "111111.111111",
          "1111111111111",
          "1111.111.1111",
          "1111..1..1111",
          "1111.....1111",
          "1111.....1111",
          "1111.....1111",
          "1111.....1111",
          "1111.....1111",
          "1111.....1111"],
    "A": ["...111111...",
          "..11111111..",
          ".1111..1111.",
          "1111....1111",
          "1111....1111",
          "111111111111",
          "111111111111",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          "1111....1111"],
    "R": ["111111111...",
          "1111111111..",
          "1111...1111.",
          "1111....1111",
          "1111...1111.",
          "1111111111..",
          "111111111...",
          "1111..1111..",
          "1111...1111.",
          "1111...1111.",
          "1111....1111",
          "1111....1111"],
    "I": ["1111"] * 12,
    "O": ["...111111...",
          ".1111111111.",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          "1111....1111",
          ".1111111111.",
          "...111111..."],
}

PLATE_BODY = (36, 72, 216, 255)
PLATE_LIGHT = (108, 108, 252, 255)
PLATE_DARK = (36, 36, 144, 255)
PLATE_OUTLINE = (252, 180, 0, 255)
PLATE_OUTER = (252, 144, 0, 255)


def make_nameplate(text="MARIO"):
    gap = 3
    widths = [len(PLATE_FONT[c][0]) for c in text]
    w = sum(widths) + gap * (len(text) - 1) + 4
    body = np.zeros((16, w), bool)
    x = 2
    for c, cw in zip(text, widths):
        for y, row in enumerate(PLATE_FONT[c]):
            for i, ch in enumerate(row):
                if ch == "1":
                    body[2 + y, x + i] = True
        x += cw + gap

    def shifted(a, dy, dx):
        out = np.zeros_like(a)
        h, ww = a.shape
        ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
        xs, xd = (slice(0, ww - dx), slice(dx, ww)) if dx >= 0 else (slice(-dx, ww), slice(0, ww + dx))
        out[yd, xd] = a[ys, xs]
        return out

    ortho = shifted(body, 1, 0) | shifted(body, -1, 0) | shifted(body, 0, 1) | shifted(body, 0, -1)
    diag = shifted(body, 1, 1) | shifted(body, -1, -1) | shifted(body, 1, -1) | shifted(body, -1, 1)
    outline = ortho & ~body
    outer = diag & ~body & ~outline
    light = body & (~shifted(body, 1, 0) | ~shifted(body, 0, 1))      # top / left edges
    dark = body & (~shifted(body, -1, 0) | ~shifted(body, 0, -1))     # bottom / right edges

    img = np.zeros((16, w, 4), np.uint8)
    img[body] = PLATE_BODY
    img[dark] = PLATE_DARK
    img[light] = PLATE_LIGHT
    img[outline] = PLATE_OUTLINE
    img[outer] = PLATE_OUTER
    return Image.fromarray(img, "RGBA")


# --------------------------------------------------------------------------

def write_icons(head, portrait, sprites_dir, mod_dir):
    lives, head_small = make_lives_icon(head)
    lives.save(os.path.join(sprites_dir, "hud_mario.png"))
    with open(os.path.join(sprites_dir, "hud_mario.json"), "w") as f:
        f.write('{\n\t"hud_lives_icon_mario": { "File": "hud_mario.png", "Rect": "0,0,48,16" }\n}\n')

    plate = make_nameplate()
    plate.save(os.path.join(sprites_dir, "result_mario.png"))
    with open(os.path.join(sprites_dir, "result_mario.json"), "w") as f:
        f.write('{\n\t"result_nameplate_mario": { "File": "result_mario.png", "Rect": "0,0,%d,16", "Center": "-1,0" }\n}\n'
                % plate.width)

    # Data Select portrait, anchored at the bottom center
    portrait.save(os.path.join(sprites_dir, "dataselect_mario.png"))
    with open(os.path.join(sprites_dir, "dataselect_mario.json"), "w") as f:
        f.write('{\n\t"mario_dataselect": { "File": "dataselect_mario.png", "Rect": "0,0,%d,%d", "Center": "%d,%d" }\n}\n'
                % (portrait.width, portrait.height, portrait.width // 2 + 2, portrait.height))

    # Mod icons
    icon = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    s = 64 / max(portrait.size)
    p2 = portrait.resize((int(portrait.width * s), int(portrait.height * s)), Image.NEAREST)
    icon.alpha_composite(p2, ((64 - p2.width) // 2, 64 - p2.height))
    icon.save(os.path.join(mod_dir, "icon.png"))
    icon.save(os.path.join(mod_dir, "icon-64px.png"))
    icon16 = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    icon16.alpha_composite(head_small, (0, 1))
    icon16.save(os.path.join(mod_dir, "icon-16px.png"))
