"""
Builds the "Mario 64" Sonic 3 A.I.R. mod from your own game files.

Usage:
    python3 tools/build_mod.py --sm64-decomp <sm64 decomp dir> --sm64-rom <Super Mario 64 (U).z64>
                               --s3air <sonic3air_game dir> [--out build]

Inputs:
  - sm64 decomp source (https://github.com/n64decomp/sm64), for Mario's model and animations
  - a US Super Mario 64 ROM (z64), for textures and voice clips
  - the Sonic 3 A.I.R. game folder, for the HUD font sprites used to compose "MARIO" texts

Output:
  build/Mario64/          - the mod folder, ready to copy into the S3AIR "mods" folder
  build/Mario64.zip       - the same as zip
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_sprites  # noqa: E402


MOD_NAME = "Mario64"


# --------------------------------------------------------------------------
# Text sprites: "MARIO" composed from the game's own HUD / results font
# --------------------------------------------------------------------------

def segment_glyphs(img, y0, y1):
    """Split a text line into glyph column ranges (separated by fully transparent columns)."""
    a = img[y0:y1, :, 3] > 0
    used = a.any(axis=0)
    glyphs = []
    x = 0
    while x < len(used):
        if used[x]:
            s = x
            while x < len(used) and used[x]:
                x += 1
            glyphs.append((s, x))
        else:
            x += 1
    return glyphs


def _glyph_runs(img, y0, x0, w):
    """Letters of a nameplate word: column runs of letter body pixels (the outlines overlap)."""
    b = img[y0:y0 + 16, x0:x0 + w]
    body = ((b[..., 3] > 0) & (b[..., 2] > 100)).sum(axis=0)
    runs = []
    x = 0
    while x < w:
        if body[x] > 0:
            s = x
            while x < w and body[x] > 0:
                x += 1
            runs.append((x0 + s, x0 + x))
        else:
            x += 1
    return runs


def make_result_nameplate(s3air_sprites):
    img = np.array(Image.open(os.path.join(s3air_sprites, "result_sprites.png")).convert("RGBA"))
    sonic = _glyph_runs(img, 8, 8, 72)      # S O N I C
    miles = _glyph_runs(img, 40, 80, 72)    # M I L E S
    supr = _glyph_runs(img, 8, 88, 80)      # S U P E R
    tails = _glyph_runs(img, 40, 8, 64)     # [TA] I L S  (T and A touch each other)
    ta0, ta1 = tails[0]
    pick = [(40, miles[0]), (40, (ta0 + 12, ta1)), (8, supr[4]), (40, miles[1]), (8, sonic[1])]
    OUTLINE = 2
    total = sum(e - s for _y, (s, e) in pick) + 3 * (len(pick) - 1) + 2 * OUTLINE
    out = np.zeros((16, total, 4), np.uint8)
    x = OUTLINE
    for y, (s, e) in pick:
        part = img[y:y + 16, s - OUTLINE:e + OUTLINE]
        dst = out[:, x - OUTLINE:x - OUTLINE + part.shape[1]]
        # Body pixels win over outline pixels of the neighbor letter
        body = (part[..., 3] > 0) & (part[..., 2] > 100)
        outline = (part[..., 3] > 0) & ~body & (dst[..., 3] == 0)
        dst[body] = part[body]
        dst[outline] = part[outline]
        x += (e - s) + 3
    return Image.fromarray(out, "RGBA")


# Small HUD font (lives icon), drawn in the colors of the original lives icon text
HUD_FONT = {
    "M": ["10001", "11011", "10101", "10001", "10001", "10001"],
    "A": ["0110", "1001", "1001", "1111", "1001", "1001"],
    "R": ["1110", "1001", "1001", "1110", "1010", "1001"],
    "I": ["11", "11", "11", "11", "11", "11"],
    "O": ["0110", "1001", "1001", "1001", "1001", "0110"],
}


def make_hud_glyph(rows):
    yellow = np.array([252, 252, 0, 255], np.uint8)
    white = np.array([252, 252, 252, 255], np.uint8)
    shadow = np.array([72, 72, 108, 255], np.uint8)
    h, w = len(rows), len(rows[0])
    out = np.zeros((h + 1, w + 1, 4), np.uint8)
    for y in range(h):
        for x in range(w):
            if rows[y][x] == "1":
                out[y, x] = white if y in (2, 3) else yellow
    for y in range(h + 1):
        for x in range(w + 1):
            if out[y, x, 3] == 0:
                left = x > 0 and y < h and rows[y][x - 1] == "1"
                up = y > 0 and x < w and rows[y - 1][x] == "1"
                if left or up:
                    out[y, x] = shadow
    return out


def make_lives_icon(s3air_sprites, head_img):
    lives = np.array(Image.open(os.path.join(s3air_sprites, "hud_life_sprites.png")).convert("RGBA"))
    icon = np.zeros((16, 48, 4), np.uint8)
    # Head portrait (16x16 with the dark frame lines at top & bottom, like the originals)
    frame = lives[16:32, 0:16].copy()
    portrait = np.zeros((16, 16, 4), np.uint8)
    portrait[0, :] = frame[0, :]
    portrait[15, :] = frame[15, :]
    h = np.array(head_img)
    ph, pw = h.shape[:2]
    # Fit the head into the 14 rows between the frame lines
    sub = h[:14, :16]
    bg = np.array([252, 252, 252, 255], np.uint8)
    portrait[1:15, :] = bg
    sh, sw = sub.shape[:2]
    region = portrait[1:1 + sh, 0:sw]
    mask = sub[..., 3] > 0
    region[mask] = sub[mask]
    icon[:, 0:16] = portrait

    # Text "MARIO"
    letters = [make_hud_glyph(HUD_FONT[c]) for c in "MARIO"]
    total = sum(g.shape[1] for g in letters)
    x = 17 + max(0, (31 - total) // 2)
    for g in letters:
        dst = icon[1:8, x:x + g.shape[1]]
        m = g[..., 3] > 0
        dst[m] = g[m]
        x += g.shape[1]
    # The small "x" below the name
    icon[8:16, 16:48] = lives[16 + 8:32, 16:48]
    return Image.fromarray(icon, "RGBA")


# --------------------------------------------------------------------------
# Voice clips
# --------------------------------------------------------------------------

VOICES = {
    "mario_yah": "sfx_mario/02_mario_yah",
    "mario_hoo": "sfx_mario/00_mario_jump_hoo",
    "mario_wah": "sfx_mario/01_mario_jump_wah",
    "mario_yahoo": "sfx_mario/04_mario_yahoo",
    "mario_wahoo": "sfx_mario/18_mario_waha",
    "mario_ooof": "sfx_mario/0B_mario_ooof",
    "mario_mammamia": "sfx_mario_peach/03_mario_dying",
    "mario_herewego": "sfx_mario/0C_mario_here_we_go",
    "mario_yippee": "sfx_mario/19_mario_yippee",
}


def extract_voices(decomp, rom, outdir):
    assets = json.load(open(os.path.join(decomp, "assets.json")))
    ctl = assets["@sound ctl us"]
    tbl = assets["@sound tbl us"]
    work = tempfile.mkdtemp(prefix="sm64snd_")
    try:
        os.makedirs(os.path.join(work, "tools"))
        shutil.copy(os.path.join(decomp, "tools", "disassemble_sound.py"), os.path.join(work, "tools"))
        subprocess.check_call(["gcc", "-O2", "-o", os.path.join(work, "tools", "aifc_decode"),
                               os.path.join(decomp, "tools", "aifc_decode.c"), "-lm"])
        args = [sys.executable, "-I", os.path.join(work, "tools", "disassemble_sound.py"), os.path.abspath(rom),
                str(ctl[1]["us"][0]), str(ctl[0]), str(tbl[1]["us"][0]), str(tbl[0]), "--only-samples"]
        for key, path in VOICES.items():
            asset = "sound/samples/%s.aiff" % path
            args.append("%s:%d" % (asset, assets[asset][1]["us"][1]))
        subprocess.check_call(args, cwd=work)
        entries = {}
        for key, path in VOICES.items():
            src = os.path.join(work, "sound", "samples", path + ".aiff")
            dst = os.path.join(outdir, key + ".ogg")
            subprocess.check_call(["ffmpeg", "-v", "error", "-y", "-i", src, "-ar", "48000", "-ac", "1",
                                   "-c:a", "libvorbis", "-q:a", "5", dst])
            entries[key] = {"File": key + ".ogg", "Type": "Sound"}
        with open(os.path.join(outdir, "audio_replacements.json"), "w") as f:
            f.write("{\n" + ",\n".join('\t"%s": { "File": "%s", "Type": "Sound" }' % (k, v["File"])
                                         for k, v in entries.items()) + "\n}\n")
    finally:
        shutil.rmtree(work, ignore_errors=True)


# --------------------------------------------------------------------------

def append_sprite_json(json_path, png_name, key, img, center):
    w, h = img.size
    with open(json_path) as f:
        text = f.read().rstrip().rstrip("}").rstrip()
    text += ',\n\t"%s": { "File": "%s", "Rect": "0,0,%d,%d", "Center": "%d,%d" }\n}\n' % (key, png_name, w, h, center[0], center[1])
    with open(json_path, "w") as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sm64-decomp", required=True)
    ap.add_argument("--sm64-rom", required=True)
    ap.add_argument("--s3air", required=True, help="Sonic 3 A.I.R. game folder (containing doc/modding)")
    ap.add_argument("--out", default=os.path.join(REPO, "build"))
    ap.add_argument("--no-voices", action="store_true")
    args = ap.parse_args()

    s3air_sprites = os.path.join(args.s3air, "doc", "modding", "sprites")
    moddir = os.path.join(args.out, MOD_NAME)
    if os.path.exists(moddir):
        shutil.rmtree(moddir)
    shutil.copytree(os.path.join(REPO, "mod"), moddir)
    sprites = os.path.join(moddir, "sprites")
    os.makedirs(sprites, exist_ok=True)

    # Character sprites
    print("Rendering Mario sprites...")
    sys.argv = ["gen_sprites.py", args.sm64_decomp, args.sm64_rom, sprites]
    gen_sprites.main()

    # Icons
    head = Image.open(os.path.join(sprites, "mario_icon_head_raw.png"))
    portrait = Image.open(os.path.join(sprites, "mario_icon_portrait_raw.png"))
    pc = tuple(int(v) for v in open(os.path.join(sprites, "mario_icon_portrait_raw.center")).read().split(","))
    for fn in os.listdir(sprites):
        if fn.startswith("mario_icon_") or fn == "mario_frame_counts.json":
            os.remove(os.path.join(sprites, fn))

    # Head for the lives icon: crop the head of the high-res render and scale it to 16x14
    hb = head.crop((0, 0, head.width, int(head.height * 0.40)))
    bb = hb.getbbox()
    hb = hb.crop(bb)
    scale = min(16.0 / hb.width, 14.0 / hb.height)
    head_small = hb.resize((max(1, int(round(hb.width * scale))), max(1, int(round(hb.height * scale)))), Image.LANCZOS)
    hs = np.array(head_small)
    hs[..., 3] = np.where(hs[..., 3] >= 128, 255, 0)
    canvas = np.zeros((14, 16, 4), np.uint8)
    oy, ox = 14 - hs.shape[0], (16 - hs.shape[1]) // 2
    canvas[oy:oy + hs.shape[0], ox:ox + hs.shape[1]] = hs
    head_small = Image.fromarray(canvas, "RGBA")
    lives = make_lives_icon(s3air_sprites, head_small)
    lives.save(os.path.join(sprites, "hud_mario.png"))
    with open(os.path.join(sprites, "hud_mario.json"), "w") as f:
        f.write('{\n\t"hud_lives_icon_mario": { "File": "hud_mario.png", "Rect": "0,0,48,16" }\n}\n')

    plate = make_result_nameplate(s3air_sprites)
    plate.save(os.path.join(sprites, "result_mario.png"))
    with open(os.path.join(sprites, "result_mario.json"), "w") as f:
        f.write('{\n\t"result_nameplate_mario": { "File": "result_mario.png", "Rect": "0,0,%d,16", "Center": "-1,0" }\n}\n' % plate.width)

    # Data Select portrait: bottom center anchored
    portrait.save(os.path.join(sprites, "dataselect_mario.png"))
    with open(os.path.join(sprites, "dataselect_mario.json"), "w") as f:
        f.write('{\n\t"mario_dataselect": { "File": "dataselect_mario.png", "Rect": "0,0,%d,%d", "Center": "%d,%d" }\n}\n'
                % (portrait.width, portrait.height, portrait.width // 2 + 2, portrait.height))

    # Mod icons
    icon = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    p2 = portrait.resize((portrait.width * 64 // max(portrait.size), portrait.height * 64 // max(portrait.size)), Image.NEAREST)
    icon.alpha_composite(p2, ((64 - p2.width) // 2, 64 - p2.height))
    icon.save(os.path.join(moddir, "icon.png"))
    icon.save(os.path.join(moddir, "icon-64px.png"))
    icon16 = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    icon16.alpha_composite(head_small.crop((0, 0, 16, min(16, head_small.height))), (0, 0))
    icon16.save(os.path.join(moddir, "icon-16px.png"))

    if not args.no_voices:
        print("Extracting voice clips...")
        audio = os.path.join(moddir, "audio")
        os.makedirs(audio, exist_ok=True)
        extract_voices(args.sm64_decomp, args.sm64_rom, audio)

    # Zip
    zpath = os.path.join(args.out, MOD_NAME + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _dirs, files in os.walk(moddir):
            for fn in sorted(files):
                full = os.path.join(root, fn)
                z.write(full, os.path.relpath(full, args.out))
    print("Done: %s" % zpath)


if __name__ == "__main__":
    main()
