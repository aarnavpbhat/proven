"""Reading figures, and why a rounded figure is not a contradiction."""
import pytest

from proven.money import compare, find_money, find_percents, fmt_money, fmt_signed, parse_money


@pytest.mark.parametrize("text, value, half", [
    ("$90K", 90_000, 500),
    ("$91.2K", 91_200, 50),
    ("$1.25M", 1_250_000, 5_000),
    ("$1.2 million", 1_200_000, 50_000),
    ("$90,000", 90_000, 0.5),
    ("$2.5bn", 2_500_000_000, 50_000_000),
    ("90K", 90_000, 500),
    ("$1.2MM", 1_200_000, 50_000),
])
def test_money_figures_keep_their_written_precision(text, value, half):
    figure = parse_money(text)
    assert figure is not None
    assert figure.value == pytest.approx(value)
    assert figure.half_unit == pytest.approx(half)


def test_accounting_parentheses_are_negative_but_ordinary_parentheses_are_not():
    assert parse_money("($12.5K)").value == pytest.approx(-12_500)
    figures = find_money("Legal rose (prior $30K) to $120K")
    assert [f.value for f in figures] == [30_000, 120_000]
    assert figures[0].text == "$30K"


@pytest.mark.parametrize("text", ["2026", "in Q4", "5 months", "18%", "12.5%", "3 people"])
def test_numbers_that_are_not_money_are_not_read_as_money(text):
    assert find_money(text) == []


def test_percentages_are_points():
    [pct] = find_percents("up 18.4% on the month")
    assert pct.value == pytest.approx(18.4)
    assert pct.half_unit == pytest.approx(0.05)


def test_a_rounded_figure_agrees_with_the_value_it_rounds():
    # Rounding is not a contradiction: "$90K" for $91,240.
    assert compare(91_240, parse_money("$90K"), 0.05, 0.10) == "agree"
    assert compare(90_400, parse_money("$90K"), 0.0, 0.0) == "agree"   # written precision alone


def test_three_bands():
    stated = parse_money("$100K")
    assert compare(96_000, stated, 0.05, 0.10) == "agree"
    assert compare(92_000, stated, 0.05, 0.10) == "near"
    assert compare(60_000, stated, 0.05, 0.10) == "disagree"


def test_formatting():
    assert fmt_money(50412.4) == "$50,412"
    assert fmt_money(-12040) == "-$12,040"
    assert fmt_signed(100) == "+$100"


def test_full_figures_and_currency_codes():
    full = parse_money("$1,250,000")
    assert full.value == 1_250_000 and full.half_unit == 0.5
    assert parse_money("USD 2.5M").value == pytest.approx(2_500_000)
