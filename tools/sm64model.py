"""
Minimal SM64 Mario model loader + software renderer.

Reads Mario's geometry / display lists from the sm64 decompilation source
(actors/mario/model.inc.c), his animations from assets/anims/*.inc.c and
the textures straight out of a US Super Mario 64 ROM (z64, big endian).

Only the subset of F3D that Mario's high-poly model uses is interpreted.
"""

import json
import math
import os
import re
import struct

import numpy as np


# --------------------------------------------------------------------------
# ROM / texture handling
# --------------------------------------------------------------------------

def mio0_decompress(data, offset):
    if data[offset:offset + 4] != b"MIO0":
        raise ValueError("No MIO0 header at 0x%x" % offset)
    dest_size, comp_off, uncomp_off = struct.unpack(">III", data[offset + 4:offset + 16])
    out = bytearray()
    layout = offset + 16
    comp = offset + comp_off
    uncomp = offset + uncomp_off
    bit_idx = 0
    cur = 0
    while len(out) < dest_size:
        if bit_idx == 0:
            cur = struct.unpack(">I", data[layout:layout + 4])[0]
            layout += 4
            bit_idx = 32
        bit_idx -= 1
        if cur & (1 << bit_idx):
            out.append(data[uncomp])
            uncomp += 1
        else:
            v = struct.unpack(">H", data[comp:comp + 2])[0]
            comp += 2
            length = (v >> 12) + 3
            back = (v & 0xFFF) + 1
            start = len(out) - back
            for i in range(length):
                out.append(out[start + i])
    return bytes(out)


def decode_rgba16(raw, w, h):
    px = np.frombuffer(raw[:w * h * 2], dtype=">u2").astype(np.uint32).reshape(h, w)
    r = ((px >> 11) & 0x1F) * 255 // 31
    g = ((px >> 6) & 0x1F) * 255 // 31
    b = ((px >> 1) & 0x1F) * 255 // 31
    a = (px & 1) * 255
    return np.stack([r, g, b, a], axis=-1).astype(np.float32) / 255.0


def load_textures(decomp_dir, rom_path, model_src):
    rom = open(rom_path, "rb").read()
    if rom[:4] != b"\x80\x37\x12\x40":
        raise ValueError("ROM is not a big-endian .z64 image")
    assets = json.load(open(os.path.join(decomp_dir, "assets.json")))
    # Map texture variable -> asset file
    tex_files = dict(re.findall(
        r"static const Texture (\w+)\[\] = \{\s*#include \"(actors/mario/[\w.]+)\.inc\.c\"", model_src))
    blocks = {}
    textures = {}
    for var, path in tex_files.items():
        meta = assets[path + ".png"]
        w, h, size, offs = meta
        blk, inner = offs["us"]
        if blk not in blocks:
            blocks[blk] = mio0_decompress(rom, blk)
        textures[var] = decode_rgba16(blocks[blk][inner:inner + size], w, h)
    return textures


# --------------------------------------------------------------------------
# Source parsing
# --------------------------------------------------------------------------

def _ints(s):
    return [int(x, 0) for x in re.findall(r"-?0x[0-9a-fA-F]+|-?\d+", s)]


def parse_model(src):
    lights = {}
    for name, body in re.findall(r"static const Lights1 (\w+) = gdSPDefLights1\(([^;]*)\);", src):
        v = _ints(body)
        lights[name] = {"a": np.array(v[0:3], np.float32) / 255.0,
                        "d": np.array(v[3:6], np.float32) / 255.0,
                        "dir": np.array([x if x < 128 else x - 256 for x in v[6:9]], np.float32)}
    vtx = {}
    for name, body in re.findall(r"static const Vtx (\w+)\[\] = \{(.*?)\n\};", src, re.S):
        rows = []
        for line in re.findall(r"\{\{\{(.*?)\}\}\}", body):
            v = _ints(line)
            x, y, z, _flag, s, t, nx, ny, nz, a = v
            nx, ny, nz = [c if c < 128 else c - 256 for c in (nx, ny, nz)]
            rows.append((x, y, z, s, t, nx, ny, nz))
        vtx[name] = np.array(rows, np.float32)
    gfx = {}
    for name, body in re.findall(r"const Gfx (\w+)\[\] = \{(.*?)\n\};", src, re.S):
        cmds = []
        for m in re.finditer(r"(gs\w+)\((.*?)\),?\s*$", body, re.M):
            cmds.append((m.group(1), m.group(2)))
        gfx[name] = cmds
    return lights, vtx, gfx


