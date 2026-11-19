from __future__ import annotations

import io
import math
import random
import re
from textwrap import wrap

try:
    from PIL import Image, ImageColor, ImageDraw, ImageFont

    PIL_AVAILABLE = True
except ModuleNotFoundError:
    Image = ImageColor = ImageDraw = ImageFont = None
    PIL_AVAILABLE = False


CARD_DESIGNS = (
    {
        "name": "blossom",
        "background": "#FFF5F8",
        "background_2": "#FFE7F0",
        "panel": "#FFFFFF",
        "panel_2": "#FFF9FC",
        "accent": "#D95F8A",
        "accent_2": "#F4A7C2",
        "text": "#482B3B",
        "soft": "#FFE3EC",
        "soft_2": "#FFD1E2",
        "line": "#F8C7D8",
        "emojis": ("🌸", "✨", "💗"),
    },
    {
        "name": "celebration",
        "background": "#FFF8ED",
        "background_2": "#FFEBD0",
        "panel": "#FFFDF8",
        "panel_2": "#FFF6E8",
        "accent": "#E76F51",
        "accent_2": "#F4A261",
        "text": "#4D342C",
        "soft": "#FFE5C2",
        "soft_2": "#FFD397",
        "line": "#F8CFA7",
        "emojis": ("🎈", "🎂", "🎉"),
    },
    {
        "name": "garden",
        "background": "#F1FBF7",
        "background_2": "#DDF3E8",
        "panel": "#FCFFFD",
        "panel_2": "#F1FBF6",
        "accent": "#3C9D8B",
        "accent_2": "#80CFAE",
        "text": "#294B45",
        "soft": "#DDF4E9",
        "soft_2": "#C6EBD9",
        "line": "#B7E3D1",
        "emojis": ("🌿", "🌼", "🦋"),
    },
    {
        "name": "moonlight",
        "background": "#25213B",
        "background_2": "#1C1930",
        "panel": "#342D50",
        "panel_2": "#2B2543",
        "accent": "#F5B6D2",
        "accent_2": "#A9C7FF",
        "text": "#FFF5FB",
        "soft": "#514875",
        "soft_2": "#443963",
        "line": "#665B91",
        "emojis": ("🌙", "💜", "🫶"),
    },
    {
        "name": "ocean",
        "background": "#EEF8FF",
        "background_2": "#D9EEFC",
        "panel": "#FFFFFF",
        "panel_2": "#F2FAFF",
        "accent": "#3D83B8",
        "accent_2": "#83C8E8",
        "text": "#25445A",
        "soft": "#DDF2FC",
        "soft_2": "#C4E7F8",
        "line": "#B8DFF1",
        "emojis": ("🌊", "🫧", "💙"),
    },
    {
        "name": "sunrise",
        "background": "#FFF9EC",
        "background_2": "#FFECC3",
        "panel": "#FFFDF7",
        "panel_2": "#FFF6DF",
        "accent": "#C98338",
        "accent_2": "#F0B95C",
        "text": "#5A3C25",
        "soft": "#FFF0C9",
        "soft_2": "#FFE2A2",
        "line": "#F3D899",
        "emojis": ("🌞", "🌻", "🧡"),
    },
)

WISH_TEMPLATES = (
    "May your day be filled with laughter, love, and lovely surprises.",
    "Wishing you bright moments and a year full of little joys.",
    "May every birthday wish lead you to something wonderful.",
    "Warm hugs, sweet cake, and beautiful memories for your day.",
    "May this new chapter bring you peace, courage, and happiness.",
    "You deserve a joyful, gentle year that feels completely yours.",
    "May today remind you how loved and appreciated you are.",
    "Wishing you new adventures, kind people, and happy beginnings.",
    "May your smile be big today and your worries feel small.",
    "Here is to more laughter, good luck, and unforgettable moments.",
    "May your heart stay light and your dreams move closer.",
    "You make the world brighter just by being you.",
    "Wishing you cake, cuddles, and every reason to smile.",
    "May the year ahead be kinder, brighter, and full of magic.",
    "More sunsets, better surprises, and reasons to celebrate.",
    "Have the sweetest birthday and a beautiful year ahead.",
)

