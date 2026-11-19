import unittest
from datetime import date, timedelta

from advance_report.data import load_dataset
from advance_report.money import ZERO
from advance_report.render import to_json, to_text
from advance_report.report import build_report

from .support import REAL_DATA, make_dataset, rub

REAL = load_dataset(REAL_DATA)


def contract(report: dict, contract_id: str) -> dict:
    return next(item for item in report["contracts"] if item["contract_id"] == contract_id)


def works(entry: dict) -> dict:
    """{work_id: (статус, выплачено, осталось)} — компактно для сравнения."""
    return {work["work_id"]: (work["status"], str(work["paid"]), str(work["remaining"])) for work in entry["works"]}


def totals(entry: dict) -> dict:
    return {key: str(value) for key, value in entry["totals"].items()}


class CheckDateTest(unittest.TestCase):
    """Дата из письма бухгалтера: 10.11.2026."""

    def setUp(self):
        self.report = build_report(REAL, date(2026, 11, 10))

    def test_contract_d1(self):
        d1 = contract(self.report, "D-1")
        self.assertEqual(works(d1), {
            "W-11": ("done", "100000.00", "0.00"),
            "W-12": ("done", "100000.00", "0.00"),
            "W-13": ("cancelled", "0.00", "0.00"),
            "W-14": ("done", "100000.00", "0.00"),
            "W-15": ("planned", "0.00", "100000.00"),
            "W-16": ("planned", "0.00", "100000.00"),
        })
        self.assertEqual(totals(d1), {
            "works_due": "500000.00",
            "accepted": "300000.00",
            "paid": "315000.00",
            "paid_to_works": "300000.00",
            "advance_unapplied": "15000.00",
            "overpaid": "0.00",
            "accepted_debt": "0.00",
            "queued": "150000.00",
            "remaining": "185000.00",
        })

    def test_contract_d2(self):
        d2 = contract(self.report, "D-2")
        self.assertEqual(works(d2), {
            "W-21": ("done", "20000.00", "0.00"),
            "W-22": ("done", "30000.00", "0.00"),
            "W-23": ("planned", "0.00", "40000.00"),  # принята только 11.11
        })
        self.assertEqual(totals(d2), {
            "works_due": "90000.00",
            "accepted": "50000.00",
            "paid": "75000.00",  # P-8 оплачен только 12.11
            "paid_to_works": "50000.00",
            "advance_unapplied": "25000.00",
            "overpaid": "0.00",
            "accepted_debt": "0.00",
            "queued": "0.00",
            "remaining": "15000.00",
        })

    def test_payment_sources_show_what_paid_for_what(self):
        d1 = contract(self.report, "D-1")
        w14 = next(work for work in d1["works"] if work["work_id"] == "W-14")
        self.assertEqual(
            [(item["payment_id"], str(item["amount"])) for item in w14["paid_from"]],
            [("P-3", "15000.00"), ("P-1", "85000.00")],
        )
        self.assertEqual([(item["payment_id"], str(item["amount"])) for item in d1["unapplied_from"]], [("P-1", "15000.00")])

    def test_payment_statuses_on_date(self):
        d1 = contract(self.report, "D-1")
        self.assertEqual({p["payment_id"]: p["status"] for p in d1["payments"]},
                         {"P-1": "paid", "P-2": "refunded", "P-3": "paid", "P-4": "queued"})
        d2 = contract(self.report, "D-2")
        self.assertNotIn("P-8", {p["payment_id"] for p in d2["payments"]})  # заведён только 12.11

    def test_report_totals_are_sums_of_contract_totals(self):
        self.assertEqual(totals(self.report), {
            "works_due": "590000.00",
            "accepted": "350000.00",
            "paid": "390000.00",
            "paid_to_works": "350000.00",
            "advance_unapplied": "40000.00",
            "overpaid": "0.00",
            "accepted_debt": "0.00",
            "queued": "150000.00",
            "remaining": "200000.00",
        })

    def test_overpayment_on_one_contract_does_not_reduce_debt_on_another(self):
        report = build_report(REAL, date(2026, 11, 12))
        self.assertEqual(report["totals"]["overpaid"], rub("5000.00"))
        self.assertEqual(report["totals"]["remaining"], contract(report, "D-1")["totals"]["remaining"])

    def test_warnings(self):
        d1 = contract(self.report, "D-1")
        self.assertEqual(len(d1["warnings"]), 2)
        self.assertIn("отменены: W-13", d1["warnings"][0])
        self.assertIn("станет авансом", d1["warnings"][1])
        self.assertEqual(contract(self.report, "D-2")["warnings"], [])


