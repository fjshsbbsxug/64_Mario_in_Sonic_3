"""
Renders Mario's in-game sprite sheet for the Sonic 3 A.I.R. mod.

Usage:
    python3 gen_sprites.py <sm64 decomp dir> <sm64 US rom .z64> <output sprites dir>

Produces:
    character_mario.png / character_mario.json   - all in-game character sprites
    mario_icons.png / mario_icons.json            - lives icon, data select portrait
"""

import json
import math
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sm64model as sm  # noqa: E402


SS = 4                    # supersampling factor
CANVAS = 64               # sprite canvas size before trimming
PX_PER_UNIT = 0.255       # Mario ends up ~38 px tall, like Sonic
YAW = 62                  # mostly side view, slightly turned towards the camera
PITCH = 8
LIGHT = (0.45, 0.75, 0.65)

# Distance from the character's center to the floor, in pixels.
# Upright S3K characters have 19 px, rolling ones (jumps etc.) have 14 px.
UPRIGHT = 19
ROLLING = 14


def frames_even(anim, n, first=None, last=None):
    a = anim["start"] if first is None else first
    b = sm.anim_num_frames(anim) - 1 if last is None else last
    if n == 1:
        return [int(round((a + b) / 2))]
    return [int(round(a + (b - a) * i / (n - 1))) for i in range(n)]


def frames_cycle(anim, n):
    """For looping animations: n frames evenly over the full loop (last frame != first)."""
    a = anim["loop_start"]
    b = sm.anim_num_frames(anim)
    return [int(a + (b - a) * i / n) for i in range(n)]


# name, anim id, frame selector, options
SPRITES = [
    ("idle",        0xC5, ("even", 4),            dict()),
    ("blink",       0xC5, ("at", [0]),            dict(eyes="closed")),
    ("walk",        0x48, ("cycle", 8),           dict()),
    ("run",         0x72, ("cycle", 8),           dict()),
    ("skid",        0x0F, ("at", [6]),            dict()),
    ("push",        0x6C, ("cycle", 4),           dict()),
    ("crouch",      0x98, ("at", [0]),            dict()),
    ("lookup",      0x1E, ("last", 1),            dict()),
    ("jump",        0x4D, ("at", [2, 8, 16]),     dict(anchor=ROLLING, lhand="open", rhand="open")),
    ("jump2",       0x50, ("even", 2),            dict(anchor=ROLLING, lhand="open", rhand="open")),
    ("jump2fall",   0x4C, ("even", 2),            dict(anchor=ROLLING, lhand="open", rhand="open")),
    ("triple",      0xC1, ("even", 8),            dict(anchor=ROLLING)),
    ("backflip",    0x04, ("even", 8, 2, 30),     dict(anchor=ROLLING)),
    ("longjump",    0x13, ("even", 2),            dict(anchor=ROLLING)),
    ("fall",        0x56, ("even", 2),            dict(lhand="open", rhand="open")),
    ("spring",      0x50, ("at", [4]),            dict(lhand="open", rhand="open")),
    ("gpspin",      0x3C, ("even", 4),            dict(anchor=ROLLING)),
    ("gpound",      0x3D, ("at", [0]),            dict(anchor=ROLLING)),
    ("gpland",      0x3A, ("at", [2]),            dict()),
    ("dive",        0x88, ("even", 2),            dict(anchor=ROLLING, lhand="open", rhand="open")),
    ("diveslide",   0x89, ("at", [0]),            dict(anchor=ROLLING, lhand="open", rhand="open")),
    ("crouchslide", 0x98, ("at", [0]),            dict(anchor=ROLLING)),
    ("wallkick",    0xCB, ("even", 3),            dict(anchor=ROLLING, lhand="open", rhand="open")),
    ("hurt",        0x02, ("at", [4]),            dict(eyes="half", lhand="open", rhand="open")),
    ("death",       0x02, ("at", [4]),            dict(eyes="dead", lhand="open", rhand="open", yaw=8)),
    ("drown",       0xA5, ("at", [20]),           dict(eyes="dead", lhand="open", rhand="open", yaw=20)),
    ("victory",     0xCD, ("at", [40, 52, 64, 76]), dict(rhand="open")),
    ("balance",     0x2D, ("even", 2),            dict(eyes="half", lhand="open", rhand="open")),
    ("hang",        0x35, ("cycle", 2),           dict(lhand="open", rhand="open", anchor=UPRIGHT)),
    ("pole",        0x0D, ("at", [0]),            dict(lhand="open", rhand="open")),
    ("twirl",       0x94, ("cycle", 4),           dict(lhand="open", rhand="open")),
    ("carried",     0x2B, ("at", [0]),            dict(lhand="open", rhand="open")),
    ("panic",       0x2D, ("even", 2),            dict(eyes="half", lhand="open", rhand="open")),
    ("wait",        0xC3, ("even", 2),            dict()),
]


def select_frames(anim, sel):
    kind = sel[0]
    if kind == "even":
        return frames_even(anim, *sel[1:])
    if kind == "cycle":
        return frames_cycle(anim, sel[1])
    if kind == "at":
        return sel[1]
    if kind == "last":
        n = sm.anim_num_frames(anim)
        return [n - 1 - i for i in range(sel[1])][::-1]
    raise ValueError(kind)


def downsample(img, ss):
    h, w = img.shape[0] // ss, img.shape[1] // ss
    blk = img.reshape(h, ss, w, ss, 4).transpose(0, 2, 1, 3, 4).reshape(h, w, ss * ss, 4)
    a = blk[..., 3]
    cov = a.mean(axis=2)
    wsum = np.maximum(a.sum(axis=2, keepdims=True), 1e-6)
    rgb = (blk[..., :3] * a[..., None]).sum(axis=2) / wsum
    alpha = (cov >= 0.45).astype(np.float32)
    # Darken the silhouette edge a bit, like hand-drawn Genesis sprites
    opaque = alpha > 0
    pad = np.pad(opaque, 1)
    inner = pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    edge = opaque & ~inner
    rgb[edge] *= 0.72
    return np.dstack([rgb, alpha])