CARD_TITLES = (
    "Happy Birthday",
    "Birthday Wishes",
    "A Little Birthday Love",
    "For Your Special Day",
)

_remaining_wishes: list[str] = []
_design_order: list[int] = []


def clean_birthday_name(raw_name: str) -> str:
    """Keep names friendly for Discord text and safe for image rendering."""
    name = re.sub(r"\s+", " ", raw_name).strip()
    name = re.sub(r"[@#:`*_~|<>\\/\r\n\t]", "", name).strip()
    return name[:40]


def birthday_wish(name: str) -> str:
    if not _remaining_wishes:
        _remaining_wishes.extend(WISH_TEMPLATES)
        random.shuffle(_remaining_wishes)
    return _remaining_wishes.pop()


def birthday_caption(name: str, wish: str, from_name: str = "Luna") -> str:
    return f"Made an animated birthday card for **{name}**.\n{wish}\nWith love from **{from_name} & Luna**."


def _font(size: int, bold: bool = False):
    names = (
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        "arialbd.ttf" if bold else "arial.ttf",
        "segoeuib.ttf" if bold else "segoeui.ttf",
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _center_text(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    text: str,
    font,
    fill: str,
) -> None:
    left, top, right, bottom = box
    bounds = draw.textbbox((0, 0), text, font=font)
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    draw.text(
        (left + (right - left - width) / 2, top + (bottom - top - height) / 2),
        text,
        font=font,
        fill=fill,
    )


def _vertical_gradient(width: int, height: int, top_color: str, bottom_color: str):
    gradient = Image.new("RGB", (width, height))
    top_rgb = ImageColor.getrgb(top_color)
    bottom_rgb = ImageColor.getrgb(bottom_color)
    pixels = gradient.load()
    denominator = max(1, height - 1)
    for y in range(height):
        ratio = y / denominator
        color = tuple(
            round(top_rgb[channel] + (bottom_rgb[channel] - top_rgb[channel]) * ratio)
            for channel in range(3)
        )
        for x in range(width):
            pixels[x, y] = color
    return gradient


def _paint_gradient_box(
    image,
    box: tuple[int, int, int, int],
    radius: int,
    top_color: str,
    bottom_color: str,
) -> None:
    left, top, right, bottom = box
    gradient = _vertical_gradient(right - left + 1, bottom - top + 1, top_color, bottom_color)
    mask = Image.new("L", gradient.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, gradient.width - 1, gradient.height - 1),
        radius=radius,
        fill=255,
    )
    image.paste(gradient, (left, top), mask)


