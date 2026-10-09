"""
Mario's model straight from the ROM, and a small software renderer for it.

The model is described by F3D display lists in segment 0x04. This module interprets
the subset of F3D commands that Mario's model uses and turns it into a triangle list,
which then gets rasterized with simple N64-like lighting.
"""

import math
import struct

import numpy as np

from rom import decode_rgba16


# Segment 0x04 addresses of the display lists of Mario's high-poly model parts
DL = {
    "butt": 0x0400CC98,
    "torso": 0x04010370,
    "eyes_front": 0x040119A0,
    "eyes_half": 0x04011A90,
    "eyes_closed": 0x04011B80,
    "eyes_dead": 0x04012030,
    "left_arm": 0x0400D1D8,
    "left_forearm": 0x0400D2F8,
    "left_hand_fist": 0x0400D8F0,
    "left_hand_open": 0x04019CA0,
    "right_arm": 0x0400DDE8,
    "right_forearm": 0x0400DF08,
    "right_hand_fist": 0x0400E458,
    "right_hand_open": 0x0401A428,
    "right_hand_peace": 0x0401BF30,
    "left_thigh": 0x0400E7B0,
    "left_leg": 0x0400E918,
    "left_foot": 0x0400ECA0,
    "right_thigh": 0x0400EFB8,
    "right_leg": 0x0400F1D8,
    "right_foot": 0x0400F4E8,
}

# Skeleton of the regular Mario model (mario_geo_body): parent, translation, part.
# The order matches the animation channels.
SKELETON = [
    (-1, (0, 0, 0), None),               # 0 root
    (0, (0, 0, 0), "butt"),              # 1
    (1, (68, 0, 0), "torso"),            # 2
    (2, (87, 0, 0), "@eyes"),            # 3 head
    (2, (67, -10, 79), None),            # 4 left shoulder
    (4, (0, 0, 0), "left_arm"),          # 5
    (5, (65, 0, 0), "left_forearm"),     # 6
    (6, (60, 0, 0), "@left_hand"),       # 7
    (2, (68, -10, -79), None),           # 8 right shoulder
    (8, (0, 0, 0), "right_arm"),         # 9
    (9, (65, 0, 0), "right_forearm"),    # 10
    (10, (60, 0, 0), "@right_hand"),     # 11
    (1, (13, -8, 42), None),             # 12 left hip
    (12, (0, 0, 0), "left_thigh"),       # 13
    (13, (89, 0, 0), "left_leg"),        # 14
    (14, (67, 0, 0), "left_foot"),       # 15
    (1, (13, -8, -42), None),            # 16 right hip
    (16, (0, 0, 0), "right_thigh"),      # 17
    (17, (89, 0, 0), "right_leg"),       # 18
    (18, (67, 0, 0), "right_foot"),      # 19
]

G_CULL_BACK = 0x00002000


# --------------------------------------------------------------------------
# Animation
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


def anim_num_frames(anim):
    return max(1, anim["loop_end"])


def _anim_value(anim, channel, frame):
    count = anim["index"][channel * 2]
    off = anim["index"][channel * 2 + 1]
    return float(anim["values"][off + min(frame, count - 1)])


def pose_matrices(anim, frame):
    """World matrices of all skeleton nodes (row-vector convention like SM64: v' = v * M)."""
    flags = anim["flags"]
    ch = 0
    mats = []
    for i, (parent, trans, _part) in enumerate(SKELETON):
        t = list(trans)
        if i == 0:
            # Root translation: keep only the vertical part, the sprite stays centered horizontally
            mult = 189.0 / anim["ydiv"] if anim["ydiv"] else 1.0
            if not (flags & 0x10) and not (flags & 0x40):
                t[1] += _anim_value(anim, ch + 1, frame) * mult
            ch += 3
        r = [_anim_value(anim, ch + k, frame) for k in range(3)]
        ch += 3
        local = mtx_rotate_xyz_translate(t, r)
        mats.append(local if parent < 0 else local @ mats[parent])
    return mats


# --------------------------------------------------------------------------
# Display list interpreter
# --------------------------------------------------------------------------

class Model:
    def __init__(self, segment):
        self.seg = segment
        self.textures = {}

    def u32(self, addr):
        o = addr & 0x00FFFFFF
        return struct.unpack(">I", self.seg[o:o + 4])[0]

    def texture(self, addr, w, h):
        key = (addr, w, h)
        if key not in self.textures:
            o = addr & 0x00FFFFFF
            self.textures[key] = decode_rgba16(self.seg[o:o + w * h * 2], w, h)
        return self.textures[key]


