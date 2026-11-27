#!/usr/bin/env python3
"""Fetch the official artwork and pack it for the board's "Modern" art style.

    python3 tools/fetch_artwork.py            # Kanto, 1-151, normal and shiny
    python3 tools/fetch_artwork.py 4 25       # just these species
    python3 tools/send_sd.py ...               # then copy tools/sdcard/mons/a*.bin to the card

Personal use only: the artwork belongs to Nintendo / The Pokemon Company and
is never committed (tools/artwork_cache/ and tools/sdcard/mons/*.bin are
git-ignored). Source: the PokeAPI sprites repository's "official-artwork".

Output: /mons/aNNN.bin (normal), /mons/asNNN.bin (shiny) and the food menu's
items /mons/i_red.bin, i_blue.bin, i_green.bin, i_candy.bin, format TPA1:
    "TPA1", u16 w, u16 h, then for each of the h rows:
    u16 x0, u16 n, then n pixels of (u16 RGB565, u8 alpha)
Rows hold only the span between their first and last non-transparent pixel,
so the empty corners of the square artwork cost nothing. Little-endian.

The picture is stored at the exact size it is drawn on the main screen (it
fits ART_MAX_H x ART_MAX_W), so the board never scales it: scaling on the
ESP32 costs time on every frame.
"""
import os
import struct
import sys
import urllib.request

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "artwork_cache")
OUT = os.path.join(HERE, "sdcard", "mons")
BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork"
# Must match ART_MAX_H / ART_MAX_W in sdmon.h.
ART_MAX_H = 190
ART_MAX_W = 230
# The food menu's items, from the item illustrations ("dream-world"), packed to
# fit ICON_PX (must match ICON_PX in sdmon.h). Board file name -> item.
ITEM_BASE = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/items/dream-world"
ICON_PX = 52
ITEMS = {
    "i_red": "razz-berry",     # the red berry
    "i_blue": "oran-berry",    # the blue berry
    "i_green": "lum-berry",    # the green berry
    "i_candy": "rare-candy",   # the candy
}


def fetch(dex, shiny):
    return download(f"{'s' if shiny else ''}{dex}.png", f"{BASE}/{'shiny/' if shiny else ''}{dex}.png")


def download(name, url):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": "tamapoke-art-fetch"})
        with urllib.request.urlopen(req, timeout=30) as r, open(path + ".part", "wb") as f:
            f.write(r.read())
        os.replace(path + ".part", path)
    return path


def rgb565(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def pack(png_path, max_h=ART_MAX_H, max_w=ART_MAX_W):
    im = Image.open(png_path).convert("RGBA")
    box = im.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
    if box:
        im = im.crop(box)
    k = min(max_h / im.height, max_w / im.width)
    w, h = max(1, round(im.width * k)), max(1, round(im.height * k))
    im = im.resize((w, h), Image.LANCZOS)
    px = im.load()
    out = bytearray(b"TPA1" + struct.pack("<HH", w, h))
    for y in range(h):
        xs = [x for x in range(w) if px[x, y][3] > 8]
        if not xs:
            out += struct.pack("<HH", 0, 0)
            continue
        x0, x1 = xs[0], xs[-1] + 1
        out += struct.pack("<HH", x0, x1 - x0)
        for x in range(x0, x1):
            r, g, b, a = px[x, y]
            out += struct.pack("<HB", rgb565(r, g, b), a if a > 8 else 0)
    return bytes(out)


def main(argv):
    dexes = [int(a) for a in argv] or list(range(1, 152))
    os.makedirs(OUT, exist_ok=True)
    for board_name, item in ITEMS.items():
        data = pack(download(f"item-{item}.png", f"{ITEM_BASE}/{item}.png"), ICON_PX, ICON_PX)
        with open(os.path.join(OUT, board_name + ".bin"), "wb") as f:
            f.write(data)
        print(f"{board_name} ok ({item})", flush=True)
    for dex in dexes:
        for shiny in (False, True):
            try:
                data = pack(fetch(dex, shiny))
            except Exception as e:  # a missing shiny falls back on the board
                print(f"{'shiny ' if shiny else ''}{dex}: skipped ({e})")
                continue
            name = f"a{'s' if shiny else ''}{dex:03d}.bin"
            with open(os.path.join(OUT, name), "wb") as f:
                f.write(data)
        print(f"{dex:03d} ok", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
