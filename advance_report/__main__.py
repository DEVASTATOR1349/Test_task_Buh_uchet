"""Запуск: python -m advance_report [--data ПАПКА] [--host АДРЕС] [--port ПОРТ]"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .data import DataError, load_dataset
from .server import ReportServer

DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m advance_report", description="HTTP-сервис: отчёт по оплате работ на дату.")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA, help="папка с contracts.csv, works.csv, payments.csv")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    try:
        load_dataset(args.data)
    except DataError as exc:
        print("Ошибки в данных:", *exc.problems, sep="\n  ", file=sys.stderr)
        return 1

    server = ReportServer((args.host, args.port), args.data)
    host, port = server.server_address[:2]
    print(f"Данные: {args.data}", flush=True)
    print(f"Отчёт:  http://{host}:{port}/report?date=2026-11-10&format=text  (Ctrl+C — остановить)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
