"""Minimal PNG read/write on the standard library alone.

The pack's tooling deliberately carries no dependencies -- the Lua suite needs
only an interpreter -- so the coordinate tools stay stdlib-only too. Enough
PNG to read the map art and write overlays back out, nothing more.
"""

import struct
import zlib

_SIG = b"\x89PNG\r\n\x1a\n"


def _chunks(data):
    i = len(_SIG)
    while i < len(data):
        (length,) = struct.unpack_from(">I", data, i)
        kind = data[i + 4:i + 8]
        body = data[i + 8:i + 8 + length]
        yield kind, body
        i += 8 + length + 4


def _unfilter(raw, w, h, bpp):
    stride = w * bpp
    out = bytearray(stride * h)
    prev = bytearray(stride)
    pos = 0
    for y in range(h):
        ft = raw[pos]
        pos += 1
        line = bytearray(raw[pos:pos + stride])
        pos += stride
        if ft == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 0xFF
        elif ft == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 0xFF
        elif ft == 3:
            for x in range(stride):
                left = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((left + prev[x]) >> 1)) & 0xFF
        elif ft == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + pr) & 0xFF
        elif ft != 0:
            raise ValueError(f"bad filter {ft}")
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return out


def read_rgb(path):
    """-> (width, height, bytearray of RGB triples). Handles colour types 2,3,6."""
    data = open(path, "rb").read()
    if data[:8] != _SIG:
        raise ValueError("not a PNG")
    w = h = depth = ctype = None
    idat = bytearray()
    plte = None
    for kind, body in _chunks(data):
        if kind == b"IHDR":
            w, h, depth, ctype, _, _, interlace = struct.unpack(">IIBBBBB", body)
            if depth != 8 or interlace:
                raise ValueError(f"unsupported PNG (depth {depth}, interlace {interlace})")
        elif kind == b"PLTE":
            plte = body
        elif kind == b"IDAT":
            idat += body
        elif kind == b"IEND":
            break
    bpp = {2: 3, 3: 1, 6: 4}.get(ctype)
    if bpp is None:
        raise ValueError(f"unsupported colour type {ctype}")
    flat = _unfilter(zlib.decompress(bytes(idat)), w, h, bpp)
    if ctype == 2:
        return w, h, flat
    rgb = bytearray(w * h * 3)
    if ctype == 3:
        for i in range(w * h):
            rgb[i * 3:i * 3 + 3] = plte[flat[i] * 3:flat[i] * 3 + 3]
    else:  # 6 = RGBA, composite onto black
        for i in range(w * h):
            rgb[i * 3:i * 3 + 3] = flat[i * 4:i * 4 + 3]
    return w, h, rgb


def write_rgb(path, w, h, rgb):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgb[y * w * 3:(y + 1) * w * 3]
    out = bytearray(_SIG)
    for kind, body in (
        (b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)),
        (b"IDAT", zlib.compress(bytes(raw), 6)),
        (b"IEND", b""),
    ):
        out += struct.pack(">I", len(body)) + kind + body
        out += struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)
    open(path, "wb").write(out)


def size(path):
    data = open(path, "rb").read(24)
    return struct.unpack(">II", data[16:24])
