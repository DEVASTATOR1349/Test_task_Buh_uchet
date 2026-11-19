"""Загрузка выгрузки из учёта (data/*.csv) и проверка её целостности.

Любая ошибка в данных останавливает построение отчёта: лучше не дать отчёт,
чем дать отчёт с молча пропущенным платежом.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Callable, Optional

from .money import parse_date, parse_money

WORK_STATUSES = ("planned", "done", "cancelled")
PAYMENT_STATUSES = ("paid", "queued", "refunded")


class DataError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


@dataclass(frozen=True)
class Contract:
    contract_id: str
    contractor: str
    amount: Decimal
    signed_at: date


@dataclass(frozen=True)
class Work:
    work_id: str
    contract_id: str
    title: str
    price: Decimal
    status: str
    completed_at: Optional[date]
    cancelled_at: Optional[date]


@dataclass(frozen=True)
class Payment:
    payment_id: str
    contract_id: str
    work_id: Optional[str]
    purpose: str
    amount: Decimal
    status: str
    created_at: date
    paid_at: Optional[date]
    refunded_at: Optional[date]


@dataclass(frozen=True)
class Dataset:
    contracts: dict[str, Contract]
    works: dict[str, Work]
    payments: dict[str, Payment]


def natural_key(identifier: str) -> list:
    """'W-2' раньше 'W-10': числа внутри номера сравниваются как числа."""
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", identifier)]


class _Row:
    """Строка CSV, которая собирает ошибки вместо того, чтобы падать на первой."""

    def __init__(self, values: dict[str, str], where: str, problems: list[str]):
        self.values = values
        self.where = where
        self.problems = problems

    def error(self, message: str) -> None:
        self.problems.append(f"{self.where}: {message}")

    def text(self, column: str, required: bool = True) -> str:
        value = self.values[column]
        if required and not value:
            self.error(f"не заполнено {column}")
        return value

    def parsed(self, column: str, parser: Callable, required: bool = True):
        value = self.values[column]
        if not value:
            if required:
                self.error(f"не заполнено {column}")
            return None
        try:
            return parser(value)
        except ValueError as exc:
            self.error(f"{column}: {exc}")
            return None


def _read_rows(path: Path, columns: tuple[str, ...], problems: list[str]) -> list[_Row]:
    if not path.is_file():
        problems.append(f"{path.name}: файл не найден в {path.parent}")
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in columns if column not in (reader.fieldnames or [])]
        if missing:
            problems.append(f"{path.name}: нет колонок {', '.join(missing)}")
            return []
        rows = []
        for raw in reader:
            where = f"{path.name}, строка {reader.line_num}"
            if None in raw:
                problems.append(f"{where}: значений больше, чем колонок")
                continue
            values = {column: (raw[column] or "").strip() for column in columns}
            rows.append(_Row(values, where, problems))
        return rows


def _check_unique(row: _Row, identifier: str, seen: dict) -> None:
    if identifier and identifier in seen:
        row.error(f"номер {identifier} повторяется")


def _check_status_dates(row: _Row, status: str, columns: tuple[str, ...], expected: set[str]) -> None:
    """Для статуса должны быть заполнены ровно те даты, которые ему положены."""
    for column in columns:
        filled = row.values[column] != ""
        if column in expected and not filled:
            row.error(f"статус {status}, но не заполнено {column}")
        if column not in expected and filled:
            row.error(f"статус {status}, но заполнено {column}")


def load_dataset(data_dir: Path) -> Dataset:
    data_dir = Path(data_dir)
    problems: list[str] = []

    contracts: dict[str, Contract] = {}
    for row in _read_rows(data_dir / "contracts.csv", ("contract_id", "contractor", "amount", "signed_at"), problems):
        contract_id = row.text("contract_id")
        _check_unique(row, contract_id, contracts)
        contract = Contract(
            contract_id=contract_id,
            contractor=row.text("contractor"),
            amount=row.parsed("amount", parse_money),
            signed_at=row.parsed("signed_at", parse_date),
        )
        if contract_id and contract_id not in contracts:
            contracts[contract_id] = contract

    works: dict[str, Work] = {}
    work_columns = ("work_id", "contract_id", "title", "price", "status", "completed_at", "cancelled_at")
    for row in _read_rows(data_dir / "works.csv", work_columns, problems):
        work_id = row.text("work_id")
        _check_unique(row, work_id, works)
        contract_id = row.text("contract_id")
        if contract_id and contract_id not in contracts:
            row.error(f"договор {contract_id} не найден в contracts.csv")
        status = row.text("status")
        work = Work(
            work_id=work_id,
            contract_id=contract_id,
            title=row.text("title", required=False),
            price=row.parsed("price", parse_money),
            status=status,
            completed_at=row.parsed("completed_at", parse_date, required=False),
            cancelled_at=row.parsed("cancelled_at", parse_date, required=False),
        )
        dates = ("completed_at", "cancelled_at")
        if status == "done":
            _check_status_dates(row, status, dates, {"completed_at"})
        elif status == "cancelled":
            _check_status_dates(row, status, dates, {"cancelled_at"})
        elif status == "planned":
            _check_status_dates(row, status, dates, set())
        elif status:
            row.error(f"неизвестный статус {status!r}, ожидается один из {', '.join(WORK_STATUSES)}")
        if work_id and work_id not in works:
            works[work_id] = work

    payments: dict[str, Payment] = {}
    payment_columns = (
        "payment_id", "contract_id", "work_id", "purpose", "amount",
        "status", "created_at", "paid_at", "refunded_at",
    )
    for row in _read_rows(data_dir / "payments.csv", payment_columns, problems):
        payment_id = row.text("payment_id")
        _check_unique(row, payment_id, payments)
        contract_id = row.text("contract_id")
        if contract_id and contract_id not in contracts:
            row.error(f"договор {contract_id} не найден в contracts.csv")
        work_id = row.text("work_id", required=False) or None
        if work_id:
            work = works.get(work_id)
            if work is None:
                row.error(f"работа {work_id} не найдена в works.csv")
            elif contract_id and work.contract_id != contract_id:
                row.error(f"работа {work_id} относится к договору {work.contract_id}, а платёж — к {contract_id}")
        status = row.text("status")
        payment = Payment(
            payment_id=payment_id,
            contract_id=contract_id,
            work_id=work_id,
            purpose=row.text("purpose", required=False),
            amount=row.parsed("amount", parse_money),
            status=status,
            created_at=row.parsed("created_at", parse_date),
            paid_at=row.parsed("paid_at", parse_date, required=False),
            refunded_at=row.parsed("refunded_at", parse_date, required=False),
        )
        if payment.amount is not None and payment.amount == 0:
            row.error("сумма платежа 0")
        dates = ("paid_at", "refunded_at")
        if status == "paid":
            _check_status_dates(row, status, dates, {"paid_at"})
        elif status == "queued":
            _check_status_dates(row, status, dates, set())
        elif status == "refunded":
            _check_status_dates(row, status, dates, {"paid_at", "refunded_at"})
            if payment.paid_at and payment.refunded_at and payment.refunded_at < payment.paid_at:
                row.error("refunded_at раньше paid_at")
        elif status:
            row.error(f"неизвестный статус {status!r}, ожидается один из {', '.join(PAYMENT_STATUSES)}")
        if payment_id and payment_id not in payments:
            payments[payment_id] = payment

    if problems:
        raise DataError(problems)
    return Dataset(contracts=contracts, works=works, payments=payments)
