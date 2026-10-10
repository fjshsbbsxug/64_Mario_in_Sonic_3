"""
Renders Mario's in-game sprite sheet for the Sonic 3 A.I.R. mod.

Produces character_mario.png / character_mario.json with all in-game character sprites,
plus the raw renders used for the icons.
"""

import math
import os

import numpy as np
from PIL import Image

import model as mdl


SS = 4                    # supersampling factor
CANVAS = 64               # sprite canvas size before trimming
PX_PER_UNIT = 0.255       # Mario ends up ~38 px tall, like Sonic
YAW = 62                  # mostly side view, slightly turned towards the camera
PITCH = 8
LIGHT = (0.45, 0.75, 0.65)

# Distance from the character's center to the floor, in pixels.
# Mario always uses the upright hitbox, which has 19 px below the center.
UPRIGHT = 19


# SM64 animations used by the mod: (animation id, render every n-th frame, options)
# Sprite keys are "mario_<anim id hex>_<index>", sprite i shows SM64 frame i * step.
OPEN = dict(lhand="open", rhand="open")
ANIMS = [
    (0xC3, 5, {}), (0xC4, 5, {}), (0xC5, 5, {}),          # idle (head left / right / center)
    (0x48, 5, {}), (0x72, 5, {}),                         # walking, running
    (0xCA, 5, {}), (0x92, 10, {}),                        # start tiptoe, tiptoe
    (0x0F, 1, {}), (0x10, 3, {}),                         # skid, stop skid
    (0xBC, 1, {}), (0xBD, 3, {}),                         # turning around part 1 / 2
    (0x97, 2, {}), (0x98, 15, {}), (0x96, 2, {}),         # start crouching, crouching, stop crouching
    (0x9B, 2, {}), (0x99, 8, {}), (0x9A, 2, {}),          # start crawling, crawling, stop crawling
    (0x4D, 2, OPEN), (0x4E, 4, {}),                       # single jump, landing
    (0x50, 2, OPEN), (0x4C, 3, OPEN), (0x4B, 3, {}),      # double jump rise / fall, landing
    (0xC1, 3, {}), (0xC0, 4, {}),                         # triple jump, landing
    (0x04, 3, {}),                                        # backflip
    (0xBF, 3, OPEN), (0xBE, 2, {}),                       # side flip, landing
    (0x13, 3, {}), (0x14, 3, {}), (0x11, 3, {}), (0x12, 3, {}),  # long jump fast / slow, landings
    (0x56, 1, OPEN), (0x57, 4, {}),                       # general fall, general land
    (0x88, 4, OPEN), (0x5A, 4, OPEN),                     # dive, slow land from dive
    (0x6F, 2, {}),                                        # forward spinning (rollout)
    (0x8C, 2, {}), (0x8D, 3, {}), (0x53, 5, OPEN),        # slide kick, crouch from slide kick, fall from slide kick
    (0xCB, 3, OPEN), (0xCC, 1, OPEN),                     # wall kick, start wall kick
    (0x4F, 3, {}),                                        # air kick
    (0x67, 1, {}), (0x69, 2, {}), (0x68, 1, {}), (0x6A, 3, {}), (0x66, 3, {}),  # punches, ground kick
    (0x3C, 2, {}), (0x3D, 2, {}), (0x3A, 2, {}),          # ground pound start / fall / landing
    (0x91, 2, OPEN), (0x8F, 4, OPEN), (0x90, 3, OPEN),    # butt slide, stop slide, fall from slide
    (0x6C, 3, {}),                                        # pushing
    (0x02, 1, OPEN), (0x7B, 5, OPEN), (0x8A, 5, OPEN),    # backward air knockback, backward ground knockback, ground bonk
    (0xCD, 6, dict(rhand="open")),                        # star dance (act clear)
    (0x35, 9, OPEN), (0x0D, 28, OPEN), (0x94, 1, OPEN),   # hang on ceiling, idle on pole, twirl
    (0x2B, 10, OPEN), (0x2D, 1, OPEN), (0x58, 5, OPEN),   # hanging on owl (carried), air forward kb, being grabbed
    (0xAA, 3, OPEN), (0xAB, 2, OPEN), (0xAC, 4, OPEN), (0xB2, 5, OPEN), (0xAD, 5, OPEN),  # swimming
    (0xB0, 1, OPEN), (0xAF, 3, OPEN),                     # water punch
]

# Extra sprite sets with ids that don't exist in SM64: (id, anim id, frames, options)
EXTRA = [
    (0xE0, 0x02, [4], dict(eyes="dead", lhand="open", rhand="open", yaw=8)),      # death
    (0xE1, 0xA5, [20], dict(eyes="dead", lhand="open", rhand="open", yaw=20)),    # drowned
    (0xE2, 0xC5, [10], dict(eyes="closed")),                                       # idle blink
    (0xE3, 0x02, [4], dict(eyes="half", lhand="open", rhand="open")),             # hurt
]


