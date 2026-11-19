import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

from advance_report.server import ReportHandler, ReportServer

from .support import REAL_DATA, write_csv


class QuietHandler(ReportHandler):
    def log_message(self, *args) -> None:
        pass


class ServerTestCase(unittest.TestCase):
    data_dir = REAL_DATA

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.static_dir = self.root / "static"
        self.static_dir.mkdir()
        self.prepare()
        self.server = ReportServer(("127.0.0.1", 0), self.data_dir, self.static_dir)
        self.server.RequestHandlerClass = QuietHandler
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]
        self.base = f"http://127.0.0.1:{self.port}"

    def prepare(self) -> None:
        """Подготовить файлы до старта сервера."""

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def get(self, path: str):
        try:
            with urlopen(self.base + path, timeout=5) as response:
                return response.status, response.headers.get("Content-Type"), response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.headers.get("Content-Type"), error.read().decode("utf-8")

    def raw_status(self, path: str) -> int:
        """Запрос с путём как есть: urllib сам схлопывает '..'."""
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request("GET", path)
            return connection.getresponse().status
        finally:
            connection.close()


class ReportEndpointTest(ServerTestCase):
    def test_json_report(self):
        status, content_type, body = self.get("/report?date=2026-11-10")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        report = json.loads(body)
        self.assertEqual(report["report_date"], "2026-11-10")
        self.assertEqual([c["totals"]["remaining"] for c in report["contracts"]], ["185000.00", "15000.00"])
        self.assertEqual(report["totals"]["remaining"], "200000.00")

    def test_text_report(self):
        status, content_type, body = self.get("/report?date=2026-11-10&format=text")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/plain; charset=utf-8")
        self.assertIn("Договор D-1 — Студия «Свет»", body)

    def test_usage_page_without_built_frontend(self):
        status, _, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("/report?date=", body)
        self.assertIn("npm run build", body)

    def test_date_is_required(self):
        status, _, body = self.get("/report")
        self.assertEqual(status, 400)
        self.assertIn("Укажите дату", json.loads(body)["error"])

    def test_bad_date(self):
        status, _, body = self.get("/report?date=10.11.2026")
        self.assertEqual(status, 400)
        self.assertIn("ГГГГ-ММ-ДД", json.loads(body)["error"])

    def test_bad_format(self):
        status, _, _ = self.get("/report?date=2026-11-10&format=xlsx")
        self.assertEqual(status, 400)

    def test_unknown_path(self):
        status, _, _ = self.get("/reports")
        self.assertEqual(status, 404)


class StaticFilesTest(ServerTestCase):
    def prepare(self):
        (self.static_dir / "index.html").write_text("<!doctype html><title>Отчёт</title>", encoding="utf-8")
        (self.static_dir / "assets").mkdir()
        (self.static_dir / "assets" / "app-1a2b.js").write_text("console.log(1)", encoding="utf-8")
        (self.static_dir / "notes.md").write_text("не для раздачи", encoding="utf-8")
        (self.root / "secret.js").write_text("секрет", encoding="utf-8")

    def test_index_is_served_at_root(self):
        status, content_type, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/html; charset=utf-8")
        self.assertIn("<title>Отчёт</title>", body)

    def test_asset_has_js_type_and_long_cache(self):
        with urlopen(self.base + "/assets/app-1a2b.js", timeout=5) as response:
            self.assertEqual(response.headers["Content-Type"], "text/javascript; charset=utf-8")
            self.assertIn("immutable", response.headers["Cache-Control"])

    def test_api_still_works_next_to_frontend(self):
        status, _, body = self.get("/report?date=2026-11-10")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["totals"]["paid"], "390000.00")

    def test_unknown_file_types_are_not_served(self):
        self.assertEqual(self.get("/notes.md")[0], 404)

    def test_path_traversal_is_blocked(self):
        for path in ["/../secret.js", "/%2e%2e/secret.js", "/assets/..%2f..%2fsecret.js", "/..%5csecret.js", "/a%00.js"]:
            with self.subTest(path=path):
                self.assertEqual(self.raw_status(path), 404)


class BrokenDataTest(ServerTestCase):
    def prepare(self):
        self.data_dir = write_csv(
            self.root,
            contracts="D-1,Подрядчик,100.00,2026-01-01",
            payments="P-1,D-9,,Аванс,10.00,paid,2026-02-01,2026-02-01,",
        )

    def test_data_errors_are_reported_not_hidden(self):
        status, _, body = self.get("/report?date=2026-11-10")
        self.assertEqual(status, 500)
        answer = json.loads(body)
        self.assertEqual(answer["error"], "Ошибки в данных, отчёт не построен")
        self.assertEqual(answer["problems"], ["payments.csv, строка 2: договор D-9 не найден в contracts.csv"])


if __name__ == "__main__":
    unittest.main()