def _draw_wrapped_center(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    fill: str,
    center_x: int,
    top: int,
    max_chars: int,
    line_gap: int = 8,
    bottom: int | None = None,
) -> int:
    lines = wrap(text, width=max_chars) or [""]
    heights = []
    for line in lines:
        bounds = draw.textbbox((0, 0), line, font=font)
        heights.append(bounds[3] - bounds[1])
    total_height = sum(heights) + line_gap * (len(lines) - 1)
    y = top
    if bottom is not None:
        y += max(0, (bottom - top - total_height) // 2)
    for line, height in zip(lines, heights):
        bounds = draw.textbbox((0, 0), line, font=font)
        width = bounds[2] - bounds[0]
        draw.text((center_x - width / 2, y), line, font=font, fill=fill)
        y += height + line_gap
    return y


def _draw_cake(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    theme: dict[str, str],
    scale: float = 1.0,
) -> None:
    def box(left: float, top: float, right: float, bottom: float) -> tuple[int, int, int, int]:
        return (
            round(x + left * scale),
            round(y + top * scale),
            round(x + right * scale),
            round(y + bottom * scale),
        )

    draw.rounded_rectangle(
        box(35, 75, 185, 135),
        radius=max(1, round(14 * scale)),
        fill=theme["accent"],
    )
    draw.rounded_rectangle(
        box(50, 42, 170, 88),
        radius=max(1, round(13 * scale)),
        fill=theme["soft"],
    )
    draw.rectangle(box(65, 19, 76, 44), fill=theme["accent_2"])
    draw.rectangle(box(104, 12, 115, 44), fill=theme["accent_2"])
    draw.rectangle(box(143, 20, 154, 44), fill=theme["accent_2"])
    for cx, cy in ((70, 16), (109, 9), (148, 17)):
        draw.ellipse(box(cx - 6, cy - 8, cx + 6, cy + 7), fill="#FFD166")
    for dot_x in range(55, 165, 28):
        draw.ellipse(box(dot_x, 57, dot_x + 9, 66), fill=theme["accent"])
    draw.rectangle(box(22, 135, 198, 146), fill=theme["text"])


def _draw_balloon(draw: ImageDraw.ImageDraw, x: int, y: int, color: str, text: str = "") -> None:
    draw.ellipse((x, y, x + 72, y + 92), fill=color)
    draw.polygon((x + 32, y + 88, x + 42, y + 88, x + 37, y + 104), fill=color)
    draw.line((x + 37, y + 104, x + 33, y + 142, x + 40, y + 176), fill="#7A6D70", width=2)
    if text:
        _center_text(draw, (x + 8, y + 27, x + 64, y + 62), text, _font(18, True), "#FFFFFF")


def _draw_gift(draw: ImageDraw.ImageDraw, x: int, y: int, theme: dict[str, str]) -> None:
    draw.rounded_rectangle((x, y + 28, x + 95, y + 100), radius=9, fill=theme["accent_2"])
    draw.rectangle((x + 39, y + 28, x + 56, y + 100), fill=theme["accent"])
    draw.rectangle((x, y + 42, x + 95, y + 59), fill=theme["accent"])
    draw.ellipse((x + 22, y, x + 48, y + 28), outline=theme["accent"], width=5)
    draw.ellipse((x + 47, y, x + 73, y + 28), outline=theme["accent"], width=5)


def _draw_heart(draw: ImageDraw.ImageDraw, x: int, y: int, color: str) -> None:
    draw.ellipse((x, y, x + 34, y + 34), fill=color)
    draw.ellipse((x + 26, y, x + 60, y + 34), fill=color)
    draw.polygon((x + 1, y + 20, x + 59, y + 20, x + 30, y + 62), fill=color)


def _draw_mini_heart(draw: ImageDraw.ImageDraw, x: int, y: int, size: int, color) -> None:
    """Draw a compact heart suitable for the subtle animated overlay."""
    half = max(3, size // 2)
    draw.ellipse((x, y, x + half, y + half), fill=color)
    draw.ellipse((x + half // 2, y, x + half + half // 2, y + half), fill=color)
    draw.polygon(
        (
            (x + 1, y + half // 2),
            (x + size - 1, y + half // 2),
            (x + size // 2, y + size),
        ),
        fill=color,
    )


def _draw_sun(draw: ImageDraw.ImageDraw, x: int, y: int, color: str, ray_color: str) -> None:
    draw.ellipse((x + 20, y + 20, x + 76, y + 76), fill=color)
    for start, end in (
        ((x + 48, y), (x + 48, y + 14)),
        ((x + 48, y + 82), (x + 48, y + 96)),
        ((x, y + 48), (x + 14, y + 48)),
        ((x + 82, y + 48), (x + 96, y + 48)),
    ):
        draw.line((*start, *end), fill=ray_color, width=5)


def _rgba(color: str, alpha: int) -> tuple[int, int, int, int]:
    return (*ImageColor.getrgb(color), max(0, min(255, alpha)))


def _next_card_design(rng: random.Random) -> dict[str, object]:
    """Rotate through a shuffled design deck so consecutive cards are different."""
    global _design_order
    if not _design_order:
        _design_order = list(range(len(CARD_DESIGNS)))
        rng.shuffle(_design_order)
    return CARD_DESIGNS[_design_order.pop()]


def _emoji_font(size: int):
    """Use a system emoji font when available, with a safe monochrome fallback."""
    for name in ("seguiemj.ttf", "NotoColorEmoji.ttf", "Apple Color Emoji.ttc", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _fit_font(text: str, size: int, bold: bool, max_width: int):
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    for current_size in range(size, 10, -1):
        font = _font(current_size, bold)
        bounds = probe.textbbox((0, 0), text, font=font)
        if bounds[2] - bounds[0] <= max_width:
            return font
    return _font(10, bold)


def _center_emoji(
    draw: ImageDraw.ImageDraw,
    box: tuple[int, int, int, int],
    emoji: str,
    size: int,
    fill: str = "#FFFFFF",
) -> None:
    _center_text(draw, box, emoji, _emoji_font(size), fill)


def _draw_leaf(draw: ImageDraw.ImageDraw, x: int, y: int, color: str, angle: int = 0) -> None:
    draw.ellipse((x, y, x + 24, y + 54), fill=color)
    draw.line((x + 12, y + 50, x + 38, y + 78), fill=color, width=5)


def _draw_card_pattern(
    draw: ImageDraw.ImageDraw,
    design: dict[str, object],
    include_balloons: bool = True,
    include_corner_heart: bool = True,
) -> None:
    if include_balloons:
        _draw_floating_balloons(draw, design)
    if include_corner_heart:
        _draw_floating_heart(draw, design)
    _draw_gift(draw, 115, 535, design)


def _draw_floating_balloons(
    draw: ImageDraw.ImageDraw,
    design: dict[str, object],
    left_offset: tuple[int, int] = (0, 0),
    right_offset: tuple[int, int] = (0, 0),
) -> None:
    """Place the cute side balloons used by both the still card and GIF frames."""
    accent = str(design["accent"])
    accent_2 = str(design["accent_2"])
    left_x, left_y = left_offset
    right_x, right_y = right_offset
    _draw_balloon(draw, 112 + left_x, 105 + left_y, accent_2, "LOVE")
    _draw_balloon(draw, 1035 + right_x, 470 + right_y, accent, "YAY")


def _draw_floating_heart(
    draw: ImageDraw.ImageDraw,
    design: dict[str, object],
    offset: tuple[int, int] = (0, 0),
) -> None:
    x_offset, y_offset = offset
    _draw_heart(draw, 1010 + x_offset, 112 + y_offset, str(design["accent_2"]))


def _draw_birthday_card(
    name: str,
    wish: str,
    from_name: str,
    design: dict[str, object],
    rng: random.Random,
    include_balloons: bool = True,
    include_corner_heart: bool = True,
):
    width, height = 1200, 800
    background = str(design["background"])
    background_2 = str(design["background_2"])
    panel = str(design["panel"])
    panel_2 = str(design["panel_2"])
    accent = str(design["accent"])
    text_color = str(design["text"])
    soft = str(design["soft"])
    soft_2 = str(design["soft_2"])
    line = str(design["line"])

    image = _vertical_gradient(width, height, background, background_2)
    draw = ImageDraw.Draw(image)

    # Keep the outer background airy; the panel owns the visual hierarchy.
    for x, y, color in (
        (34, 44, soft), (1145, 38, accent), (31, 720, accent),
        (1148, 735, soft), (50, 378, accent), (1128, 390, soft),
    ):
        draw.ellipse((x, y, x + 16, y + 16), fill=color)

    _paint_gradient_box(image, (70, 50, 1130, 750), 42, panel, panel_2)
    draw.rounded_rectangle((70, 50, 1130, 750), radius=42, outline=accent, width=5)
    draw.rounded_rectangle((94, 74, 1106, 726), radius=32, outline=line, width=3)
    _draw_card_pattern(
        draw,
        design,
        include_balloons=include_balloons,
        include_corner_heart=include_corner_heart,
    )

    title = rng.choice(CARD_TITLES)
    _center_text(draw, (205, 135, 995, 220), title, _font(58, True), text_color)
    _center_text(draw, (190, 235, 1010, 320), name, _fit_font(name, 72, True, 790), accent)

    draw.line((260, 345, 940, 345), fill=line, width=3)

    _paint_gradient_box(image, (210, 370, 990, 480), 22, soft, soft_2)
    draw.rounded_rectangle((210, 370, 990, 480), radius=22, outline=line, width=2)
    _draw_wrapped_center(
        draw,
        wish,
        _font(26),
        text_color,
        width // 2,
        370,
        max_chars=55,
        line_gap=5,
        bottom=480,
    )

    _draw_cake(draw, 528, 500, design, scale=0.65)
    draw.line((250, 650, 950, 650), fill=line, width=3)
    signature = f"With love from {from_name} & Luna"
    _center_text(
        draw,
        (145, 646, 1055, 704),
        signature,
        _fit_font(signature, 27, True, 820),
        text_color,
    )
    return image


def render_birthday_card(name: str, wish: str, from_name: str = "Luna") -> io.BytesIO:
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is not installed.")

    rng = random.Random()
    design = _next_card_design(rng)
    image = _draw_birthday_card(
        clean_birthday_name(name) or "Someone",
        wish,
        clean_birthday_name(from_name) or "a friend",
        design,
        rng,
    )

    output = io.BytesIO()
    image.save(output, format="PNG", optimize=True)
    output.seek(0)
    return output


def render_birthday_gif(name: str, wish: str, from_name: str = "a friend") -> io.BytesIO:
    """Create a looping animated birthday card with a personalized signature."""
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is not installed.")

    rng = random.Random()
    recipient = clean_birthday_name(name) or "Someone"
    sender = clean_birthday_name(from_name) or "a friend"
    design = _next_card_design(rng)
    accent = str(design["accent"])
    base = _draw_birthday_card(
        recipient,
        wish,
        sender,
        design,
        rng,
        include_balloons=False,
        include_corner_heart=False,
    )

    # Keep the card itself identical in every frame. Only four nearly transparent
    # hearts gently fade and drift in the empty outer margin.
    heart_specs = (
        (32, 116, 16, 0),
        (1148, 152, 14, 1),
        (34, 664, 14, 2),
        (1144, 678, 16, 3),
    )
    frames = []
    frame_count = 6
    rise_path = (0, -8, -14, -14, -8, 0)
    sway_path = (0, 2, 3, 2, 0, -2)
    for frame_index in range(frame_count):
        frame = base.copy()
        _draw_floating_balloons(
            ImageDraw.Draw(frame),
            design,
            left_offset=(sway_path[frame_index], rise_path[frame_index]),
            right_offset=(-sway_path[frame_index], rise_path[frame_index]),
        )
        _draw_floating_heart(
            ImageDraw.Draw(frame),
            design,
            offset=(round(sway_path[frame_index] / 2), rise_path[frame_index]),
        )
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for x, y, size, phase in heart_specs:
            drift = round(math.sin((frame_index + phase) * math.pi / 3) * 3)
            fade = 34 + round((math.sin((frame_index + phase) * math.pi / 3) + 1) * 9)
            _draw_mini_heart(draw, x, y + drift, size, _rgba(accent, fade))
        frames.append(Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB"))

    output = io.BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=600,
        loop=0,
        disposal=1,
        optimize=False,
    )
    output.seek(0)
    return output