# ICZ 1 snowboarding: Mario on a snowboard, one sprite for each of Sonic's snowboarding frames
# ("mario_sb_<frame>"). Board angle (degrees, clockwise) and board center relative to the
# sprite center follow Sonic's frames, so Mario lines up with the game's animation.
# Mario leans with the board by "lean" (0..1). In the trick frames he isn't standing on the
# board, so his feet position is given instead.
#   (frame, board angle, board x, board y, SM64 animation, lean, feet position or None)
SNOWBOARD = [
    (0x01, 47, 1, 2, 0x4A, 0.4, None),          # trick frames (in the air)
    (0x02, 85, -1, 14, 0x4A, 0.0, (0, 15)),
    (0x03, -48, -2, 11, 0x4A, 0.0, (-3, 10)),
    (0x04, -53, -1, 15, 0x4A, 0.0, (2, 12)),
    (0x05, 59, 0, 12, 0x4A, 0.0, (0, 12)),
    (0x06, 0, -3, 12, 0x47, 1.0, None),         # riding
    (0x07, -6, -1, 12, 0x47, 1.0, None),
    (0x08, -11, -2, 11, 0x47, 1.0, None),
    (0x09, 62, -9, 5, 0x47, 0.4, None),         # steep slopes
    (0x0A, 38, -6, 6, 0x47, 0.6, None),
    (0x0B, 8, -2, 10, 0x47, 1.0, None),
    (0x0C, 22, -2, 9, 0x47, 1.0, None),
]
# AIZ 1 hollow tree: Mario running around the trunk, seen from 8 directions ("mario_tree_<dir>_<frame>").
# Direction 0 runs to the right, 2 away from the camera, 4 to the left, 6 towards the camera.
TREE_DIRECTIONS = 8
TREE_FRAMES = 4
TREE_ANIM = 0x72        # running