def parse_anims(anim_dir):
    """Returns dict anim_id(int) -> anim dict."""
    anims = {}
    for fn in sorted(os.listdir(anim_dir)):
        if not fn.startswith("anim_") or not fn.endswith(".inc.c"):
            continue
        src = open(os.path.join(anim_dir, fn)).read()
        arrays = {}
        for kind, name, body in re.findall(r"static const (s16|u16) (\w+)\[\] = \{(.*?)\};", src, re.S):
            vals = _ints(body)
            arr = np.array(vals, np.int64)
            if kind == "s16":
                arr = np.where(arr > 32767, arr - 65536, arr)
            arrays[name] = arr
        for name, body in re.findall(r"static const struct Animation (\w+)\[\] = \{(.*?)\};", src, re.S):
            fields = [f.strip() for f in body.split(",") if f.strip()]
            anim_id = int(name.split("_")[1], 16)
            values_name = fields[6]
            index_name = fields[7]
            anims[anim_id] = {
                "flags": int(fields[0], 0),
                "ydiv": int(fields[1], 0),
                "start": int(fields[2], 0),
                "loop_start": int(fields[3], 0),
                "loop_end": int(fields[4], 0),
                "values": arrays[values_name],
                "index": arrays[index_name],
            }
    return anims


# --------------------------------------------------------------------------
# Math helpers (row-vector convention like SM64: v' = v * M)
# --------------------------------------------------------------------------

def sins(a):
    return math.sin(a * math.pi / 32768.0)


def coss(a):
    return math.cos(a * math.pi / 32768.0)


def mtx_rotate_xyz_translate(t, r):
    sx, cx = sins(r[0]), coss(r[0])
    sy, cy = sins(r[1]), coss(r[1])
    sz, cz = sins(r[2]), coss(r[2])
    m = np.zeros((4, 4), np.float64)
    m[0] = [cy * cz, cy * sz, -sy, 0]
    m[1] = [sx * sy * cz - cx * sz, sx * sy * sz + cx * cz, sx * cy, 0]
    m[2] = [cx * sy * cz + sx * sz, cx * sy * sz - sx * cz, cx * cy, 0]
    m[3] = [t[0], t[1], t[2], 1]
    return m


def mtx_scale(s):
    m = np.eye(4)
    m[0, 0] = m[1, 1] = m[2, 2] = s
    return m


# --------------------------------------------------------------------------
# Skeleton for the regular high-poly Mario (actors/mario/geo.inc.c, mario_geo_body)
# --------------------------------------------------------------------------
# Each entry: (parent_index, translation, display_list or callable key)
# Order matches the depth first animated-part traversal of mario_geo_body,
# which is also the order of the animation channels.

SKELETON = [
    (-1, (0, 0, 0), None),                    # 0 root
    (0, (0, 0, 0), "mario_butt"),             # 1
    (1, (68, 0, 0), "mario_torso"),           # 2
    (2, (87, 0, 0), "@face"),                 # 3 head
    (2, (67, -10, 79), None),                 # 4 left shoulder
    (4, (0, 0, 0), "mario_left_arm"),         # 5
    (5, (65, 0, 0), "mario_left_forearm_shared_dl"),  # 6
    (6, (60, 0, 0), "@left_hand"),            # 7
    (2, (68, -10, -79), None),                # 8 right shoulder
    (8, (0, 0, 0), "mario_right_arm"),        # 9
    (9, (65, 0, 0), "mario_right_forearm_shared_dl"),  # 10
    (10, (60, 0, 0), "@right_hand"),          # 11
    (1, (13, -8, 42), None),                  # 12 left hip
    (12, (0, 0, 0), "mario_left_thigh"),      # 13
    (13, (89, 0, 0), "mario_left_leg_shared_dl"),  # 14
    (14, (67, 0, 0), "mario_left_foot"),      # 15
    (1, (13, -8, -42), None),                 # 16 right hip
    (16, (0, 0, 0), "mario_right_thigh"),     # 17
    (17, (89, 0, 0), "mario_right_leg_shared_dl"),  # 18
    (18, (67, 0, 0), "mario_right_foot"),     # 19
]

