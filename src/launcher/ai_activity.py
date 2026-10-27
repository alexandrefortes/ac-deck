"""Small original pixel car for the AI activity indicator.

The caller decides visibility and supplies the normal render-loop clock.
This module only draws rectangles; it owns no timers, workers or requests.
"""
from math import isfinite
from types import MappingProxyType


WIDTH = 24
HEIGHT = 14
PIXEL_SIZE = 2
FRAME_SECONDS = 0.5
PALETTE = MappingProxyType({
    'o': (74, 73, 69),
    'g': (243, 205, 85),
    'h': (242, 240, 233),
    'v': (104, 121, 130),
    'd': (39, 40, 42),
    'm': (174, 179, 183),
    's': (49, 50, 52),
})


def _make_frame(phase):
    pixels = [[' '] * WIDTH for unused in range(HEIGHT)]

    def fill(x, y, width, height, color):
        for yy in range(y, y + height):
            pixels[yy][x:x + width] = [color] * width

    # Fixed silhouette: roof, divided windows, low body and a pale headlight.
    fill(4, 13, 18, 1, 's')
    fill(8, 2, 9, 1, 'o')
    fill(7, 3, 11, 3, 'o')
    fill(18, 4, 1, 2, 'o')
    fill(8, 3, 4, 3, 'v')
    fill(13, 3, 3, 3, 'v')
    fill(16, 4, 2, 2, 'v')
    fill(9, 2, 7, 1, 'g')
    fill(3, 6, 19, 4, 'o')
    fill(22, 7, 1, 3, 'o')
    fill(4, 6, 17, 1, 'g')
    fill(4, 7, 18, 2, 'g')
    fill(4, 7, 1, 1, 'h')
    fill(21, 7, 1, 1, 'h')
    fill(5, 9, 16, 1, 'g')

    # One hub pixel per wheel moves half a turn per second. Body stays still.
    dx, dy = ((1, 1), (2, 1), (2, 2), (1, 2))[phase]
    for x in (5, 17):
        fill(x, 9, 4, 4, 'd')
        fill(x + dx, 9 + dy, 1, 1, 'm')
    return tuple(''.join(row) for row in pixels)


FRAMES = tuple(_make_frame(phase) for phase in range(4))


def frame(now):
    """Return a deterministic frame for a monotonic time in seconds."""
    seconds = float(now)
    if not isfinite(seconds) or seconds < 0:
        seconds = 0
    return FRAMES[int(seconds / FRAME_SECONDS) % len(FRAMES)]


def bounds(x, y, pixel_size=PIXEL_SIZE):
    """Return the reserved logical area; both target resolutions share it."""
    if type(pixel_size) is not int or pixel_size <= 0:
        raise ValueError('pixel_size must be a positive integer')
    return int(x), int(y), WIDTH * pixel_size, HEIGHT * pixel_size


def draw(window, x, y, now, pixel_size=PIXEL_SIZE):
    """Paint the car at the requested corner and return its reserved bounds."""
    x, y, width, height = bounds(x, y, pixel_size)
    for yy, row in enumerate(frame(now)):
        xx = 0
        while xx < WIDTH:
            color = row[xx]
            end = xx + 1
            while end < WIDTH and row[end] == color:
                end += 1
            if color != ' ':
                window.rect(x + xx * pixel_size, y + yy * pixel_size,
                            (end - xx) * pixel_size, pixel_size, PALETTE[color])
            xx = end
    return x, y, width, height
