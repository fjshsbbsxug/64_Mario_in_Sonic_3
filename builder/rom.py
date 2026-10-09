"""
Access to the data inside a Super Mario 64 (USA) ROM.

Everything Mario-related that the mod needs is read from here: the model segment
(geometry, display lists, lights, textures), the animation table and the voice samples.
"""

import hashlib
import struct

import numpy as np


SM64_US_SHA1 = "9bef1128717f958171a4afac3ed78ee2bb4e86ce"

# ROM locations for the USA version
MARIO_SEGMENT_MIO0 = 0x114750       # Segment 0x04: Mario's model data (MIO0 compressed)
MARIO_ANIMS_TABLE = 0x4EC000        # Mario's animation table (uncompressed)


class RomError(Exception):
    pass


def normalize_rom(data):
    """Convert .v64 (byte swapped) and .n64 (little endian) dumps to .z64 byte order."""
    head = data[:4]
    if head == b"\x80\x37\x12\x40":
        return data
    if head == b"\x37\x80\x40\x12":
        a = np.frombuffer(data, np.uint8).reshape(-1, 2)[:, ::-1]
        return a.tobytes()
    if head == b"\x40\x12\x37\x80":
        a = np.frombuffer(data, np.uint8).reshape(-1, 4)[:, ::-1]
        return a.tobytes()
    raise RomError("This file does not look like a Nintendo 64 ROM.")


def load_rom(path):
    with open(path, "rb") as f:
        data = normalize_rom(f.read())
    sha1 = hashlib.sha1(data).hexdigest()
    if sha1 != SM64_US_SHA1:
        name = data[0x20:0x34].decode("ascii", "replace").strip()
        region = chr(data[0x3E]) if len(data) > 0x3E else "?"
        raise RomError(
            "Unsupported ROM (internal name '%s', region '%s', SHA-1 %s).\n"
            "Please use an unmodified Super Mario 64 (USA) ROM." % (name, region, sha1))
    return data


def mio0_decompress(data, offset):
    if data[offset:offset + 4] != b"MIO0":
        raise RomError("No MIO0 block at 0x%X" % offset)
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
            start = len(out) - ((v & 0xFFF) + 1)
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


def mario_segment(rom):
    return mio0_decompress(rom, MARIO_SEGMENT_MIO0)


def load_animations(rom):
    """Returns dict: animation index -> animation dict (same layout as SM64's struct Animation)."""
    count = struct.unpack(">I", rom[MARIO_ANIMS_TABLE:MARIO_ANIMS_TABLE + 4])[0]
    anims = {}
    for i in range(count):
        off, size = struct.unpack(">II", rom[MARIO_ANIMS_TABLE + 8 + i * 8:MARIO_ANIMS_TABLE + 16 + i * 8])
        base = MARIO_ANIMS_TABLE + off
        flags, ydiv, start, loop_start, loop_end, _bones, values_off, index_off, length = \
            struct.unpack(">hhhhhhIII", rom[base:base + 24])
        num_index = (values_off - index_off) // 2
        index = np.frombuffer(rom[base + index_off:base + index_off + num_index * 2], ">u2").astype(np.int64)
        num_values = (length - values_off) // 2
        values = np.frombuffer(rom[base + values_off:base + values_off + num_values * 2], ">i2").astype(np.int64)
        anims[i] = {"flags": flags & 0xFFFF, "ydiv": ydiv, "start": start, "loop_start": loop_start,
                    "loop_end": loop_end, "values": values, "index": index}
    return anims


# --------------------------------------------------------------------------
# Voice samples (VADPCM in the sound sample table)
# --------------------------------------------------------------------------

# name -> (ROM offset of the ADPCM data, size in bytes, ROM offset of the codebook)
VOICE_SAMPLES = {
    "mario_hoo":      (6323856, 1881, 5764528),
    "mario_wah":      (6325744, 2052, 5764656),
    "mario_yah":      (6327808, 2691, 5764784),
    "mario_yahoo":    (6337424, 8523, 5765040),
    "mario_ooof":     (6376384, 5544, 5765936),
    "mario_herewego": (6381936, 12807, 5766064),
    "mario_wahoo":    (6580640, 9693, 5767600),
    "mario_yippee":   (6590336, 9018, 5767728),
    "mario_mammamia": (6687168, 15786, 5770704),
}
VOICE_SAMPLE_RATE = 16000


def _vadpcm_table(book):
    """Expand an order 2 / 2 predictor codebook into 8x10 predictor tables (as in N64 aifc decoders)."""
    order, npred = 2, 2
    tables = []
    for p in range(npred):
        t = [[0] * (order + 8) for _ in range(8)]
        for j in range(order):
            for k in range(8):
                t[k][j] = book[p * 16 + j * 8 + k]
        for k in range(1, 8):
            t[k][order] = t[k - 1][order - 1]
        t[0][order] = 1 << 11
        for k in range(1, 8):
            for j in range(8):
                t[j][k + order] = 0 if j < k else t[j - k][order]
        tables.append(t)
    return tables


def _inner_product(v1, v2, n):
    out = 0
    for i in range(n):
        out += v1[i] * v2[i]
    # floor(out / 2048)
    return out >> 11


def decode_vadpcm(data, book):
    tables = _vadpcm_table(book)
    order = 2
    state = [0] * 16
    out = []
    nframes = len(data) // 9
    for f in range(nframes):
        frame = data[f * 9:f * 9 + 9]
        header = frame[0]
        scale = 1 << (header >> 4)
        table = tables[header & 0x0F]
        ix = []
        for b in frame[1:]:
            for nib in (b >> 4, b & 0x0F):
                ix.append((nib - 16 if nib >= 8 else nib) * scale)
        for j in range(2):
            in_vec = [0] * 16
            for i in range(order):
                in_vec[i] = state[16 - order + i] if j == 0 else state[8 - order + i]
            for i in range(8):
                ind = j * 8 + i
                in_vec[order + i] = ix[ind]
                state[ind] = _inner_product(table[i], in_vec, order + i) + ix[ind]
        out.extend(max(-32768, min(32767, s)) for s in state)
    return np.array(out, np.int16)


def load_voice(rom, name):
    data_off, size, book_off = VOICE_SAMPLES[name]
    order, npred = struct.unpack(">ii", rom[book_off:book_off + 8])
    if order != 2 or npred != 2:
        raise RomError("Unexpected codebook for %s" % name)
    book = list(struct.unpack(">32h", rom[book_off + 8:book_off + 8 + 64]))
    size -= size % 9
    return decode_vadpcm(rom[data_off:data_off + size], book)
