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
        self.server = ReportServer(("127.0.0.1", 0), self.data_dir)
        self.server.RequestHandlerClass = QuietHandler
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def get(self, path: str):
        try:
            with urlopen(self.base + path, timeout=5) as response:
                return response.status, response.headers.get("Content-Type"), response.read().decode("utf-8")
        except HTTPError as error:
            return error.code, error.headers.get("Content-Type"), error.read().decode("utf-8")


class ReportEndpointTest(ServerTestCase):
    def test_json_report(self):
        status, content_type, body = self.get("/report?date=2026-11-10")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        report = json.loads(body)
        self.assertEqual(report["report_date"], "2026-11-10")
        self.assertEqual([c["totals"]["remaining"] for c in report["contracts"]], ["185000.00", "15000.00"])

    def test_text_report(self):
        status, content_type, body = self.get("/report?date=2026-11-10&format=text")
        self.assertEqual(status, 200)
        self.assertEqual(content_type, "text/plain; charset=utf-8")
        self.assertIn("Договор D-1 — Студия «Свет»", body)

    def test_usage_page(self):
        status, _, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn("/report?date=", body)

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


class BrokenDataTest(ServerTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = write_csv(
            Path(self.tmp.name),
            contracts="D-1,Подрядчик,100.00,2026-01-01",
            payments="P-1,D-9,,Аванс,10.00,paid,2026-02-01,2026-02-01,",
        )
        super().setUp()

    def tearDown(self):
        super().tearDown()
        self.tmp.cleanup()

    def test_data_errors_are_reported_not_hidden(self):
        status, _, body = self.get("/report?date=2026-11-10")
        self.assertEqual(status, 500)
        answer = json.loads(body)
        self.assertEqual(answer["error"], "Ошибки в данных, отчёт не построен")
        self.assertEqual(answer["problems"], ["payments.csv, строка 2: договор D-9 не найден в contracts.csv"])


if __name__ == "__main__":
    unittest.main()
