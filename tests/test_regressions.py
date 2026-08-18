import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests
from openpyxl import load_workbook


class RegressionTests(unittest.TestCase):
    def test_core_workers_imports_independently(self):
        import core.workers

        self.assertTrue(hasattr(core.workers, "QueryWorker"))

    def test_formatted_export_handles_non_finite_values(self):
        import core.export as export

        with tempfile.TemporaryDirectory() as output_dir:
            with patch.object(export, "OUTPUT_DIR", output_dir):
                path = export.export_with_format(
                    pd.DataFrame({"value": [1, float("nan"), float("inf"), float("-inf")]}),
                    "formatted.xlsx",
                )

            self.assertIsNotNone(path)
            self.assertGreater(os.path.getsize(path), 0)
            load_workbook(path)

    def test_streaming_export_preserves_existing_file_on_failure(self):
        import core.export as export

        with tempfile.TemporaryDirectory() as output_dir:
            path = Path(output_dir) / "stream.xlsx"
            path.write_bytes(b"existing")
            original = export.normalize_excel_rows
            with patch.object(export, "normalize_excel_rows", side_effect=RuntimeError("write failure")):
                self.assertFalse(
                    export.export_dataframe_streaming(
                        pd.DataFrame({"value": [1]}), str(path)
                    )
                )
            self.assertEqual(path.read_bytes(), b"existing")
            export.normalize_excel_rows = original

    def test_batch_failure_does_not_return_partial_rows(self):
        from core.query import JXCXQuery

        class Query(JXCXQuery):
            def is_cancelled(self):
                return False

        query = Query(None)
        query._fetch_data = lambda payload, timeout=None: (
            [] if payload["start"] == 50000 else [{"row": payload["start"]}]
        )
        with self.assertRaises(Exception):
            query._fetch_by_loop({}, 100001)

    def test_worker_calls_failure_callback(self):
        from core.workers import QueryWorker, TableConfig

        class Variable:
            def __init__(self, value):
                self.value = value

            def get(self):
                return self.value

        class Query:
            enabled = False

            def is_cancelled(self):
                return False

            def enter_jxcx(self):
                return True

        def failing_config(cls, name):
            return {"payload_func": lambda *args: (_ for _ in ()).throw(RuntimeError("failure"))}

        complete = []
        failed = []
        worker = QueryWorker(
            requests.Session(), Query(), lambda *args: None, lambda *args: None,
            lambda delay, callback, *args: callback(*args), Variable("hardcode"),
            Variable(False), {}, Variable(False), Variable(False), Variable(False),
            Variable(False),
        )
        with patch.object(TableConfig, "get_table_config", classmethod(failing_config)):
            worker.query_worker(
                ["test"], "2026-01-01", "2026-01-02", "",
                on_complete=lambda: complete.append(True),
                on_failed=lambda: failed.append(True),
            )

        self.assertEqual(complete, [])
        self.assertEqual(failed, [True])

    def test_thread_query_copies_session_settings(self):
        from core.workers import QueryWorker

        session = requests.Session()
        session.verify = "/tmp/test-ca.pem"
        session.trust_env = False

        class Query:
            enabled = True

            def is_cancelled(self):
                return False

        worker = QueryWorker(
            session, Query(), lambda *args: None, lambda *args: None,
            lambda *args: None, None, None, {}, None, None, None, None,
        )
        thread_query = worker._make_thread_query()
        self.assertEqual(thread_query.sess.verify, session.verify)
        self.assertEqual(thread_query.sess.trust_env, session.trust_env)


if __name__ == "__main__":
    unittest.main()
