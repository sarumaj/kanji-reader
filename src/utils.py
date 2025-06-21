"""
Utility functions for the Kanji Reader application.

This module contains helper functions and utilities used throughout
the application, including text processing, image handling, and
system monitoring.
"""

import math
import textwrap
import time
import psutil
import base64
import re
import pyperclip
from PIL import Image, ImageDraw, ImageFilter
import cairosvg
import io
from typing import Tuple, Optional
from config import config


def wrap_text(text: str, text_width: int, step: int, limit: int = -1) -> Tuple[str, ...]:
    """
    Wrap text to fit within specified width constraints.

    Args:
        text: Text to wrap
        text_width: Maximum width in characters
        step: Step size for progressive wrapping
        limit: Maximum number of lines (-1 for unlimited)

    Returns:
        Tuple of wrapped text lines
    """
    if text_width <= 0:
        return tuple()

    def inner_wrap(text: str, text_width: int) -> Tuple[str, ...]:
        lines = textwrap.wrap(text, text_width, break_long_words=False)
        if len(lines) > 1:
            return (lines[0],) + inner_wrap('\n'.join(lines[1:]), text_width - step)
        elif len(lines) > 0:
            return (lines[0],)
        else:
            return tuple()

    result = tuple(
        sorted(
            inner_wrap(text, text_width),
            reverse=True,
            key=len
        )
    )

    if limit == -1:
        limit = len(result)
    return result[:limit]


def decode_base64_field(field_value: Optional[str]) -> str:
    """
    Decode a base64 encoded field from the database.

    Args:
        field_value: Base64 encoded string or None

    Returns:
        Decoded string or empty string if None
    """
    if field_value:
        try:
            return base64.b64decode(field_value.encode()).decode()
        except Exception:
            return field_value
    return ''


def get_network_bandwidth() -> str:
    """
    Get current network bandwidth usage.

    Returns:
        Formatted bandwidth string (bps, Kbps, Mbps, Gbps)
    """
    if not hasattr(get_network_bandwidth, 'old_value'):
        get_network_bandwidth.old_value = 0

    new_value = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
    old_value = get_network_bandwidth.old_value
    get_network_bandwidth.old_value = new_value

    B = float(new_value - old_value) * 8
    KB = float(1024)
    MB = float(KB ** 2)  # 1,048,576
    GB = float(KB ** 3)  # 1,073,741,824

    if B < KB:
        return f'{B:.0f} bps'
    elif KB <= B < MB:
        return f'{B/KB:.2f} Kbps'
    elif MB <= B < GB:
        return f'{B/MB:.2f} Mbps'
    else:
        return f'{B/GB:.2f} Gbps'


def draw_ellipse_with_gradient(
    border_width: int,
    size: Tuple[int, int],
    thick: int,
    fill: str
) -> Image.Image:
    """
    Create an ellipse image with gradient effect.

    Args:
        border_width: Width of the border
        size: Size of the ellipse (width, height)
        thick: Thickness parameter for the gradient
        fill: Fill color

    Returns:
        PIL Image with gradient ellipse
    """
    mask = Image.new(
        "RGBA",
        (size[0] - border_width, size[1] - border_width),
        (0, 0, 0, 255)
    )
    draw = ImageDraw.Draw(mask)
    draw.ellipse((thick, thick, size[0] - thick, size[1] - thick), fill=fill)
    img = mask.filter(ImageFilter.GaussianBlur(thick // 2))

    mask2 = Image.new('L', (size[0] - border_width, size[1] - border_width), 0)
    draw2 = ImageDraw.Draw(mask2)
    draw2.ellipse(
        (0, 0, size[0] - border_width, size[1] - border_width),
        fill=255
    )
    img.putalpha(mask2)
    return img


def svg_to_pil_image(
    svg_data: str,
    dpi: int = 120,
    output_width: int = 140,
    output_height: int = 140
) -> Image.Image:
    """
    Convert SVG data to PIL Image.

    Args:
        svg_data: SVG data as string
        dpi: DPI for rendering
        output_width: Output width in pixels
        output_height: Output height in pixels

    Returns:
        PIL Image object
    """
    png_data = cairosvg.svg2png(
        svg_data,
        dpi=dpi,
        output_width=output_width,
        output_height=output_height
    )
    return Image.open(io.BytesIO(png_data))


def extract_kanji_from_clipboard() -> str:
    """
    Extract kanji characters from clipboard content.

    Returns:
        String containing only kanji characters or error message
    """
    try:
        clipboard_text = pyperclip.paste()
        kanji_chars = re.findall(config.search.kanji_regex, clipboard_text, re.U)
        return ''.join(kanji_chars)
    except Exception:
        return "Failed to open clipboard"


def encode_character_bytes(char: str) -> str:
    """
    Encode a character to its byte representation.

    Args:
        char: Character to encode

    Returns:
        Hex-encoded byte string
    """
    return '/'.join(
        map(
            lambda x: hex(int(''.join(x), 16)),
            zip(*[iter(char.encode('utf-8').hex())] * 2)
        )
    )


def get_current_time_angles() -> Tuple[float, float, float]:
    """
    Get current time as clock angles.

    Returns:
        Tuple of (hour_angle, minute_angle, second_angle)
    """
    current_time = time.time()
    now_loc = time.localtime(current_time)
    mlsec = float("%.9f" % (current_time % 1,))

    t = time.strptime(str(now_loc.tm_hour), "%H")
    hour = int(time.strftime("%I", t)) * 30

    hour_angle = hour + 30 * now_loc.tm_min / 60
    minute_angle = now_loc.tm_min * 6 + 6 * now_loc.tm_sec / 60
    second_angle = now_loc.tm_sec * 6 + 6 * mlsec

    return hour_angle, minute_angle, second_angle


def calculate_clock_position(
    angle: float,
    radius: float,
    center_x: float,
    center_y: float
) -> Tuple[float, float]:
    """
    Calculate position on clock face given angle and radius.

    Args:
        angle: Angle in degrees
        radius: Distance from center
        center_x: X coordinate of clock center
        center_y: Y coordinate of clock center

    Returns:
        Tuple of (x, y) coordinates
    """
    x = center_x + radius * math.cos(math.radians(angle) - math.radians(90))
    y = center_y + radius * math.sin(math.radians(angle) - math.radians(90))
    return x, y


def is_auto_advance_time() -> bool:
    """
    Check if it's time to auto-advance to next kanji.

    Returns:
        True if should advance (at 59:59.0)
    """
    current_time = time.time()
    now_loc = time.localtime(current_time)
    mlsec = float("%.9f" % (current_time % 1,))

    return (now_loc.tm_sec == 59 and
            int(mlsec * 10) == 0 and
            now_loc.tm_min == 59)
