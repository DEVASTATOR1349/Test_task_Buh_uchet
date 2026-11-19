"""Вывод отчёта: JSON для программ и текстовая таблица для человека."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from .money import format_date, format_money

WORK_STATUS_TEXT = {"done": "принята", "cancelled": "отменена", "planned": "запланирована"}
PAYMENT_STATUS_TEXT = {"paid": "оплачен", "queued": "в очереди", "refunded": "возвращён"}


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"не умею сериализовать {type(value).__name__}")


def to_json(report: dict) -> str:
    return json.dumps(report, ensure_ascii=False, indent=2, default=_json_default)


def _table(headers: list[str], rows: list[list[str]], right: set[int]) -> list[str]:
    widths = [max(len(row[i]) for row in [headers, *rows]) for i in range(len(headers))]

    def line(cells: list[str]) -> str:
        parts = [cell.rjust(width) if i in right else cell.ljust(width) for i, (cell, width) in enumerate(zip(cells, widths))]
        return "  ".join(parts).rstrip()

    return [line(headers), line(["-" * width for width in widths]), *(line(row) for row in rows)]


def _sources_text(items: list[dict]) -> str:
    return "; ".join(f"{item['payment_id']} {format_money(item['amount'])}" for item in items)


def _contract_text(contract: dict) -> list[str]:
    out = [
        f"Договор {contract['contract_id']} — {contract['contractor']}, подписан {format_date(contract['signed_at'])}, "
        f"сумма договора {format_money(contract['amount'])}",
        "",
    ]
    work_rows = []
    for work in contract["works"]:
        status = WORK_STATUS_TEXT[work["status"]]
        if work["status_date"]:
            status += " " + format_date(work["status_date"])
        work_rows.append([
            work["work_id"], work["title"], status,
            format_money(work["price"]), format_money(work["paid"]), format_money(work["remaining"]),
            _sources_text(work["paid_from"]),
        ])
    out += _table(
        ["Работа", "Название", "Статус на дату", "Цена", "Выплачено", "Осталось", "Чем оплачено"],
        work_rows, right={3, 4, 5},
    )

    totals = contract["totals"]
    summary = [
        ["Стоимость работ без отменённых", totals["works_due"]],
        ["  из них приняты", totals["accepted"]],
        ["Выплачено", totals["paid"]],
        ["  зачтено в работы", totals["paid_to_works"]],
        ["  аванс, ещё не зачтённый в работы", totals["advance_unapplied"]],
        ["  переплата", totals["overpaid"]],
        ["Осталось оплатить по договору", totals["remaining"]],
        ["  из них долг за принятые работы", totals["accepted_debt"]],
        ["В очереди на оплату (ещё не выплачено)", totals["queued"]],
    ]
    out += ["", f"Итоги по договору {contract['contract_id']}"]
    rows = [[label, format_money(value)] for label, value in summary]
    out += ["  " + row for row in _table(["", ""], rows, right={1})[2:]]
    if contract["unapplied_from"]:
        out.append(f"  Не зачтённые в работы деньги — из платежей: {_sources_text(contract['unapplied_from'])}")

    if contract["payments"]:
        payment_rows = []
        for payment in contract["payments"]:
            status = PAYMENT_STATUS_TEXT[payment["status"]]
            if payment["status"] == "paid":
                status += " " + format_date(payment["paid_at"])
            elif payment["status"] == "refunded":
                status += f" {format_date(payment['refunded_at'])} (оплачен {format_date(payment['paid_at'])})"
            else:
                status += f" с {format_date(payment['created_at'])}"
            purpose = f"{payment['work_id']}: {payment['purpose']}" if payment["work_id"] else payment["purpose"]
            payment_rows.append([payment["payment_id"], status, format_money(payment["amount"]), purpose])
        out += ["", "Платежи на дату"]
        out += ["  " + row for row in _table(["Платёж", "Статус на дату", "Сумма", "Назначение"], payment_rows, right={2})]

    if contract["warnings"]:
        out += ["", "Обратите внимание"]
        out += [f"  - {warning}" for warning in contract["warnings"]]
    return out


def to_text(report: dict) -> str:
    day = format_date(report["report_date"])
    out = [
        f"Отчёт по оплате работ на {day} (конец дня)",
        "Суммы в рублях. Статусы работ и платежей — на дату отчёта, а не на момент выгрузки.",
        "Платежи без привязки к работе зачтены в принятые работы по порядку приёмки.",
    ]
    if not report["contracts"]:
        out += ["", "На эту дату нет подписанных договоров."]
    for contract in report["contracts"]:
        out += ["", "=" * 100, "", *_contract_text(contract)]
    return "\n".join(out) + "\n"