def render_sprite(model, anims, anim_id, frame, opts, px_per_unit=PX_PER_UNIT, canvas=CANVAS):
    anim = anims[anim_id]
    mats = sm.pose_matrices(anim, frame)
    soup = sm.build_soup(model, mats, eyes=opts.get("eyes", "front"),
                         lhand=opts.get("lhand", "fist"), rhand=opts.get("rhand", "fist"))
    view = sm.view_matrix(opts.get("yaw", YAW), opts.get("pitch", PITCH))
    anchor = opts.get("anchor", UPRIGHT)
    center = canvas // 2
    hi = sm.render(soup, view, (canvas, canvas), px_per_unit,
                   (center, center + anchor), LIGHT, ss=SS)
    return downsample(hi, SS), (center, center)


def build_palette(images, ncolors):
    """Shared palette for all sprites, so the sheet looks consistent."""
    pix = np.concatenate([im[im[..., 3] > 0][:, :3] for im in images])
    pix = (pix * 255).astype(np.uint8)
    side = int(math.ceil(math.sqrt(len(pix))))
    buf = np.zeros((side * side, 3), np.uint8)
    buf[:len(pix)] = pix
    buf[len(pix):] = pix[0]
    pim = Image.fromarray(buf.reshape(side, side, 3), "RGB")
    q = pim.quantize(colors=ncolors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(q.getpalette()[:ncolors * 3], np.float32).reshape(-1, 3) / 255.0
    # Snap to the 5 bits per channel that S3AIR supports
    return np.round(pal * 31) / 31


def apply_palette(img, pal):
    rgb = img[..., :3]
    d = ((rgb[..., None, :] - pal[None, None, :, :]) ** 2).sum(-1)
    idx = d.argmin(-1)
    out = np.dstack([pal[idx], img[..., 3]])
    return out


def trim(img, center):
    a = img[..., 3] > 0
    if not a.any():
        return img[:1, :1], (0, 0)
    ys, xs = np.where(a)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return img[y0:y1, x0:x1], (center[0] - x0, center[1] - y0)


def pack(sprites, sheet_width=512, pad=2):
    """Simple shelf packer. sprites: list of (key, img, center)."""
    x = y = pad
    shelf = 0
    placed = []
    for key, img, center in sprites:
        h, w = img.shape[:2]
        if x + w + pad > sheet_width:
            x = pad
            y += shelf + pad
            shelf = 0
        placed.append((key, x, y, img, center))
        x += w + pad
        shelf = max(shelf, h)
    height = y + shelf + pad
    sheet = np.zeros((height, sheet_width, 4), np.float32)
    for key, px, py, img, _c in placed:
        h, w = img.shape[:2]
        sheet[py:py + h, px:px + w] = img
    return sheet, placed


def save_sheet(sheet, placed, png_path, json_path):
    Image.fromarray((np.clip(sheet, 0, 1) * 255).round().astype(np.uint8), "RGBA").save(png_path)
    fname = os.path.basename(png_path)
    lines = []
    for key, px, py, img, center in placed:
        h, w = img.shape[:2]
        lines.append('\t"%s": { "File": "%s", "Rect": "%d,%d,%d,%d", "Center": "%d,%d" }'
                     % (key, fname, px, py, w, h, center[0], center[1]))
    with open(json_path, "w") as f:
        f.write("{\n" + ",\n".join(lines) + "\n}\n")


def main():
    decomp, rom, outdir = sys.argv[1:4]
    os.makedirs(outdir, exist_ok=True)
    model, anims = sm.load_model(decomp, rom)

    rendered = []
    counts = {}
    for name, aid, sel, opts in SPRITES:
        frames = select_frames(anims[aid], sel)
        counts[name] = len(frames)
        for i, f in enumerate(frames):
            img, center = render_sprite(model, anims, aid, f, opts)
            rendered.append(("mario_%s_%d" % (name, i), img, center))

    # Icons: lives icon head and data select portrait
    icons = []
    head, hc = render_sprite(model, anims, 0xC5, 0, dict(yaw=35, pitch=5, anchor=40), px_per_unit=0.36, canvas=96)
    icons.append(("mario_icon_head_raw", head, hc))
    portrait, pc = render_sprite(model, anims, 0xC5, 0, dict(yaw=40, pitch=5), px_per_unit=0.255)
    icons.append(("mario_icon_portrait_raw", portrait, pc))

    pal = build_palette([r[1] for r in rendered], 26)
    final = []
    for key, img, center in rendered:
        img = apply_palette(img, pal)
        img, c = trim(img, center)
        final.append((key, img, c))
    sheet, placed = pack(final)
    save_sheet(sheet, placed, os.path.join(outdir, "character_mario.png"),
               os.path.join(outdir, "character_mario.json"))

    # Icons get post-processed separately in build_mod.py
    for key, img, center in icons:
        img = apply_palette(img, pal)
        img, c = trim(img, center)
        Image.fromarray((img * 255).round().astype(np.uint8), "RGBA").save(os.path.join(outdir, key + ".png"))
        with open(os.path.join(outdir, key + ".center"), "w") as f:
            f.write("%d,%d\n" % c)

    with open(os.path.join(outdir, "mario_frame_counts.json"), "w") as f:
        json.dump(counts, f, indent=1)
    print("Rendered %d sprites" % len(final))


if __name__ == "__main__":
    main()