class PointInTimeTest(unittest.TestCase):
    """Статусы выгрузки «на сейчас» пересчитываются на дату отчёта."""

    def test_refunded_payment_counts_until_refund(self):
        d1 = contract(build_report(REAL, date(2026, 9, 5)), "D-1")
        self.assertEqual(d1["totals"]["paid"], rub("350000.00"))  # P-1 + P-2, возврат ещё впереди
        d1 = contract(build_report(REAL, date(2026, 9, 10)), "D-1")
        self.assertEqual(d1["totals"]["paid"], rub("300000.00"))  # в день возврата уже не считается

    def test_cancelled_work_is_due_until_cancellation(self):
        before = contract(build_report(REAL, date(2026, 10, 11)), "D-1")
        self.assertEqual(works(before)["W-13"][0], "planned")
        self.assertEqual(before["totals"]["works_due"], rub("600000.00"))
        self.assertEqual(before["warnings"], [])
        after = contract(build_report(REAL, date(2026, 10, 12)), "D-1")
        self.assertEqual(works(after)["W-13"][0], "cancelled")
        self.assertEqual(after["totals"]["works_due"], rub("500000.00"))

    def test_queued_payment_appears_only_after_creation(self):
        d1 = contract(build_report(REAL, date(2026, 10, 31)), "D-1")
        self.assertEqual(d1["totals"]["queued"], ZERO)
        self.assertNotIn("P-4", {p["payment_id"] for p in d1["payments"]})

    def test_bound_payment_before_acceptance_stays_on_its_work(self):
        d1 = contract(build_report(REAL, date(2026, 10, 25)), "D-1")
        self.assertEqual(works(d1)["W-14"], ("planned", "15000.00", "85000.00"))

    def test_oldest_accepted_work_is_closed_first(self):
        d2 = contract(build_report(REAL, date(2026, 10, 10)), "D-2")
        self.assertEqual(works(d2)["W-21"], ("done", "20000.00", "0.00"))
        self.assertEqual(works(d2)["W-22"], ("done", "25000.00", "5000.00"))
        self.assertEqual(d2["totals"]["accepted_debt"], rub("5000.00"))
        self.assertEqual(d2["totals"]["remaining"], rub("45000.00"))

    def test_overpayment_after_last_payment(self):
        d2 = contract(build_report(REAL, date(2026, 11, 12)), "D-2")
        self.assertEqual(works(d2)["W-23"], ("done", "40000.00", "0.00"))
        self.assertEqual(d2["totals"]["paid"], rub("95000.00"))
        self.assertEqual(d2["totals"]["overpaid"], rub("5000.00"))
        self.assertEqual(d2["totals"]["remaining"], ZERO)
        self.assertIn("Переплата 5 000,00", d2["warnings"][0])

    def test_contract_signed_after_report_date_is_absent(self):
        report = build_report(REAL, date(2026, 9, 19))
        self.assertEqual([item["contract_id"] for item in report["contracts"]], ["D-1"])
        self.assertEqual(build_report(REAL, date(2026, 8, 24))["contracts"], [])

    def test_totals_reconcile_on_every_day(self):
        """Суммы по строкам сходятся с итогами договора на любой день периода."""
        day = date(2026, 8, 20)
        while day <= date(2026, 11, 30):
            for entry in build_report(REAL, day)["contracts"]:
                with self.subTest(day=day, contract=entry["contract_id"]):
                    t = entry["totals"]
                    lines = entry["works"]
                    self.assertEqual(t["paid"], sum((w["paid"] for w in lines), ZERO) + t["advance_unapplied"] + t["overpaid"])
                    self.assertEqual(t["paid_to_works"], sum((w["paid"] for w in lines), ZERO))
                    self.assertEqual(t["remaining"], sum((w["remaining"] for w in lines), ZERO) - t["advance_unapplied"])
                    for work in lines:
                        self.assertGreaterEqual(work["remaining"], ZERO)
                        self.assertLessEqual(work["paid"], work["price"])
                        self.assertEqual(sum((s["amount"] for s in work["paid_from"]), ZERO), work["paid"])
            day += timedelta(days=1)