class TriSoup:
    def __init__(self):
        self.tris = []    # (positions 3x3, normals 3x3, uv 3x2, material dict, cull)


def _combiner(w0, w1):
    """Cycle 1 RGB inputs of G_SETCOMBINE: (a, b, c, d)."""
    return ((w0 >> 20) & 0xF, (w1 >> 28) & 0xF, (w0 >> 15) & 0x1F, (w1 >> 15) & 0x7)


def run_dl(model, addr, matrix, state, soup):
    nmat = matrix[:3, :3]
    pc = addr
    seg = model.seg
    while True:
        o = pc & 0x00FFFFFF
        w0, w1 = struct.unpack(">II", seg[o:o + 8])
        pc += 8
        op = w0 >> 24
        if op == 0x06:                      # G_DL
            if (w0 >> 16) & 0xFF:
                pc = w1                     # branch
            else:
                run_dl(model, w1, matrix, state, soup)
        elif op == 0xB8:                    # G_ENDDL
            return
        elif op == 0x03:                    # G_MOVEMEM (lights)
            idx = (w0 >> 16) & 0xFF
            lo = w1 & 0x00FFFFFF
            col = np.array(list(seg[lo:lo + 3]), np.float32) / 255.0
            if idx == 0x86:
                state["diffuse"] = col
            elif idx == 0x88:
                state["ambient"] = col
        elif op == 0xFC:                    # G_SETCOMBINE
            state["combine"] = _combiner(w0, w1)
        elif op == 0xBB:                    # G_TEXTURE
            state["tex_on"] = (w0 & 0xFF) != 0
        elif op == 0xFD:                    # G_SETTIMG
            state["teximg"] = w1
        elif op == 0xF2:                    # G_SETTILESIZE
            if ((w1 >> 24) & 0x7) == 0:
                state["texsize"] = ((((w1 >> 12) & 0xFFF) >> 2) + 1, ((w1 & 0xFFF) >> 2) + 1)
        elif op == 0xB7:                    # G_SETGEOMETRYMODE
            if w1 & G_CULL_BACK:
                state["cull"] = True
        elif op == 0xB6:                    # G_CLEARGEOMETRYMODE
            if w1 & G_CULL_BACK:
                state["cull"] = False
        elif op == 0x04:                    # G_VTX
            n = ((w0 >> 20) & 0xF) + 1
            v0 = (w0 >> 16) & 0xF
            vo = w1 & 0x00FFFFFF
            for k in range(n):
                x, y, z, _f, s, t, nx, ny, nz, _a = struct.unpack(">hhhHhhbbbB", seg[vo + k * 16:vo + k * 16 + 16])
                p = np.array([x, y, z, 1.0]) @ matrix
                nn = np.array([nx, ny, nz], np.float64) @ nmat
                nn = nn / max(np.linalg.norm(nn), 1e-6)
                state["vbuf"][v0 + k] = (p[:3], nn, (s / 32.0, t / 32.0))
        elif op == 0xBF:                    # G_TRI1
            ids = [((w1 >> 16) & 0xFF) // 10, ((w1 >> 8) & 0xFF) // 10, (w1 & 0xFF) // 10]
            verts = [state["vbuf"][i] for i in ids]
            tex = None
            if state.get("tex_on") and state.get("teximg"):
                w, h = state.get("texsize", (32, 32))
                tex = model.texture(state["teximg"], w, h)
            soup.tris.append((
                np.array([v[0] for v in verts]),
                np.array([v[1] for v in verts]),
                np.array([v[2] for v in verts]),
                {"ambient": state["ambient"], "diffuse": state["diffuse"],
                 "combine": state.get("combine", (15, 15, 31, 4)), "tex": tex},
                state.get("cull", True)))
        # Everything else (syncs, tiles, render modes...) doesn't matter here


def build_soup(model, mats, eyes="front", lhand="fist", rhand="fist"):
    soup = TriSoup()
    state = {"ambient": np.array([0.5, 0.5, 0.5]), "diffuse": np.array([1.0, 1.0, 1.0]),
             "vbuf": [None] * 16, "cull": True}
    scale = np.eye(4)
    scale[0, 0] = scale[1, 1] = scale[2, 2] = 0.25       # GEO_SCALE in mario_geo
    for i, (_p, _t, part) in enumerate(SKELETON):
        if part is None:
            continue
        if part == "@eyes":
            part = "eyes_" + eyes
        elif part == "@left_hand":
            part = "left_hand_" + lhand
        elif part == "@right_hand":
            part = "right_hand_" + rhand
        run_dl(model, DL[part], mats[i] @ scale, state, soup)
    return soup


# --------------------------------------------------------------------------
# Rasterizer
# --------------------------------------------------------------------------

def _cc_input(sel, kind, shade, texel):
    """Color combiner input. kind: 'a', 'b', 'c' or 'd'. Returns array (..., 3)."""
    one = np.ones_like(shade)
    zero = np.zeros_like(shade)
    if sel == 1:
        return texel[..., :3]
    if sel == 4:
        return shade
    if sel in (3, 5):           # primitive / environment color: white for Mario
        return one
    if kind == "c":
        if sel == 8:
            return np.repeat(texel[..., 3:4], 3, axis=-1)
        if sel in (10, 12):
            return one
        return zero
    if kind in ("a", "d") and sel == 6:
        return one
    return zero


def render(soup, view, size, px_per_unit, origin, light_dir, ss=4):
    """
    view:   3x3 rotation model space -> camera space (x right, y up, z towards viewer)
    origin: output pixel position of the model origin (Mario's feet)
    Returns an RGBA float image of size*ss.
    """
    W, H = size[0] * ss, size[1] * ss
    color = np.zeros((H, W, 3), np.float32)
    alpha = np.zeros((H, W), np.float32)
    zbuf = np.full((H, W), -1e9, np.float32)
    k = px_per_unit * ss
    ox, oy = origin[0] * ss, origin[1] * ss
    L = np.array(light_dir, np.float64)
    L = L / np.linalg.norm(L)
    for tri_pos, tri_nrm, tri_uv, mat, cull in soup.tris:
        cp = tri_pos @ view
        cn = tri_nrm @ view
        sx = ox + cp[:, 0] * k
        sy = oy - cp[:, 1] * k
        sz = cp[:, 2]
        area = (sx[1] - sx[0]) * (sy[2] - sy[0]) - (sx[2] - sx[0]) * (sy[1] - sy[0])
        if abs(area) < 1e-9 or (cull and area > 0):
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
        # Per-vertex lighting (gouraud shading), slightly more contrast than on the N64
        shade_v = np.array([np.clip(mat["ambient"] * 0.7 + mat["diffuse"] * (0.15 + 0.95 * max(0.0, float(np.dot(n, L)))), 0, 1)
                            for n in cn])
        shade = w0[..., None] * shade_v[0] + w1[..., None] * shade_v[1] + w2[..., None] * shade_v[2]
        if mat["tex"] is not None:
            tex = mat["tex"]
            th, tw = tex.shape[:2]
            u = w0 * tri_uv[0, 0] + w1 * tri_uv[1, 0] + w2 * tri_uv[2, 0]
            v = w0 * tri_uv[0, 1] + w1 * tri_uv[1, 1] + w2 * tri_uv[2, 1]
            texel = tex[np.clip(np.floor(v).astype(int), 0, th - 1), np.clip(np.floor(u).astype(int), 0, tw - 1)]
        else:
            texel = np.zeros(shade.shape[:-1] + (4,), np.float32)
        a, b, c, d = mat["combine"]
        out = (_cc_input(a, "a", shade, texel) - _cc_input(b, "b", shade, texel)) * _cc_input(c, "c", shade, texel) \
            + _cc_input(d, "d", shade, texel)
        out = np.clip(out, 0, 1)
        color[y0:y1 + 1, x0:x1 + 1][upd] = out[upd]
        zb[upd] = z[upd]
        alpha[y0:y1 + 1, x0:x1 + 1][upd] = 1.0
    return np.dstack([color, alpha])


def view_matrix(yaw_deg, pitch_deg=0.0, roll_deg=0.0):
    """roll_deg rotates the image counter-clockwise (around the model origin)."""
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    r = math.radians(roll_deg)
    ry = np.array([[math.cos(y), 0, -math.sin(y)], [0, 1, 0], [math.sin(y), 0, math.cos(y)]])
    rx = np.array([[1, 0, 0], [0, math.cos(p), math.sin(p)], [0, -math.sin(p), math.cos(p)]])
    rz = np.array([[math.cos(r), math.sin(r), 0], [-math.sin(r), math.cos(r), 0], [0, 0, 1]])
    return ry @ rx @ rz
