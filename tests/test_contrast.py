"""WCAG 2.2 contrast of the colour pairs the dashboard uses, in both themes.

Colours are read from the design tokens in styles.css, so a token change that makes text hard to
read fails here. Text needs 4.5:1 (success criterion 1.4.3); chart shapes and control borders
that carry meaning need 3:1 against the page (1.4.11).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

STYLES = Path(__file__).resolve().parents[1] / "src" / "d365_pqu" / "static" / "styles.css"
AA_TEXT = 4.5
AA_GRAPHICS = 3.0
Colour = tuple[float, float, float, float]

# (foreground token, background token): text set in the first colour on the second.
TEXT_PAIRS = [
    ("text", "bg"),
    ("text", "bg-inset"),
    ("muted", "bg"),
    ("muted", "bg-inset"),
    ("link", "bg"),
    ("link", "bg-inset"),
    # In-Progress status, today in the agenda, New and Due soon tags.
    ("signal", "bg"),
    ("signal", "bg-inset"),
    # Warnings: source flags, stale data, inline alerts.
    ("warn", "bg"),
    ("warn", "warn-bg"),
    ("text", "warn-bg"),
    # Errors and Canceled.
    ("danger", "bg"),
    ("danger", "danger-bg"),
    ("text", "danger-bg"),
    # Timeline bar labels: completed, in progress; primary buttons and pressed toggles.
    ("muted", "past-bg"),
    ("on-signal", "signal"),
    ("bg", "text"),
]

# Chart marks and the borders of inputs and buttons, against the page.
GRAPHIC_PAIRS = [
    ("text", "bg"),
    ("signal", "bg"),
    ("past", "bg"),
]


def _block(css: str, selector: str) -> dict[str, str]:
    match = re.search(re.escape(selector) + r"\s*\{(.*?)\}", css, re.DOTALL)
    assert match, f"{selector} block not found"
    return dict(re.findall(r"--([\w-]+):\s*([^;]+);", match.group(1)))


def _tokens(theme: str) -> dict[str, str]:
    css = STYLES.read_text(encoding="utf-8")
    tokens = _block(css, ":root")
    if theme == "dark":
        tokens.update(_block(css, 'html[data-theme="dark"]'))
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


def _failures(tokens: dict[str, str], pairs: list[tuple[str, str]], minimum: float) -> list[str]:
    failures = []
    for foreground, background in pairs:
        base = _parse(tokens[background])
        ratio = contrast(_over(_parse(tokens[foreground]), base), base)
        if ratio < minimum:
            failures.append(f"{foreground} on {background}: {ratio:.2f}")
    return failures


def test_contrast_formula_matches_known_values() -> None:
    assert round(contrast(_parse("#000000"), _parse("#ffffff")), 2) == 21.0
    assert round(contrast(_parse("#777777"), _parse("#ffffff")), 2) == 4.48


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_text_colours_meet_wcag_aa(theme: str) -> None:
    failures = _failures(_tokens(theme), TEXT_PAIRS, AA_TEXT)
    assert failures == [], f"{theme} theme: " + "; ".join(failures)


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_chart_marks_are_distinguishable_from_the_page(theme: str) -> None:
    failures = _failures(_tokens(theme), GRAPHIC_PAIRS, AA_GRAPHICS)
    assert failures == [], f"{theme} theme: " + "; ".join(failures)