EYES = {
    "front": "mario_cap_on_eyes_front",
    "half": "mario_cap_on_eyes_half_closed",
    "closed": "mario_cap_on_eyes_closed",
    "dead": "mario_cap_on_eyes_dead",
}
LEFT_HAND = {"fist": "mario_left_hand_closed", "open": "mario_left_hand_open"}
RIGHT_HAND = {"fist": "mario_right_hand_closed", "open": "mario_right_hand_open",
              "peace": "mario_right_hand_peace"}


def anim_value(anim, attr_idx, frame):
    count = anim["index"][attr_idx * 2]
    off = anim["index"][attr_idx * 2 + 1]
    f = frame if frame < count else count - 1
    return float(anim["values"][off + f])


def pose_matrices(anim, frame, overrides=None, lateral=False):
    """Compute world matrices for every skeleton node (Mario model space, pre-scale)."""
    flags = anim["flags"]
    attr = 0
    mats = []
    for i, (parent, trans, _dl) in enumerate(SKELETON):
        t = list(trans)
        if i == 0:
            # Root translation, see geo_set_animation_globals / geo_process_animated_part
            mult = 189.0 / anim["ydiv"] if anim["ydiv"] else 1.0
            if flags & 0x08:            # ANIM_FLAG_HOR_TRANS -> vertical translation only
                t[1] += anim_value(anim, attr + 1, frame) * mult
            elif flags & 0x10:          # ANIM_FLAG_VERT_TRANS -> lateral translation only
                t[0] += anim_value(anim, attr, frame) * mult
                t[2] += anim_value(anim, attr + 2, frame) * mult
            elif flags & 0x40:          # ANIM_FLAG_6 -> no translation
                pass
            else:
                t[0] += anim_value(anim, attr, frame) * mult
                t[1] += anim_value(anim, attr + 1, frame) * mult
                t[2] += anim_value(anim, attr + 2, frame) * mult
            attr += 3
            if not lateral:
                t[0] = 0.0
                t[2] = 0.0
        r = [anim_value(anim, attr, frame), anim_value(anim, attr + 1, frame), anim_value(anim, attr + 2, frame)]
        attr += 3
        if overrides and i in overrides:
            r = [r[k] + overrides[i][k] for k in range(3)]
        local = mtx_rotate_xyz_translate(t, r)
        mats.append(local if parent < 0 else local @ mats[parent])
    return mats


def anim_num_frames(anim):
    return max(1, anim["loop_end"])


# --------------------------------------------------------------------------
# Display list interpreter -> triangle soup
# --------------------------------------------------------------------------

class TriSoup:
    def __init__(self):
        self.pos = []      # (3,3) world positions
        self.nrm = []      # (3,3) world normals
        self.uv = []       # (3,2) texel coords
        self.mat = []      # material record
        self.cull = []


