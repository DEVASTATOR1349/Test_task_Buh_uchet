"""HTTP-сервис на стандартной библиотеке.

GET /report?date=ГГГГ-ММ-ДД[&format=json|text]

Данные читаются из CSV на каждый запрос: поправили выгрузку — следующий
запрос уже по новым данным, перезапуск не нужен.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .data import DataError, load_dataset
from .money import parse_date
from .render import to_json, to_text
from .report import build_report

USAGE = """Отчёт по оплате работ на дату.

  GET /report?date=2026-11-10              JSON
  GET /report?date=2026-11-10&format=text  таблица для чтения глазами
"""


class ReportServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], data_dir: Path):
        super().__init__(address, ReportHandler)
        self.data_dir = Path(data_dir)


class ReportHandler(BaseHTTPRequestHandler):
    server: ReportServer

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/":
            self._send(HTTPStatus.OK, USAGE, "text/plain")
        elif url.path == "/report":
            self._report(parse_qs(url.query))
        else:
            self._error(HTTPStatus.NOT_FOUND, f"Нет такого адреса: {url.path}. Отчёт — /report?date=ГГГГ-ММ-ДД")

    def _report(self, params: dict[str, list[str]]) -> None:
        if "date" not in params:
            self._error(HTTPStatus.BAD_REQUEST, "Укажите дату отчёта: /report?date=ГГГГ-ММ-ДД")
            return
        try:
            day = parse_date(params["date"][0])
        except ValueError as exc:
            self._error(HTTPStatus.BAD_REQUEST, f"Неверная {exc}")
            return
        output = params.get("format", ["json"])[0]
        if output not in ("json", "text"):
            self._error(HTTPStatus.BAD_REQUEST, "format: json или text")
            return
        try:
            data = load_dataset(self.server.data_dir)
        except DataError as exc:
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Ошибки в данных, отчёт не построен", exc.problems)
            return
        report = build_report(data, day)
        if output == "text":
            self._send(HTTPStatus.OK, to_text(report), "text/plain")
        else:
            self._send(HTTPStatus.OK, to_json(report), "application/json")

    def _error(self, status: HTTPStatus, message: str, problems: list[str] | None = None) -> None:
        body = {"error": message}
        if problems:
            body["problems"] = problems
        self._send(status, json.dumps(body, ensure_ascii=False, indent=2), "application/json")

    def _send(self, status: HTTPStatus, body: str, content_type: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