class AllocationRulesTest(unittest.TestCase):
    """Крайние случаи, которых нет в выгрузке, но которые возможны."""

    CONTRACT = "D-1,Подрядчик,300.00,2026-01-01"

    def test_bound_payment_excess_goes_to_contract_pool(self):
        data = make_dataset(
            self.CONTRACT,
            works="W-1,D-1,Первая,100.00,done,2026-02-01,\nW-2,D-1,Вторая,200.00,done,2026-02-02,",
            payments="P-1,D-1,W-1,Оплата первой,150.00,paid,2026-02-05,2026-02-05,",
        )
        entry = build_report(data, date(2026, 3, 1))["contracts"][0]
        self.assertEqual(works(entry), {"W-1": ("done", "100.00", "0.00"), "W-2": ("done", "50.00", "150.00")})

    def test_payment_bound_to_cancelled_work_goes_to_pool(self):
        data = make_dataset(
            self.CONTRACT,
            works="W-1,D-1,Отменённая,100.00,cancelled,,2026-02-01\nW-2,D-1,Принятая,200.00,done,2026-02-10,",
            payments="P-1,D-1,W-1,Аванс за первую,100.00,paid,2026-01-15,2026-01-15,",
        )
        entry = build_report(data, date(2026, 3, 1))["contracts"][0]
        self.assertEqual(works(entry), {"W-1": ("cancelled", "0.00", "0.00"), "W-2": ("done", "100.00", "100.00")})
        # До отмены деньги сидели на своей работе.
        entry = build_report(data, date(2026, 1, 20))["contracts"][0]
        self.assertEqual(works(entry)["W-1"], ("planned", "100.00", "0.00"))

    def test_events_on_report_date_are_included(self):
        data = make_dataset(
            self.CONTRACT,
            works="W-1,D-1,Работа,300.00,done,2026-02-01,",
            payments="P-1,D-1,,Оплата,300.00,paid,2026-02-01,2026-02-01,",
        )
        entry = build_report(data, date(2026, 2, 1))["contracts"][0]
        self.assertEqual(works(entry), {"W-1": ("done", "300.00", "0.00")})
        entry = build_report(data, date(2026, 1, 31))["contracts"][0]
        self.assertEqual(works(entry), {"W-1": ("planned", "0.00", "300.00")})
        self.assertEqual(entry["payments"], [])

    def test_same_acceptance_date_uses_natural_work_order(self):
        data = make_dataset(
            "D-1,Подрядчик,200.00,2026-01-01",
            works="W-10,D-1,Десятая,100.00,done,2026-02-01,\nW-2,D-1,Вторая,100.00,done,2026-02-01,",
            payments="P-1,D-1,,Аванс,150.00,paid,2026-01-10,2026-01-10,",
        )
        entry = build_report(data, date(2026, 3, 1))["contracts"][0]
        self.assertEqual(works(entry), {"W-2": ("done", "100.00", "0.00"), "W-10": ("done", "50.00", "50.00")})

    def test_payment_paid_before_it_was_entered_counts_as_paid(self):
        data = make_dataset(
            "D-1,Подрядчик,100.00,2026-01-01",
            works="W-1,D-1,Работа,100.00,done,2026-01-05,",
            payments="P-1,D-1,,Оплата задним числом,100.00,paid,2026-02-01,2026-01-10,",
        )
        entry = build_report(data, date(2026, 1, 20))["contracts"][0]
        self.assertEqual(entry["totals"]["paid"], rub("100.00"))

    def test_queued_more_than_remaining_warns_about_overpayment(self):
        data = make_dataset(
            "D-1,Подрядчик,100.00,2026-01-01",
            works="W-1,D-1,Работа,100.00,done,2026-01-05,",
            payments="P-1,D-1,,Оплата,80.00,paid,2026-01-10,2026-01-10,\nP-2,D-1,,Ещё,50.00,queued,2026-01-11,,",
        )
        entry = build_report(data, date(2026, 1, 20))["contracts"][0]
        self.assertEqual(entry["warnings"], [
            "В очереди на оплату 50,00, а осталось оплатить 20,00: после оплаты будет переплата 30,00."
        ])


class RenderTest(unittest.TestCase):
    def test_json_keeps_money_as_exact_strings(self):
        text = to_json(build_report(REAL, date(2026, 11, 10)))
        self.assertIn('"remaining": "185000.00"', text)
        self.assertIn('"report_date": "2026-11-10"', text)
        self.assertIn("Студия «Свет»", text)

    def test_text_report_is_readable(self):
        text = to_text(build_report(REAL, date(2026, 11, 10)))
        self.assertIn("Отчёт по оплате работ на 10.11.2026", text)
        self.assertIn("Осталось оплатить по договору           185 000,00", text)
        self.assertIn("P-3 15 000,00; P-1 85 000,00", text)
        self.assertIn("возвращён 10.09.2026 (оплачен 02.09.2026)", text)

    def test_text_report_without_contracts(self):
        self.assertIn("нет подписанных договоров", to_text(build_report(REAL, date(2026, 1, 1))))


if __name__ == "__main__":
    unittest.main()
