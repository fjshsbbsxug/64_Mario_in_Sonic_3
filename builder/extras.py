"""
Mario versions of the other character graphics that Sonic 3 A.I.R. shows for Sonic:
signpost, end pose (after the credits), Blue Sphere special stage, continue screen and Tornado.

The sprite keys and sizes follow Sonic's sprites (see doc/modding/sprites in the game folder),
the mod's scripts make the game use them for Mario.
"""

import math
import os

import numpy as np
from PIL import Image

import model as mdl
import sprites as sp


BACK_YAW = 188          # seen from behind (Blue Sphere)
FRONT_YAW = 40          # turned towards the camera
RUN = 0x72
IDLE = 0xC5
STAR_DANCE = 0xCD
SPIN = 0x6F             # forward somersault
OPEN = dict(lhand="open", rhand="open")


def render(model, anims, anim, frame, opts, px_per_unit, canvas=96, anchor=None):
    """Renders a pose; returns the trimmed image and the feet position inside it."""
    opts = dict(opts)
    opts.setdefault("anchor", canvas // 2 - 4 if anchor is None else anchor)
    img, center = sp.render_sprite(model, anims, anim, frame, opts, px_per_unit=px_per_unit, canvas=canvas)
    feet = (center[0], center[1] + opts["anchor"])
    img, offset = sp.trim(img, feet)
    return img, offset


def place(img, feet, size, center):
    """Puts an image into a fixed-size frame so that the feet end up at the given position."""
    w, h = size
    out = np.zeros((h, w, 4), np.float32)
    ox, oy = center[0] - feet[0], center[1] - feet[1]
    ih, iw = img.shape[:2]
    for y in range(ih):
        ty = oy + y
        if 0 <= ty < h:
            x0, x1 = max(0, -ox), min(iw, w - ox)
            if x0 < x1:
                out[ty, ox + x0:ox + x1] = img[y, x0:x1]
    return out


def fit_bottom(img, feet, size, margin=1):
    """Frame of the given size with the image centered horizontally, standing on the bottom edge."""
    w, h = size
    ih, iw = img.shape[:2]
    return place(img, feet, size, (w // 2 + (feet[0] - iw // 2), h - margin - (ih - feet[1])))


def signpost(model, anims, head):
    """48x32 signpost face: Mario's head on a sky-blue panel with a dark border."""
    w, h = 48, 32
    out = np.zeros((h, w, 4), np.float32)
    out[:, :] = (0.10, 0.10, 0.35, 1.0)
    out[2:h - 2, 2:w - 2] = (0.42, 0.71, 0.99, 1.0)
    out[2:4, 2:w - 2] = (0.70, 0.86, 1.0, 1.0)
    hd = head.astype(np.float32) / 255.0
    hh, hw = hd.shape[:2]
    scale = min(28.0 / hh, 40.0 / hw)
    small = np.array(Image.fromarray(head).resize((max(1, round(hw * scale)), max(1, round(hh * scale))), Image.LANCZOS)).astype(np.float32) / 255.0
    sh, sw = small.shape[:2]
    ox, oy = (w - sw) // 2, h - 2 - sh
    mask = small[..., 3] >= 0.5
    region = out[oy:oy + sh, ox:ox + sw]
    region[mask, :3] = small[mask, :3]
    return out


def head_only(body_img):
    """Crops Mario's head (top part) out of a full body render, like the lives icon."""
    img = body_img[:int(body_img.shape[0] * 0.42)]
    ys, xs = np.where(img[..., 3] > 0)
    return img[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def render_extras(model, anims, body_img):
    """Returns a list of (key, float RGBA image, center)."""
    sprites = []
    head_img = head_only(body_img)

    def add(key, img, center):
        sprites.append((key, img, center))

    # Signpost
    add("signpost_mario", signpost(model, anims, head_img), (24, 16))

    # End pose after the credits: Mario's star dance pose (peace sign), small and big
    pose_frame = 28
    pose = dict(yaw=FRONT_YAW, pitch=5, lhand="open", rhand="peace")
    small, feet = render(model, anims, STAR_DANCE, pose_frame, pose, 0.42, canvas=96)
    add("endpose_mario_0x00", fit_bottom(small, feet, (48, 72)), (24, 36))
    big, feet = render(model, anims, STAR_DANCE, pose_frame, pose, 0.72, canvas=160, anchor=74)
    add("endpose_mario_0x01", fit_bottom(big, feet, (88, 128)), (44, 64))

    # Blue Sphere: seen from behind; 0x01 standing, 0x02 - 0x08 running, 0x09 - 0x0b jumping
    bs_scale = 0.30
    bs_opts = dict(yaw=BACK_YAW, pitch=22)
    img, feet = render(model, anims, IDLE, 0, bs_opts, bs_scale)
    add("bluesphere_mario_0x01", fit_bottom(img, feet, (32, 40)), (16, 35))
    loop_end = max(1, anims[RUN]["loop_end"])
    for i in range(7):
        img, feet = render(model, anims, RUN, i * loop_end // 7, bs_opts, bs_scale)
        add("bluesphere_mario_0x%02x" % (i + 2), fit_bottom(img, feet, (32, 56), margin=4), (16, 43))
    spin_end = max(1, anims[SPIN]["loop_end"])
    for i in range(3):
        img, feet = render(model, anims, SPIN, 2 + i * spin_end // 4, dict(bs_opts, **OPEN), bs_scale * 0.8)
        frame = np.zeros((32, 32, 4), np.float32)
        ih, iw = img.shape[:2]
        oy, ox = max(0, (32 - ih) // 2), max(0, (32 - iw) // 2)
        frame[oy:oy + min(ih, 32), ox:ox + min(iw, 32)] = img[:32, :32]
        add("bluesphere_mario_0x%02x" % (i + 9), frame, (16, 38))

    # Continue screen: Mario waiting (two frames), and the small icons
    idle_end = max(1, anims[IDLE]["loop_end"])
    for i in range(2):
        img, feet = render(model, anims, IDLE, i * idle_end // 2, dict(yaw=FRONT_YAW, pitch=5), 0.26)
        add("character_mario_continue_0x%02x" % i, fit_bottom(img, feet, (24, 40)), (12, 20))
        img, feet = render(model, anims, IDLE, i * idle_end // 2, dict(yaw=FRONT_YAW, pitch=5), 0.15)
        add("continue_icon_mario_wait_0x%02x" % i, fit_bottom(img, feet, (24, 24)), (12, 12))
    img, feet = render(model, anims, IDLE, 0, dict(yaw=FRONT_YAW, pitch=5), 0.15)
    add("continue_icon_mario", fit_bottom(img, feet, (20, 24), margin=0), (12, 24))

    # Tornado: Mario as pilot (head and shoulders above the cockpit) and standing on the wings
    hd = head_img.astype(np.float32) / 255.0
    for key, size, center in (("tornado_mario_pilot", (32, 16), (20, 8)), ("tornado_mario_pilot_small", (16, 8), (8, 4))):
        w, h = size
        hh, hw = hd.shape[:2]
        scale = min(float(h) / (hh * 0.75), float(w) / hw)
        small = np.array(Image.fromarray(head_img).resize((max(1, round(hw * scale)), max(1, round(hh * scale))), Image.LANCZOS)).astype(np.float32) / 255.0
        small[..., 3] = (small[..., 3] >= 0.5).astype(np.float32)
        frame = np.zeros((h, w, 4), np.float32)
        sh, sw = small.shape[:2]
        ox = max(0, center[0] - sw // 2)
        part = small[:h, :min(sw, w - ox)]
        frame[0:part.shape[0], ox:ox + part.shape[1]] = part
        add(key, frame, center)
    img, feet = render(model, anims, IDLE, 0, dict(yaw=FRONT_YAW, pitch=5), 0.15)
    add("tornado_mario_small", fit_bottom(img, feet, (16, 24), margin=0), (8, 12))

    return sprites


def write_extras(model, anims, body_img, sprites_dir):
    """Renders the extra sprites into mario_extra.png / .json (colors snapped to 5 bits per channel)."""
    sprites = render_extras(model, anims, body_img)
    sheet, placed = sp.pack([(k, np.dstack([np.round(i[..., :3] * 31) / 31, (i[..., 3] >= 0.5).astype(np.float32)]), c)
                             for k, i, c in sprites], sheet_width=256)
    sp.save_sheet(sheet, placed, os.path.join(sprites_dir, "mario_extra.png"), os.path.join(sprites_dir, "mario_extra.json"))
