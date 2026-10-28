"""Generates a placeholder sprite sheet (blob.png + blob.json) with zero dependencies.
Replace it with your own art later: keep the manifest format and nothing else changes.

    python assets/make_placeholder.py            # writes assets/sprites/blob.{png,json}
    python assets/make_placeholder.py --preview  # also writes a 4x preview.png
"""
import json, struct, sys, zlib
from pathlib import Path

W = H = 32
COLS = 4
T = (0, 0, 0, 0)
OUT = (40, 45, 60, 255)
BODY = (126, 214, 178, 255)
BELLY = (190, 240, 214, 255)
EYE = (30, 30, 45, 255)
WHITE = (255, 255, 255, 255)
CHEEK = (255, 160, 170, 255)
GOLD = (255, 214, 102, 255)
BLUE = (120, 180, 255, 255)
RED = (255, 100, 100, 255)

# name: (frames, fps, loop, next)
STATES = {
    "idle": (4, 4, True, None),
    "sleeping": (4, 2, True, None),
    "alert": (4, 8, False, "idle"),
    "thinking": (4, 4, True, None),
    "working": (4, 8, True, None),
    "happy": (4, 6, False, "idle"),
    "confused": (4, 6, False, "idle"),
    "curious": (4, 3, True, None),
}


class Canvas:
    def __init__(self):
        self.p = [[T] * W for _ in range(H)]

    def set(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.p[y][x] = c

    def rect(self, x, y, w, h, c):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.set(xx, yy, c)

    def pts(self, points, c):
        for x, y in points:
            self.set(x, y, c)


def creature(state, f):
    c = Canvas()
    dx = dy = ear_up = 0
    look = (0, 0)
    if state == "idle":
        dy = [0, 0, 1, 0][f]
    elif state == "sleeping":
        dy = [1, 1, 2, 2][f]
    elif state == "alert":
        dy, ear_up = [-1, 0, -1, 0][f], 2
    elif state == "thinking":
        look = (1, -1)
    elif state == "working":
        dx = [-1, 1, -1, 1][f]
    elif state == "happy":
        dy = [0, -3, -5, -2][f]
    elif state == "confused":
        dx = [0, 1, 0, -1][f]
    elif state == "curious":
        dy = [0, 0, -1, 0][f]
        look = (1, 0)

    cx, cy = 16 + dx, 20 + dy
    fill = {}
    for y in range(H):
        for x in range(W):
            if ((x - cx) / 10) ** 2 + ((y - cy) / 8) ** 2 <= 1:
                fill[(x, y)] = BODY
    # ears: triangles rising from the top of the body
    for ex, extra in ((cx - 6, 3 if state == "curious" else 0), (cx + 6, 0)):
        h = 5 + ear_up + extra
        for k in range(h):
            w = max(1, 3 - (k * 3) // h)
            for xx in range(ex - w // 2, ex - w // 2 + w):
                fill[(xx, cy - 6 - k)] = BODY
    for (x, y), col in fill.items():
        edge = any((x + a, y + b) not in fill for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        c.set(x, y, OUT if edge else col)
    # belly
    for y in range(H):
        for x in range(W):
            if ((x - cx) / 6) ** 2 + ((y - (cy + 3)) / 4) ** 2 <= 1:
                c.set(x, y, BELLY)

    # eyes
    ox, oy = look
    ey = cy - 2 + oy
    lx, rx = cx - 4 + ox, cx + 3 + ox

    def normal(x):
        c.rect(x, ey, 2, 3, EYE); c.set(x, ey, WHITE)

    def wide(x):
        c.rect(x, ey - 1, 3, 4, EYE); c.set(x, ey - 1, WHITE)

    def closed(x):
        c.rect(x, ey + 1, 3, 1, EYE)

    def happy_eye(x):
        c.pts([(x, ey + 1), (x + 1, ey), (x + 2, ey + 1)], EYE)

    def narrow(x):
        c.rect(x, ey + 1, 3, 2, EYE)

    if state == "idle":
        (closed if f == 3 else normal)(lx); (closed if f == 3 else normal)(rx)
    elif state == "sleeping":
        closed(lx); closed(rx)
    elif state in ("alert", "curious"):
        wide(lx); wide(rx)
    elif state == "working":
        narrow(lx); narrow(rx)
    elif state == "happy":
        happy_eye(lx); happy_eye(rx)
    elif state == "confused":
        normal(lx); wide(rx)
    else:
        normal(lx); normal(rx)

    my = cy + 2
    if state in ("idle", "happy", "alert"):
        c.pts([(cx - 1, my + 1), (cx, my + 1), (cx + 1, my + 1), (cx - 2, my), (cx + 2, my)], EYE)
    elif state == "confused":
        c.pts([(cx - 2, my + 1), (cx - 1, my), (cx, my + 1), (cx + 1, my), (cx + 2, my + 1)], EYE)
    if state in ("idle", "happy"):
        c.rect(cx - 7, cy + 1, 2, 1, CHEEK); c.rect(cx + 6, cy + 1, 2, 1, CHEEK)

    # state decorations
    if state == "sleeping":
        zx, zy = [(23, 9), (24, 8), (25, 7), (26, 6)][f]
        c.pts([(zx, zy), (zx + 1, zy), (zx + 2, zy), (zx + 1, zy + 1), (zx, zy + 2),
               (zx + 1, zy + 2), (zx + 2, zy + 2)], BLUE)
    elif state == "thinking":
        for i in range(([1, 2, 3, 2][f])):
            c.rect(22 + 3 * i, 6 - i, 2, 2, GOLD)
    elif state in ("working", "happy"):
        sx, sy = (26, 12) if f % 2 == 0 else (5, 10)
        c.pts([(sx, sy - 1), (sx - 1, sy), (sx, sy), (sx + 1, sy), (sx, sy + 1)], GOLD)
    elif state == "confused":
        x, y = cx + 8, cy - 8 + f % 2
        c.pts([(x, y), (x - 1, y + 1), (x, y + 1), (x + 1, y + 1), (x, y + 2)], BLUE)
    elif state == "alert":
        c.rect(26, 5, 1, 4, RED); c.set(26, 10, RED)
    elif state == "curious":
        c.pts([(24, 5), (25, 4), (26, 4), (27, 5), (27, 6), (26, 7), (26, 8), (26, 10)], GOLD)
    return c.p


def write_png(path, pixels):
    h, w = len(pixels), len(pixels[0])
    raw = b"".join(b"\x00" + bytes(v for px in row for v in px) for row in pixels)

    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
    Path(path).write_bytes(png)


def main():
    out = Path(__file__).parent / "sprites"
    out.mkdir(exist_ok=True)
    sheet = [[T] * (W * COLS) for _ in range(H * len(STATES))]
    manifest = {"image": "blob.png", "frame_size": [W, H], "states": {}}
    for row, (name, (frames, fps, loop, nxt)) in enumerate(STATES.items()):
        spec = {"row": row, "frames": frames, "fps": fps, "loop": loop}
        if nxt:
            spec["next"] = nxt
        manifest["states"][name] = spec
        for f in range(frames):
            fr = creature(name, f)
            for y in range(H):
                sheet[row * H + y][f * W:(f + 1) * W] = fr[y]
    write_png(out / "blob.png", sheet)
    (out / "blob.json").write_text(json.dumps(manifest, indent=2))
    print("wrote", out / "blob.png", out / "blob.json")
    if "--preview" in sys.argv:
        k = 4
        big = [[px for px in row for _ in range(k)] for row in sheet for _ in range(k)]
        write_png(out / "preview.png", big)


if __name__ == "__main__":
    main()
