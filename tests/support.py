from __future__ import annotations

import tempfile
from decimal import Decimal
from pathlib import Path

from advance_report.data import Dataset, load_dataset

REAL_DATA = Path(__file__).resolve().parent.parent / "data"

HEADERS = {
    "contracts.csv": "contract_id,contractor,amount,signed_at",
    "works.csv": "work_id,contract_id,title,price,status,completed_at,cancelled_at",
    "payments.csv": "payment_id,contract_id,work_id,purpose,amount,status,created_at,paid_at,refunded_at",
}


def write_csv(directory: Path, contracts: str, works: str = "", payments: str = "") -> Path:
    """Пишет три CSV во временную папку. Строки данных — без заголовков."""
    bodies = {"contracts.csv": contracts, "works.csv": works, "payments.csv": payments}
    for name, body in bodies.items():
        lines = [HEADERS[name], *(line.strip() for line in body.strip().splitlines() if line.strip())]
        (directory / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


def make_dataset(contracts: str, works: str = "", payments: str = "") -> Dataset:
    with tempfile.TemporaryDirectory() as tmp:
        return load_dataset(write_csv(Path(tmp), contracts, works, payments))


def rub(text: str) -> Decimal:
    return Decimal(text)