def interpret_dl(model, dl_name, matrix, state, soup):
    lights, vtx, gfx, textures = model
    nmat = matrix[:3, :3]
    for cmd, args in gfx[dl_name]:
        if cmd == "gsSPDisplayList":
            interpret_dl(model, args.strip(), matrix, state, soup)
        elif cmd == "gsSPEndDisplayList":
            return
        elif cmd == "gsSPLight":
            m = re.match(r"&(\w+)\.(\w)\s*,\s*(\d+)", args.strip())
            lname, part, _n = m.groups()
            if part == "l":
                state["diffuse"] = lights[lname]["d"]
                state["dir"] = lights[lname]["dir"]
            else:
                state["ambient"] = lights[lname]["a"]
        elif cmd == "gsDPSetCombineMode":
            state["combine"] = args.split(",")[0].strip()
        elif cmd == "gsSPTexture":
            state["tex_on"] = "G_ON" in args
            a = args.split(",")
            state["tex_scale"] = (int(a[0], 0) / 65536.0, int(a[1], 0) / 65536.0)
        elif cmd == "gsDPSetTextureImage":
            state["teximg"] = args.split(",")[-1].strip()
        elif cmd == "gsDPLoadTextureBlock":
            state["teximg"] = args.split(",")[0].strip()
        elif cmd == "gsSPSetGeometryMode":
            if "G_TEXTURE_GEN" in args:
                state["texgen"] = True
            if "G_CULL_BACK" in args:
                state["cull"] = True
        elif cmd == "gsSPClearGeometryMode":
            if "G_TEXTURE_GEN" in args:
                state["texgen"] = False
            if "G_CULL_BACK" in args:
                state["cull"] = False
        elif cmd == "gsSPVertex":
            a = [x.strip() for x in args.split(",")]
            name, n, v0 = a[0], int(a[1], 0), int(a[2], 0)
            arr = vtx[name][:n]
            p = np.hstack([arr[:, 0:3], np.ones((n, 1))]) @ matrix
            nn = arr[:, 5:8] @ nmat
            ln = np.linalg.norm(nn, axis=1, keepdims=True)
            nn = nn / np.maximum(ln, 1e-6)
            for k in range(n):
                state["vbuf"][v0 + k] = (p[k, :3], nn[k], arr[k, 3:5] / 32.0)
        elif cmd in ("gsSP1Triangle", "gsSP2Triangles"):
            v = _ints(args)
            tris = [v[0:3]] if cmd == "gsSP1Triangle" else [v[0:3], v[4:7]]
            for tri in tris:
                verts = [state["vbuf"][i] for i in tri]
                soup.pos.append(np.array([x[0] for x in verts]))
                soup.nrm.append(np.array([x[1] for x in verts]))
                soup.uv.append(np.array([x[2] for x in verts]))
                tex = textures.get(state.get("teximg")) if state.get("tex_on") else None
                soup.mat.append({
                    "ambient": state["ambient"].copy(),
                    "diffuse": state["diffuse"].copy(),
                    "combine": state.get("combine", "G_CC_SHADE"),
                    "tex": tex,
                })
                soup.cull.append(state.get("cull", True))
        # everything else (sync, tiles, etc) is irrelevant for us


def build_soup(model, mats, eyes="front", lhand="fist", rhand="fist"):
    soup = TriSoup()
    state = {"ambient": np.array([0.5, 0.5, 0.5]), "diffuse": np.array([1.0, 1.0, 1.0]),
             "vbuf": [None] * 32, "cull": True}
    scale = mtx_scale(0.25)
    for i, (_p, _t, dl) in enumerate(SKELETON):
        if dl is None:
            continue
        m = mats[i] @ scale
        if dl == "@face":
            interpret_dl(model, EYES[eyes], m, state, soup)
        elif dl == "@left_hand":
            interpret_dl(model, LEFT_HAND[lhand], m, state, soup)
        elif dl == "@right_hand":
            interpret_dl(model, RIGHT_HAND[rhand], m, state, soup)
        else:
            interpret_dl(model, dl, m, state, soup)
    return soup


def load_model(decomp_dir, rom_path):
    src = open(os.path.join(decomp_dir, "actors/mario/model.inc.c")).read()
    lights, vtx, gfx = parse_model(src)
    textures = load_textures(decomp_dir, rom_path, src)
    anims = parse_anims(os.path.join(decomp_dir, "assets/anims"))
    return (lights, vtx, gfx, textures), anims


# --------------------------------------------------------------------------
# Rasterizer
# --------------------------------------------------------------------------

