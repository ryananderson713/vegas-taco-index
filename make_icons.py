#!/usr/bin/env python3
"""
Generate the home-screen icons.

No imaging library is available here, so the PNGs are encoded by hand with
zlib + struct and the artwork is drawn procedurally: a neon taco on a night
ground, matching the page. Rendered at 3x and box-averaged down for antialiasing.
"""

import math
import struct
import zlib

SS = 3  # supersample factor

NIGHT = (0x0A, 0x05, 0x12)
VIOLET = (0xB1, 0x5C, 0xFF)
MAGENTA = (0xFF, 0x2E, 0x88)
SHELL_HI = (0xFF, 0xD9, 0x6B)
SHELL_LO = (0xE8, 0x9B, 0x2E)
LETTUCE = (0x43, 0xFF, 0x9A)
TOMATO = (0xFF, 0x6A, 0x3D)
CHEESE = (0xFF, 0xE0, 0x66)


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def add_glow(base, color, amount):
    amount = max(0.0, min(1.0, amount))
    return tuple(min(255, round(base[i] + (color[i] - base[i]) * amount)) for i in range(3))


def shade(x, y, size):
    """Colour one supersampled pixel."""
    cx, cy = size / 2, size / 2
    u, v = (x + 0.5 - cx) / (size / 2), (y + 0.5 - cy) / (size / 2)
    d = math.hypot(u, v)

    # night ground with a violet bloom up top
    px = lerp(NIGHT, (0x1C, 0x0E, 0x30), 1.0 - min(1.0, math.hypot(u, v + 0.35)))

    R = 0.70          # shell outer radius
    MOUTH = 0.06      # shell occupies v >= MOUTH; filling piles up above it

    # magenta sign-glow radiating off the shell
    px = add_glow(px, MAGENTA, 0.44 * math.exp(-((d - R) ** 2) / 0.045))
    px = add_glow(px, VIOLET, 0.20 * math.exp(-((d - R) ** 2) / 0.20))

    # --- filling: lumpy mound sitting in the shell, overflowing the rim ---
    half = R * 0.995
    if abs(u) <= half and v < MOUTH:
        # lumps, so it reads as fillings rather than a flat bowl of soup
        lump = (0.30 + 0.075 * math.sin(u * 6.1 + 0.4)
                     + 0.055 * math.sin(u * 11.3 + 1.9)
                     + 0.030 * math.sin(u * 17.0))
        edge = 1.0 - (abs(u) / half) ** 2.4      # taper toward the shell corners
        top = MOUTH - lump * edge
        if v >= top:
            band = (u + 1) * 3.4
            slot = int(math.floor(band)) % 3
            frac = band - math.floor(band)
            col = (LETTUCE, TOMATO, CHEESE)[slot]
            nxt = (LETTUCE, TOMATO, CHEESE)[(slot + 1) % 3]
            px = lerp(col, nxt, max(0.0, (frac - 0.80) / 0.20))
            # light from above, shadow where it meets the shell
            px = add_glow(px, (255, 255, 255), 0.30 * max(0.0, 1 - (v - top) / 0.13))
            px = lerp(px, (0x2A, 0x12, 0x0A), 0.45 * max(0.0, 1 - (MOUTH - v) / 0.07))
            return px

    # --- shell ---
    if d <= R and v >= MOUTH:
        rim = max(0.0, 1 - (R - d) / 0.085)
        px = lerp(lerp(SHELL_LO, SHELL_HI, 0.60 - v * 0.55), SHELL_HI, rim * 0.9)
        px = add_glow(px, (255, 255, 255), 0.32 * rim)
        # crease under the mouth reads as the shell's inner lip
        px = lerp(px, (0x8A, 0x54, 0x18), 0.5 * max(0.0, 1 - (v - MOUTH) / 0.055))
        return px

    return px


def render(size):
    big = size * SS
    rows = []
    for y in range(big):
        row = []
        for x in range(big):
            row.append(shade(x, y, big))
        rows.append(row)

    out = bytearray()
    for y in range(size):
        out.append(0)  # filter type: none
        for x in range(size):
            r = g = b = 0
            for dy in range(SS):
                for dx in range(SS):
                    p = rows[y * SS + dy][x * SS + dx]
                    r += p[0]; g += p[1]; b += p[2]
            n = SS * SS
            out += bytes((r // n, g // n, b // n))
    return bytes(out)


def write_png(path, size, raw):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)  # 8-bit truecolour
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


if __name__ == "__main__":
    for size, name in [(192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")]:
        n = write_png(name, size, render(size))
        print(f"{name}: {size}x{size}, {n/1024:.1f} KB")