def tree_sprite_jobs(anims):
    loop_end = max(1, anims[TREE_ANIM]["loop_end"])
    jobs = []
    for d in range(TREE_DIRECTIONS):
        for f in range(TREE_FRAMES):
            jobs.append(("mario_tree_%d_%d" % (d, f), TREE_ANIM, f * loop_end // TREE_FRAMES, {"yaw": YAW + 45 + d * 45}))
    return jobs


# Twirling (HCZ fans, updrafts and the like): Mario's twirl pose turning around ("mario_twirl_<n>")
TWIRL_FRAMES = 8
TWIRL_ANIM = 0x94


def twirl_sprite_jobs():
    return [("mario_twirl_%d" % i, TWIRL_ANIM, 0, dict(OPEN, yaw=YAW + i * 360 // TWIRL_FRAMES)) for i in range(TWIRL_FRAMES)]


SNOWBOARD_CANVAS = 96
BOARD_LENGTH = 46
BOARD_THICKNESS = 4
BOARD_COLORS = ((248, 96, 72), (200, 24, 24), (40, 24, 56))    # top, bottom, outline


def draw_board(hi, cx, cy, angle_deg, ss):
    """Draws the snowboard (a red capsule) into a supersampled RGBA image, behind what's there."""
    a = math.radians(angle_deg)
    u = np.array([math.cos(a), math.sin(a)])
    n = np.array([math.sin(a), -math.cos(a)])        # board's "up"
    h, w = hi.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w]
    px = (xs + 0.5) / ss - cx
    py = (ys + 0.5) / ss - cy
    along = px * u[0] + py * u[1]
    across = px * n[0] + py * n[1]
    half = BOARD_LENGTH / 2 - BOARD_THICKNESS / 2
    dist = np.hypot(np.maximum(np.abs(along) - half, 0), across)
    inside = dist <= BOARD_THICKNESS / 2
    outline = inside & (dist > BOARD_THICKNESS / 2 - 1)
    top, bottom, edge = [np.array(c, np.float32) / 255 for c in BOARD_COLORS]
    col = np.where((across > 0)[..., None], top, bottom)
    col = np.where(outline[..., None], edge, col)
    free = inside & (hi[..., 3] == 0)
    hi[free, :3] = col[free]
    hi[free, 3] = 1.0


def render_snowboard(model, anims, frame_def):
    _fid, angle, bx, by, anim_id, lean, feet_pos = frame_def
    mats = mdl.pose_matrices(anims[anim_id], 0)
    soup = mdl.build_soup(model, mats, lhand="open", rhand="open")
    view = mdl.view_matrix(YAW, PITCH, -angle * lean)
    c = SNOWBOARD_CANVAS // 2
    a = math.radians(angle)
    board = (c + bx, c + by)
    if feet_pos is None:
        # Standing on the board
        feet = (board[0] + math.sin(a) * BOARD_THICKNESS / 2, board[1] - math.cos(a) * BOARD_THICKNESS / 2)
    else:
        feet = (c + feet_pos[0], c + feet_pos[1])
    hi = mdl.render(soup, view, (SNOWBOARD_CANVAS, SNOWBOARD_CANVAS), PX_PER_UNIT, feet, LIGHT, ss=SS)
    draw_board(hi, board[0], board[1], angle, SS)
    return downsample(hi, SS), (c, c)


def anim_sprite_frames(anim, step):
    return list(range(0, mdl.anim_num_frames(anim), step))


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
    mats = mdl.pose_matrices(anim, frame)
    soup = mdl.build_soup(model, mats, eyes=opts.get("eyes", "front"),
                          lhand=opts.get("lhand", "fist"), rhand=opts.get("rhand", "fist"))
    view = mdl.view_matrix(opts.get("yaw", YAW), opts.get("pitch", PITCH))
    anchor = opts.get("anchor", UPRIGHT)
    center = canvas // 2
    hi = mdl.render(soup, view, (canvas, canvas), px_per_unit,
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


def render_all(model, anims, outdir, script_path, progress=None):
    """Renders the sprite sheet into outdir and writes the animation data script.
    Returns (head image, portrait image) for the icons."""
    jobs = []
    for aid, step, opts in ANIMS:
        for i, f in enumerate(anim_sprite_frames(anims[aid], step)):
            jobs.append(("mario_%02x_%d" % (aid, i), aid, f, opts))
    for xid, aid, frames, opts in EXTRA:
        for i, f in enumerate(frames):
            jobs.append(("mario_%02x_%d" % (xid, i), aid, f, opts))
    jobs += tree_sprite_jobs(anims)
    jobs += twirl_sprite_jobs()

    rendered = []
    for key, aid, f, opts in jobs:
        img, center = render_sprite(model, anims, aid, f, opts)
        rendered.append((key, img, center))
        if progress:
            progress(len(rendered), len(jobs))

    for fd in SNOWBOARD:
        img, center = render_snowboard(model, anims, fd)
        rendered.append(("mario_sb_%02x" % fd[0], img, center))

    head, _hc = render_sprite(model, anims, 0xC5, 0, dict(yaw=35, pitch=5, anchor=40), px_per_unit=0.36, canvas=96)
    portrait, _pc = render_sprite(model, anims, 0xC5, 0, dict(yaw=40, pitch=5), px_per_unit=0.255)

    pal = build_palette([r[1] for r in rendered], 26)
    final = []
    for key, img, center in rendered:
        img = apply_palette(img, pal)
        img, c = trim(img, center)
        final.append((key, img, c))
    sheet, placed = pack(final, sheet_width=1024)
    save_sheet(sheet, placed, os.path.join(outdir, "character_mario.png"),
               os.path.join(outdir, "character_mario.json"))
    write_anim_script(anims, script_path)

    def to_image(img):
        img, _c = trim(apply_palette(img, pal), (0, 0))
        return Image.fromarray((img * 255).round().astype(np.uint8), "RGBA")

    return to_image(head), to_image(portrait)


def write_anim_script(anims, path):
    """Lemon script with the SM64 animation timing data, indexed by animation id."""
    step = [0] * 256
    count = [0] * 256
    start = [0] * 256
    loop_start = [0] * 256
    loop_end = [1] * 256
    noloop = [1] * 256
    for aid, st, _opts in ANIMS:
        a = anims[aid]
        step[aid] = st
        count[aid] = len(anim_sprite_frames(a, st))
        start[aid] = max(0, a["start"])
        loop_start[aid] = max(0, a["loop_start"])
        loop_end[aid] = max(1, a["loop_end"])
        noloop[aid] = 1 if a["flags"] & 0x01 else 0
    for xid, _aid, frames, _opts in EXTRA:
        step[xid], count[xid] = 1, len(frames)

    def arr(name, typ, values):
        rows = []
        for i in range(0, 256, 16):
            rows.append("\t" + ", ".join(str(v) for v in values[i:i + 16]))
        return "constant array<%s> %s =\n{\n%s\n}\n" % (typ, name, ",\n".join(rows))

    with open(path, "w") as f:
        f.write("// Generated by the mod builder from the Super Mario 64 ROM - do not edit\n")
        f.write("// Timing data of Mario's animations, indexed by SM64 animation id\n\n")
        f.write(arr("MarioAnim.SPRITE_STEP", "u8", step) + "\n")
        f.write(arr("MarioAnim.SPRITE_COUNT", "u8", count) + "\n")
        f.write(arr("MarioAnim.START", "u16", start) + "\n")
        f.write(arr("MarioAnim.LOOP_START", "u16", loop_start) + "\n")
        f.write(arr("MarioAnim.LOOP_END", "u16", loop_end) + "\n")
        f.write(arr("MarioAnim.NO_LOOP", "u8", noloop))
