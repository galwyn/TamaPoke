#!/usr/bin/env python3
"""Takes a screenshot of the board over USB and saves it as a PNG.

  python3 tools/snap.py                       # screenshot.png from the board
  python3 tools/snap.py -o main.png
  python3 tools/snap.py --expect-bin build/snap/TamaPoke.ino.bin
  python3 tools/snap.py --from capture.txt    # decode a saved SNAP reply

The picture is the frame the firmware last drew (its framebuffer). It is not a
photo of the panel: a panel that is dark or stuck still gives the drawn frame.
Only one program can use the serial port at a time.
"""
import argparse
import glob
import hashlib
import struct
import sys
import time
import zlib
from collections import namedtuple

Shot = namedtuple('Shot', 'width height info pixels')


class SnapError(Exception):
    pass


def decode(lines):
    """Reads one SNAP reply from an iterator of text lines."""
    for line in lines:
        if line.startswith('SNAPERR'):
            raise SnapError(f'the board answered: {line}')
        if line.startswith('SNAP 1 '):
            break
    else:
        raise SnapError('no SNAP reply: is this build older than the SNAP command?')
    fields = line.split()
    width, height = int(fields[2]), int(fields[3])
    info = dict(f.split('=', 1) for f in fields[4:] if '=' in f)

    pixels = []
    for y in range(height):
        row = next(lines, '')
        start = len(pixels)
        try:
            if len(row) % 6:
                raise ValueError
            for k in range(0, len(row), 6):
                pixels += [int(row[k + 2:k + 6], 16)] * int(row[k:k + 2], 16)
        except ValueError:
            raise SnapError(f'row {y} arrived damaged') from None
        if len(pixels) - start != width:
            raise SnapError(f'row {y} has {len(pixels) - start} pixels, not {width}')

    end = next(lines, '')
    if not end.startswith('SNAPEND '):
        raise SnapError('the reply was cut off before its end line')
    checksum = 2166136261
    for c in pixels:
        checksum = ((checksum ^ (c & 0xFF)) * 16777619) & 0xFFFFFFFF
        checksum = ((checksum ^ (c >> 8)) * 16777619) & 0xFFFFFFFF
    if checksum != int(end.split()[1], 16):
        raise SnapError('checksum mismatch: the picture was damaged on the way')
    return Shot(width, height, info, pixels)


def to_png(shot):
    raw = bytearray()
    for y in range(shot.height):
        raw.append(0)  # PNG filter: none
        for c in shot.pixels[y * shot.width:(y + 1) * shot.width]:
            r, g, b = c >> 11, (c >> 5) & 63, c & 31
            raw += bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    head = struct.pack('>IIBBBBB', shot.width, shot.height, 8, 2, 0, 0, 0)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', head) + chunk(b'IDAT', zlib.compress(bytes(raw))) + chunk(b'IEND', b'')


def from_board(port, timeout):
    import serial  # pyserial; only needed to talk to the board
    if not port:
        ports = glob.glob('/dev/cu.usbmodem*')
        if len(ports) != 1:
            raise SnapError(f'expected one board, found {ports or "none"}: name it with --port')
        port = ports[0]
    with serial.Serial(port, 115200, timeout=1) as ser:
        time.sleep(0.5)
        ser.reset_input_buffer()
        ser.write(b'SNAP\n')
        deadline = time.time() + timeout

        def lines():
            pending = b''
            while time.time() < deadline:
                pending += ser.readline()
                if pending.endswith(b'\n'):
                    yield pending.decode('ascii', 'replace').rstrip('\r\n')
                    pending = b''

        return decode(lines())


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('-o', '--out', default='screenshot.png')
    ap.add_argument('--port')
    ap.add_argument('--timeout', type=float, default=30)
    ap.add_argument('--from', dest='source', help='decode a saved reply instead of asking the board')
    ap.add_argument('--expect-bin', help='fail unless the board runs exactly this .bin')
    args = ap.parse_args()
    try:
        if args.source:
            with open(args.source, errors='replace') as f:
                shot = decode(iter(f.read().splitlines()))
        else:
            shot = from_board(args.port, args.timeout)
    except SnapError as e:
        sys.exit(f'snap: {e}')

    with open(args.out, 'wb') as f:
        f.write(to_png(shot))
    print(f'{args.out}: {shot.width}x{shot.height} ' + ' '.join(f'{k}={v}' for k, v in shot.info.items()))

    if args.expect_bin:
        with open(args.expect_bin, 'rb') as f:
            want = hashlib.md5(f.read()).hexdigest()
        if shot.info.get('md5', '').lower() != want:
            sys.exit(f'snap: NOT the expected build (expected md5 {want})')
        print('build check: the board runs exactly this .bin')


if __name__ == '__main__':
    main()
