#!/usr/bin/env python3
"""Tests for tools/snap.py: python3 tools/test_snap.py"""
import os
import struct
import sys
import unittest
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snap  # noqa: E402


def fnv(pixels):
    s = 2166136261
    for c in pixels:
        for b in (c & 0xFF, c >> 8):
            s = ((s ^ b) * 16777619) & 0xFFFFFFFF
    return s


def reply(rows, checksum=None):
    pixels = [c for row in rows for c in row]
    out = ['boot noise', f'SNAP 1 {len(rows[0])} {len(rows)} fw=9.9 screen=on md5=abc']
    for row in rows:
        out.append(''.join(f'01{c:04X}' for c in row))
    out.append(f'SNAPEND {fnv(pixels) if checksum is None else checksum:08X}')
    return out


class Decode(unittest.TestCase):
    rows = [[0xF800, 0x07E0], [0x001F, 0xFFFF]]

    def test_pixels_and_header(self):
        shot = snap.decode(iter(reply(self.rows)))
        self.assertEqual((shot.width, shot.height), (2, 2))
        self.assertEqual(shot.pixels, [0xF800, 0x07E0, 0x001F, 0xFFFF])
        self.assertEqual(shot.info, {'fw': '9.9', 'screen': 'on', 'md5': 'abc'})

    def test_a_bad_checksum_is_refused(self):
        with self.assertRaises(snap.SnapError):
            snap.decode(iter(reply(self.rows, checksum=1)))

    def test_a_short_row_is_refused(self):
        lines = reply(self.rows)
        lines[2] = lines[2][:6]
        with self.assertRaises(snap.SnapError):
            snap.decode(iter(lines))

    def test_a_cut_off_reply_is_refused(self):
        with self.assertRaises(snap.SnapError):
            snap.decode(iter(reply(self.rows)[:-1]))

    def test_no_reply_is_refused(self):
        with self.assertRaises(snap.SnapError):
            snap.decode(iter(['DONE']))

    def test_png_holds_the_colours(self):
        png = snap.to_png(snap.decode(iter(reply(self.rows))))
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II', png[16:24]), (2, 2))
        at = png.index(b'IDAT')
        size = struct.unpack('>I', png[at - 4:at])[0]
        raw = zlib.decompress(png[at + 4:at + 4 + size])
        self.assertEqual(raw, bytes([0, 255, 0, 0, 0, 255, 0, 0, 0, 0, 255, 255, 255, 255]))


if __name__ == '__main__':
    unittest.main()
