"""WCAG 2.2 contrast of the colour pairs the dashboard uses for text, in both themes.

Colours are read from the design tokens in styles.css, so a token change that makes text hard to
read fails here. Normal-size text needs 4.5:1 (success criterion 1.4.3).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STYLES = Path(__file__).resolve().parents[1] / "src" / "d365_pqu" / "static" / "styles.css"
AA_TEXT = 4.5
Colour = tuple[float, float, float, float]

# (foreground token, background token, soft token laid over the background or None)
TEXT_PAIRS = [
    ("text", "bg", None),
    ("text", "surface", None),
    ("text", "bg-subtle", None),
    ("muted", "bg", None),
    ("muted", "surface", None),
    ("muted", "surface-raised", None),
    ("muted", "bg-subtle", None),
    ("accent", "bg", None),
    ("accent", "surface", None),
    ("accent", "bg-subtle", None),
    ("accent-ink", "accent", None),
    ("warning-ink", "warning", None),
    ("success", "surface", "success-soft"),
    ("warning", "surface", "warning-soft"),
    ("danger", "surface", "danger-soft"),
    ("accent", "surface", "accent-soft"),
    ("muted", "surface", "neutral-soft"),
    ("text", "surface", "neutral-soft"),
    ("phase-preview", "surface", None),
    ("phase-available", "surface", None),
    ("phase-autoupdate", "surface", None),
    ("phase-supported", "surface", None),
]


def _block(css: str, selector: str) -> dict[str, str]:
    match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.DOTALL)
    assert match, f"{selector} block not found"
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", match.group(1)))


def _tokens(theme: str) -> dict[str, str]:
    css = STYLES.read_text(encoding="utf-8")
    tokens = _block(css, ":root")
    if theme == "light":
        tokens.update(_block(css, 'html[data-theme="light"]'))
    return tokens


def _parse(value: str) -> Colour:
    value = value.strip()
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(part * 2 for part in digits)
        return (
            int(digits[0:2], 16) / 255,
            int(digits[2:4], 16) / 255,
            int(digits[4:6], 16) / 255,
            1.0,
        )
    match = re.fullmatch(r"rgba?\(([^)]*)\)", value)
    assert match, f"unsupported colour {value!r}"
    parts = [float(part) for part in match.group(1).replace("/", ",").split(",")]
    alpha = parts[3] if len(parts) > 3 else 1.0
    return (parts[0] / 255, parts[1] / 255, parts[2] / 255, alpha)


def _over(top: Colour, bottom: Colour) -> Colour:
    alpha = top[3]
    return (
        top[0] * alpha + bottom[0] * (1 - alpha),
        top[1] * alpha + bottom[1] * (1 - alpha),
        top[2] * alpha + bottom[2] * (1 - alpha),
        1.0,
    )


def _luminance(colour: Colour) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    red, green, blue = (channel(value) for value in colour[:3])
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: Colour, background: Colour) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_formula_matches_known_values() -> None:
    assert round(contrast(_parse("#000000"), _parse("#ffffff")), 2) == 21.0
    assert round(contrast(_parse("#777777"), _parse("#ffffff")), 2) == 4.48


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_text_colours_meet_wcag_aa(theme: str) -> None:
    tokens = _tokens(theme)
    failures = []
    for foreground, background, soft in TEXT_PAIRS:
        base = _parse(tokens[background])
        if soft:
            base = _over(_parse(tokens[soft]), base)
        fore = _over(_parse(tokens[foreground]), base)
        ratio = contrast(fore, base)
        if ratio < AA_TEXT:
            label = f"{foreground} on {soft + ' over ' if soft else ''}{background}"
            failures.append(f"{label}: {ratio:.2f}")
    assert failures == [], f"{theme} theme: " + "; ".join(failures)
