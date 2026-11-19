"""HTTP-сервис на стандартной библиотеке.

GET /report?date=ГГГГ-ММ-ДД[&format=json|text]   отчёт
GET /                                           веб-интерфейс (собранный web/ в static/)

Данные читаются из CSV на каждый запрос: поправили выгрузку — следующий
запрос уже по новым данным, перезапуск не нужен.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .data import DataError, load_dataset
from .money import parse_date
from .render import to_json, to_text
from .report import build_report

STATIC_DIR = Path(__file__).resolve().parent / "static"

# Явная таблица типов: на Windows mimetypes берёт их из реестра, и .js бывает text/plain —
# тогда браузер отказывается запускать модуль.
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

USAGE = """Отчёт по оплате работ на дату.

  GET /report?date=2026-11-10              JSON
  GET /report?date=2026-11-10&format=text  таблица для чтения глазами

Веб-интерфейс не собран: cd web && npm install && npm run build
"""


class ReportServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], data_dir: Path, static_dir: Path = STATIC_DIR):
        super().__init__(address, ReportHandler)
        self.data_dir = Path(data_dir)
        self.static_dir = Path(static_dir).resolve()


class ReportHandler(BaseHTTPRequestHandler):
    server: ReportServer

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/report":
            self._report(parse_qs(url.query))
        elif url.path == "/" and not (self.server.static_dir / "index.html").is_file():
            self._send(HTTPStatus.OK, USAGE.encode("utf-8"), "text/plain; charset=utf-8")
        elif not self._static(url.path):
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
            self._send(HTTPStatus.OK, to_text(report).encode("utf-8"), "text/plain; charset=utf-8")
        else:
            self._send(HTTPStatus.OK, to_json(report).encode("utf-8"), "application/json; charset=utf-8")

    def _static(self, path: str) -> bool:
        """Отдать файл фронта. Только из static/, только известных типов."""
        root = self.server.static_dir
        relative = unquote(path).lstrip("/") or "index.html"
        try:
            target = (root / relative).resolve()
            if root not in target.parents or not target.is_file() or target.suffix not in STATIC_TYPES:
                return False
        except (OSError, ValueError):  # нулевой байт, недопустимое имя файла
            return False
        # Файлы в assets/ с хешем в имени не меняются — их можно кешировать навсегда.
        cache = "public, max-age=31536000, immutable" if target.parent == root / "assets" else "no-cache"
        self._send(HTTPStatus.OK, target.read_bytes(), STATIC_TYPES[target.suffix], cache)
        return True

    def _error(self, status: HTTPStatus, message: str, problems: list[str] | None = None) -> None:
        body = {"error": message}
        if problems:
            body["problems"] = problems
        payload = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        self._send(status, payload, "application/json; charset=utf-8")

    def _send(self, status: HTTPStatus, payload: bytes, content_type: str, cache: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(payload)
