"""Деньги и даты: точный разбор и вывод, без float."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

ZERO = Decimal("0.00")
CENT = Decimal("0.01")

_MONEY_RE = re.compile(r"\d+(\.\d{1,2})?")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def parse_money(text: str) -> Decimal:
    """'100000.00' -> Decimal('100000.00'). Минус, запятая и третий знак после точки — ошибка."""
    if not _MONEY_RE.fullmatch(text):
        raise ValueError(
            f"сумма {text!r}: нужно неотрицательное число вида 100000.00 "
            "(точка, не больше двух знаков после неё)"
        )
    return Decimal(text).quantize(CENT)


def parse_date(text: str) -> date:
    """'2026-11-10' -> date(2026, 11, 10). Другие форматы — ошибка."""
    try:
        if not _DATE_RE.fullmatch(text):
            raise ValueError
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"дата {text!r}: нужен формат ГГГГ-ММ-ДД") from None


def format_money(value: Decimal) -> str:
    """Decimal('185000.00') -> '185 000,00' — как пишут суммы в бухгалтерии."""
    sign = "-" if value < 0 else ""
    units, cents = f"{abs(value):.2f}".split(".")
    grouped = f"{int(units):,}".replace(",", " ")
    return f"{sign}{grouped},{cents}"


def format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")
