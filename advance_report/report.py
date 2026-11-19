"""Отчёт на дату: сколько выплачено и сколько осталось по каждой работе и договору.

Порядок расчёта по договору (подробно и с обоснованием — в DECISIONS.md):

1. Статусы работ и платежей восстанавливаются на конец дня отчёта по датам
   событий, а не берутся из колонки status выгрузки.
2. Выплачено = платежи, деньги по которым ушли не позже даты отчёта и не были
   возвращены к этой дате. Платёж в очереди выплатой не считается.
3. Платёж, привязанный к работе, идёт в эту работу (не больше её цены);
   излишек уходит в общий котёл договора.
4. Котёл договора (платежи без привязки, по порядку оплаты) закрывает принятые
   работы по порядку приёмки: сначала самую раннюю.
5. Что осталось в котле — аванс по договору, ещё не зачтённый в работы. Сверх
   стоимости всех неотменённых работ — переплата.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

from .data import Contract, Dataset, Payment, Work, natural_key
from .money import ZERO, format_money


def work_status_on(work: Work, day: date) -> str:
    if work.completed_at is not None and work.completed_at <= day:
        return "done"
    if work.cancelled_at is not None and work.cancelled_at <= day:
        return "cancelled"
    return "planned"


def payment_status_on(payment: Payment, day: date) -> Optional[str]:
    """Статус платежа на конец дня; None — платежа ещё нет в учёте."""
    if payment.refunded_at is not None and payment.refunded_at <= day:
        return "refunded"
    if payment.paid_at is not None and payment.paid_at <= day:
        return "paid"
    if payment.created_at <= day:
        return "queued"
    return None


@dataclass
class _WorkLine:
    work: Work
    status: str
    due: Decimal
    paid: Decimal = ZERO
    paid_from: list[tuple[str, Decimal]] = field(default_factory=list)

    @property
    def remaining(self) -> Decimal:
        return self.due - self.paid

    def take(self, payment_id: str, available: Decimal) -> Decimal:
        """Зачесть в работу не больше, чем ей не хватает; вернуть зачтённое."""
        amount = min(available, self.remaining)
        if amount > 0:
            self.paid += amount
            self.paid_from.append((payment_id, amount))
            return amount
        return ZERO


def _sources(items: list[tuple[str, Decimal]]) -> list[dict]:
    return [{"payment_id": payment_id, "amount": amount} for payment_id, amount in items]


def _total(values) -> Decimal:
    return sum(values, ZERO)


TOTAL_KEYS = (
    "works_due", "accepted", "paid", "paid_to_works", "advance_unapplied",
    "overpaid", "accepted_debt", "queued", "remaining",
)


def build_report(data: Dataset, day: date) -> dict:
    signed = sorted(
        (contract for contract in data.contracts.values() if contract.signed_at <= day),
        key=lambda contract: natural_key(contract.contract_id),
    )
    contracts = [_contract_report(data, contract, day) for contract in signed]
    # Итог — сумма итогов договоров: переплата по одному договору не уменьшает долг по другому.
    totals = {key: _total(contract["totals"][key] for contract in contracts) for key in TOTAL_KEYS}
    return {"report_date": day, "contracts": contracts, "totals": totals}


def _contract_report(data: Dataset, contract: Contract, day: date) -> dict:
    works = sorted(
        (work for work in data.works.values() if work.contract_id == contract.contract_id),
        key=lambda work: natural_key(work.work_id),
    )
    lines = {}
    for work in works:
        status = work_status_on(work, day)
        lines[work.work_id] = _WorkLine(work, status, ZERO if status == "cancelled" else work.price)

    payments = sorted(
        (payment for payment in data.payments.values() if payment.contract_id == contract.contract_id),
        key=lambda payment: natural_key(payment.payment_id),
    )
    states = [(payment, payment_status_on(payment, day)) for payment in payments]
    paid = sorted(
        (payment for payment, state in states if state == "paid"),
        key=lambda payment: (payment.paid_at, natural_key(payment.payment_id)),
    )

    # Шаг 3: привязанные платежи — в свои работы, остальное — в котёл договора.
    pool: list[list] = []
    for payment in paid:
        rest = payment.amount
        if payment.work_id:
            rest -= lines[payment.work_id].take(payment.payment_id, rest)
        if rest > 0:
            pool.append([payment.payment_id, rest])

    # Шаг 4: котёл закрывает принятые работы по порядку приёмки.
    accepted = sorted(
        (line for line in lines.values() if line.status == "done"),
        key=lambda line: (line.work.completed_at, natural_key(line.work.work_id)),
    )
    for line in accepted:
        for item in pool:
            item[1] -= line.take(item[0], item[1])
    unapplied = [(payment_id, rest) for payment_id, rest in pool if rest > 0]

    # Шаг 5: остаток котла — аванс, а сверх стоимости всех работ — переплата.
    unapplied_total = _total(rest for _, rest in unapplied)
    planned_remaining = _total(line.remaining for line in lines.values() if line.status == "planned")
    advance = min(unapplied_total, planned_remaining)
    overpaid = unapplied_total - advance

    totals = {
        "works_due": _total(line.due for line in lines.values()),
        "accepted": _total(line.due for line in accepted),
        "paid": _total(payment.amount for payment in paid),
        "paid_to_works": _total(line.paid for line in lines.values()),
        "advance_unapplied": advance,
        "overpaid": overpaid,
        "accepted_debt": _total(line.remaining for line in accepted),
        "queued": _total(payment.amount for payment, state in states if state == "queued"),
    }
    totals["remaining"] = max(totals["works_due"] - totals["paid"], ZERO)

    return {
        "contract_id": contract.contract_id,
        "contractor": contract.contractor,
        "signed_at": contract.signed_at,
        "amount": contract.amount,
        "works": [_work_entry(line) for line in lines.values()],
        "totals": totals,
        "unapplied_from": _sources(unapplied),
        "payments": [_payment_entry(payment, state) for payment, state in states if state is not None],
        "warnings": _warnings(contract, lines, totals),
    }


def _work_entry(line: _WorkLine) -> dict:
    status_date = {"done": line.work.completed_at, "cancelled": line.work.cancelled_at}.get(line.status)
    return {
        "work_id": line.work.work_id,
        "title": line.work.title,
        "status": line.status,
        "status_date": status_date,
        "price": line.work.price,
        "paid": line.paid,
        "remaining": line.remaining,
        "paid_from": _sources(line.paid_from),
    }


def _payment_entry(payment: Payment, state: str) -> dict:
    return {
        "payment_id": payment.payment_id,
        "work_id": payment.work_id,
        "purpose": payment.purpose,
        "amount": payment.amount,
        "status": state,
        "created_at": payment.created_at,
        "paid_at": payment.paid_at if state in ("paid", "refunded") else None,
        "refunded_at": payment.refunded_at if state == "refunded" else None,
    }


def _warnings(contract: Contract, lines: dict[str, _WorkLine], totals: dict) -> list[str]:
    warnings = []
    if totals["works_due"] != contract.amount:
        message = (
            f"Стоимость работ к оплате {format_money(totals['works_due'])} не совпадает "
            f"с суммой договора {format_money(contract.amount)}"
        )
        cancelled = [line.work.work_id for line in lines.values() if line.status == "cancelled"]
        if cancelled:
            message += f" (отменены: {', '.join(cancelled)})"
        warnings.append(message + ". «Осталось оплатить» посчитано от стоимости работ.")
    if totals["overpaid"] > 0:
        warnings.append(
            f"Переплата {format_money(totals['overpaid'])}: выплачено больше, "
            "чем стоят все неотменённые работы по договору."
        )
    queued, remaining, debt = totals["queued"], totals["remaining"], totals["accepted_debt"]
    if queued > remaining:
        warnings.append(
            f"В очереди на оплату {format_money(queued)}, а осталось оплатить {format_money(remaining)}: "
            f"после оплаты будет переплата {format_money(queued - remaining)}."
        )
    elif queued > debt:
        warnings.append(
            f"В очереди на оплату {format_money(queued)}, а долг за принятые работы {format_money(debt)}: "
            f"{format_money(queued - debt)} после оплаты станет авансом за ещё не принятые работы."
        )
    return warnings
