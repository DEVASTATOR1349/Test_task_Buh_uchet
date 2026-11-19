import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from advance_report.data import DataError, load_dataset, natural_key
from advance_report.money import format_money, parse_date, parse_money

from .support import HEADERS, REAL_DATA, make_dataset

CONTRACT = "D-1,Подрядчик,100.00,2026-01-01"


class MoneyTest(unittest.TestCase):
    def test_parse_money_is_exact_decimal(self):
        self.assertEqual(parse_money("600000.00"), Decimal("600000.00"))
        self.assertEqual(parse_money("100.5"), Decimal("100.50"))
        self.assertEqual(parse_money("7"), Decimal("7.00"))
        self.assertEqual(str(parse_money("0.1") + parse_money("0.2")), "0.30")

    def test_parse_money_rejects_ambiguous_input(self):
        for text in ["", "-1.00", "1,50", "1.005", "1e3", " 1.00", "1 000.00", "nan"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_money(text)

    def test_format_money(self):
        self.assertEqual(format_money(Decimal("185000.00")), "185 000,00")
        self.assertEqual(format_money(Decimal("0.00")), "0,00")
        self.assertEqual(format_money(Decimal("1234567.05")), "1 234 567,05")
        self.assertEqual(format_money(Decimal("-5000.00")), "-5 000,00")

    def test_parse_date_is_strict(self):
        self.assertEqual(parse_date("2026-11-10"), date(2026, 11, 10))
        for text in ["10.11.2026", "2026-11-31", "2026-1-5", "20261110", ""]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_date(text)

    def test_natural_key(self):
        self.assertEqual(sorted(["W-10", "W-2", "W-1"], key=natural_key), ["W-1", "W-2", "W-10"])


class LoadRealDataTest(unittest.TestCase):
    def test_real_data_loads(self):
        data = load_dataset(REAL_DATA)
        self.assertEqual(sorted(data.contracts), ["D-1", "D-2"])
        self.assertEqual(len(data.works), 9)
        self.assertEqual(len(data.payments), 8)
        self.assertEqual(data.contracts["D-2"].contractor, "Иван Петров, дизайнер")
        self.assertEqual(data.payments["P-3"].work_id, "W-14")
        self.assertIsNone(data.payments["P-1"].work_id)
        self.assertEqual(data.payments["P-2"].refunded_at, date(2026, 9, 10))

    def test_utf8_bom_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "contracts.csv").write_text(f"{HEADERS['contracts.csv']}\n{CONTRACT}\n", encoding="utf-8-sig")
            (directory / "works.csv").write_text(HEADERS["works.csv"] + "\n", encoding="utf-8")
            (directory / "payments.csv").write_text(HEADERS["payments.csv"] + "\n", encoding="utf-8")
            self.assertIn("D-1", load_dataset(directory).contracts)


class ValidationTest(unittest.TestCase):
    def assertProblem(self, fragment: str, **csv):
        csv.setdefault("contracts", CONTRACT)
        with self.assertRaises(DataError) as caught:
            make_dataset(**csv)
        joined = "\n".join(caught.exception.problems)
        self.assertIn(fragment, joined)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(DataError) as caught:
            load_dataset(Path(tmp))
        self.assertIn("contracts.csv: файл не найден", caught.exception.problems[0])

    def test_missing_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "contracts.csv").write_text("contract_id,amount\nD-1,1.00\n", encoding="utf-8")
            (directory / "works.csv").write_text(HEADERS["works.csv"] + "\n", encoding="utf-8")
            (directory / "payments.csv").write_text(HEADERS["payments.csv"] + "\n", encoding="utf-8")
            with self.assertRaises(DataError) as caught:
                load_dataset(directory)
        self.assertIn("нет колонок contractor, signed_at", caught.exception.problems[0])

    def test_bad_amount_points_to_row(self):
        self.assertProblem("contracts.csv, строка 2: amount: сумма '100,00'", contracts='D-1,Подрядчик,"100,00",2026-01-01')

    def test_duplicate_id(self):
        self.assertProblem("номер D-1 повторяется", contracts=f"{CONTRACT}\n{CONTRACT}")

    def test_work_with_unknown_contract(self):
        self.assertProblem("договор D-9 не найден", works="W-1,D-9,Работа,10.00,planned,,")

    def test_unknown_work_status(self):
        self.assertProblem("неизвестный статус 'accepted'", works="W-1,D-1,Работа,10.00,accepted,2026-02-01,")

    def test_done_work_needs_completion_date(self):
        self.assertProblem("статус done, но не заполнено completed_at", works="W-1,D-1,Работа,10.00,done,,")

    def test_planned_work_must_not_have_dates(self):
        self.assertProblem("статус planned, но заполнено cancelled_at", works="W-1,D-1,Работа,10.00,planned,,2026-02-01")

    def test_payment_bound_to_work_of_other_contract(self):
        self.assertProblem(
            "работа W-1 относится к договору D-2, а платёж — к D-1",
            contracts=f"{CONTRACT}\nD-2,Другой,10.00,2026-01-01",
            works="W-1,D-2,Работа,10.00,planned,,",
            payments="P-1,D-1,W-1,Оплата,10.00,paid,2026-02-01,2026-02-01,",
        )

    def test_payment_bound_to_unknown_work(self):
        self.assertProblem("работа W-7 не найдена", payments="P-1,D-1,W-7,Оплата,10.00,paid,2026-02-01,2026-02-01,")

    def test_refunded_payment_needs_both_dates(self):
        self.assertProblem(
            "статус refunded, но не заполнено refunded_at",
            payments="P-1,D-1,,Аванс,10.00,refunded,2026-02-01,2026-02-01,",
        )

    def test_refund_before_payment(self):
        self.assertProblem(
            "refunded_at раньше paid_at",
            payments="P-1,D-1,,Аванс,10.00,refunded,2026-02-01,2026-02-05,2026-02-03",
        )

    def test_queued_payment_must_not_have_paid_date(self):
        self.assertProblem("статус queued, но заполнено paid_at", payments="P-1,D-1,,Аванс,10.00,queued,2026-02-01,2026-02-01,")

    def test_zero_payment(self):
        self.assertProblem("сумма платежа 0", payments="P-1,D-1,,Аванс,0.00,paid,2026-02-01,2026-02-01,")

    def test_all_problems_are_reported_at_once(self):
        with self.assertRaises(DataError) as caught:
            make_dataset(
                contracts=CONTRACT,
                works="W-1,D-9,Работа,10.00,planned,,\nW-2,D-1,Работа,abc,done,,",
            )
        self.assertEqual(len(caught.exception.problems), 3)


if __name__ == "__main__":
    unittest.main()