def render(soup, view, size, px_per_unit, origin, light_dir, ss=4):
    """
    view: 3x3 rotation applied to model space (row vectors) -> camera space
          camera space: x right, y up, z towards viewer
    origin: pixel position (x, y) of model origin (the feet) in output image
    Returns (rgba float image [H, W, 4]) at size*ss resolution.
    """
    W, H = size[0] * ss, size[1] * ss
    color = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)
    zbuf = np.full((H, W), -1e9, np.float32)
    k = px_per_unit * ss
    ox, oy = origin[0] * ss, origin[1] * ss
    L = np.array(light_dir, np.float64)
    L = L / np.linalg.norm(L)
    for tri_pos, tri_nrm, tri_uv, mat, cull in zip(soup.pos, soup.nrm, soup.uv, soup.mat, soup.cull):
        cp = tri_pos @ view
        cn = tri_nrm @ view
        sx = ox + cp[:, 0] * k
        sy = oy - cp[:, 1] * k
        sz = cp[:, 2]
        # signed area (screen y down) - counter clockwise in camera space is front facing
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(area) < 1e-9:
            continue
        if cull and area > 0:
            continue
        x0 = max(int(math.floor(sx.min())), 0)
        x1 = min(int(math.ceil(sx.max())), W - 1)
        y0 = max(int(math.floor(sy.min())), 0)
        y1 = min(int(math.ceil(sy.max())), H - 1)
        if x0 > x1 or y0 > y1:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        w0 = ((sx[1] - xs) * (sy[2] - ys) - (sx[2] - xs) * (sy[1] - ys)) / area
        w1 = ((sx[2] - xs) * (sy[0] - ys) - (sx[0] - xs) * (sy[2] - ys)) / area
        w2 = 1.0 - w0 - w1
        inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
        if not inside.any():
            continue
        z = w0 * sz[0] + w1 * sz[1] + w2 * sz[2]
        zb = zbuf[y0:y1 + 1, x0:x1 + 1]
        upd = inside & (z > zb)
        if not upd.any():
            continue
        # per-vertex shading (gouraud), like the N64 RSP lighting
        shade_v = []
        for vi in range(3):
            n = cn[vi]
            d = max(0.0, float(np.dot(n, L)))
            c = mat["ambient"] * 0.7 + mat["diffuse"] * (0.15 + 0.95 * d)
            shade_v.append(np.clip(c, 0, 1))
        shade_v = np.array(shade_v)
        shade = (w0[..., None] * shade_v[0] + w1[..., None] * shade_v[1] + w2[..., None] * shade_v[2])
        out = shade
        if mat["tex"] is not None and "SHADEFADEA" not in mat["combine"] and mat["combine"] != "G_CC_SHADE":
            tex = mat["tex"]
            th, tw = tex.shape[:2]
            u = w0 * tri_uv[0, 0] + w1 * tri_uv[1, 0] + w2 * tri_uv[2, 0]
            v = w0 * tri_uv[0, 1] + w1 * tri_uv[1, 1] + w2 * tri_uv[2, 1]
            ui = np.clip(np.floor(u).astype(int), 0, tw - 1)
            vi_ = np.clip(np.floor(v).astype(int), 0, th - 1)
            texel = tex[vi_, ui]
            if "BLENDRGB" in mat["combine"]:
                ta = texel[..., 3:4]
                out = shade * (1 - ta) + texel[..., :3] * ta
            elif "DECAL" in mat["combine"]:
                out = texel[..., :3]
            else:  # modulate
                out = shade * texel[..., :3]
        cb = color[y0:y1 + 1, x0:x1 + 1]
        cb[upd] = out[upd]
        zb[upd] = z[upd]
        alpha[y0:y1 + 1, x0:x1 + 1][upd] = 1.0
    return np.dstack([color, alpha])


def view_matrix(yaw_deg, pitch_deg=0.0, roll_deg=0.0):
    """Model -> camera rotation (row-vector convention)."""
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    r = math.radians(roll_deg)
    # yaw around Y: facing +Z rotated towards +X
    ry = np.array([[math.cos(y), 0, -math.sin(y)],
                   [0, 1, 0],
                   [math.sin(y), 0, math.cos(y)]])
    rx = np.array([[1, 0, 0],
                   [0, math.cos(p), math.sin(p)],
                   [0, -math.sin(p), math.cos(p)]])
    rz = np.array([[math.cos(r), math.sin(r), 0],
                   [-math.sin(r), math.cos(r), 0],
                   [0, 0, 1]])
    return ry @ rx @ rz
