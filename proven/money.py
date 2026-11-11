"""Reading figures out of prose, and comparing them at the precision they were written to.

THE ONE LESSON THIS MODULE CARRIES

A checker that compares a recomputed value with a stated one using a relative
tolerance alone calls rounded figures contradictions, because the stated value
was rounded before it was written down. The fix is to compare at the precision
the figure was *written to*: round the recomputed value the same way and see
whether it lands on the stated one.

Variance commentary is written in rounded figures as a matter of course: "$90K"
for a movement of $91,240 is not an error, and a checker that flags it is worse
than no checker. So a stated figure keeps the text it was written as, and the
half-unit of its last written digit is part of its value.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SCALES = {
    "k": 1e3, "thousand": 1e3,
    "m": 1e6, "mm": 1e6, "million": 1e6,
    "b": 1e9, "bn": 1e9, "billion": 1e9,
}

# A money figure needs a currency marker or a scale suffix. A bare number in
# prose is as likely to be a year, a headcount or a page number as an amount,
# and guessing which is how a checker manufactures findings.
_MONEY = re.compile(
    r"""
    (?P<open>\()?
    (?P<sign>[-−])?
    (?P<cur>US\$|\$|USD\s?)?
    (?P<num>\d{1,3}(?:,\d{3})+|\d+)
    (?P<frac>\.\d+)?
    (?:\s?(?P<scale>thousand|million|billion|bn|mm|MM|[kKmMbB])(?![A-Za-z]))?
    (?P<close>\))?
    (?!\s?(?:%|percent))
    """,
    re.VERBOSE,
)

_PERCENT = re.compile(r"(?P<num>\d+(?:\.\d+)?)\s?(?:%|percent\b)")


@dataclass(frozen=True)
class Figure:
    """A number as an explanation wrote it.

    `half_unit` is the written precision: "$90K" is good to ±$500, "$91.2K" to
    ±$50, "18%" to ±0.5 points. It is computed from the string, never the float.
    """

    text: str
    value: float
    half_unit: float
    start: int = 0
    end: int = 0

    def to_dict(self) -> dict:
        return {"text": self.text, "value": self.value, "half_unit": self.half_unit}


def _half_unit(frac: str | None, factor: float) -> float:
    decimals = len(frac) - 1 if frac else 0
    return 0.5 * (10 ** -decimals) * factor


def find_money(text: str) -> list[Figure]:
    """Every money figure in `text`, in order, with character offsets."""
    figures: list[Figure] = []
    for match in _MONEY.finditer(text):
        if not (match.group("cur") or match.group("scale")):
            continue
        scale = (match.group("scale") or "").lower()
        factor = SCALES.get(scale, 1.0)
        number = float(match.group("num").replace(",", "") + (match.group("frac") or ""))
        negative = bool(match.group("sign")) or bool(match.group("open") and match.group("close"))
        start, end = match.span()
        # A parenthesis is accounting notation only when it closes; otherwise it
        # is ordinary punctuation and does not belong to the figure.
        if match.group("open") and not match.group("close"):
            start += 1
        if match.group("close") and not match.group("open"):
            end -= 1
        figures.append(Figure(
            text=text[start:end].strip(),
            value=-number * factor if negative else number * factor,
            half_unit=_half_unit(match.group("frac"), factor),
            start=start,
            end=end,
        ))
    return figures


def find_percents(text: str) -> list[Figure]:
    """Every percentage in `text`. Stated as points: "18%" is 18.0, not 0.18."""
    out: list[Figure] = []
    for match in _PERCENT.finditer(text):
        num = match.group("num")
        frac = "." + num.split(".", 1)[1] if "." in num else None
        out.append(Figure(
            text=match.group(0),
            value=float(num),
            half_unit=_half_unit(frac, 1.0),
            start=match.start(),
            end=match.end(),
        ))
    return out


def parse_money(text: str) -> Figure | None:
    """The single money figure `text` consists of, or None."""
    found = find_money(text)
    return found[0] if len(found) == 1 else None


def parse_percent(text: str) -> Figure | None:
    """The single percentage `text` consists of, or None."""
    found = find_percents(text)
    return found[0] if len(found) == 1 else None


def compare(actual: float, stated: Figure, rel_tolerance: float, review_band: float) -> str:
    """'agree', 'near' or 'disagree' — three answers, because the honest one is sometimes the middle.

    Agreement is either written precision (the stated figure is what the actual
    rounds to) or a relative tolerance against the larger of the two, so that
    neither side is privileged. Between the tolerance and the review band the
    answer is 'near': close enough that a person should decide, far enough that
    passing it would be a guess.
    """
    diff = abs(actual - stated.value)
    if diff <= stated.half_unit + 1e-9:
        return "agree"
    scale = max(abs(actual), abs(stated.value))
    if scale == 0 or diff <= rel_tolerance * scale:
        return "agree"
    if diff <= review_band * scale:
        return "near"
    return "disagree"


def fmt_money(value: float) -> str:
    """'$50,412' / '-$12,040'. Whole dollars: commentary never needs cents."""
    sign = "-" if value < -0.005 else ""
    return f"{sign}${abs(value):,.0f}"


def fmt_signed(value: float) -> str:
    """'+$1,200' / '-$1,200': a movement, with its sign always shown."""
    return ("+" if value > 0.005 else "") + fmt_money(value)


def fmt_pct(share: float) -> str:
    """A share (0.33) as a whole percentage ('33%')."""
    return f"{share * 100:.0f}%"
