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

    def test_date_helpers_cover_month_lengths_and_range_validation(self):
        from gui.main_window import _get_month_days, _parse_date_range

        self.assertEqual(len(_get_month_days(2025, 2)), 28)
        self.assertEqual(len(_get_month_days(2024, 2)), 29)
        self.assertEqual(len(_get_month_days(2025, 4)), 30)
        self.assertEqual(len(_get_month_days(2025, 1)), 31)
        self.assertEqual(_get_month_days(2025, 2)[-1], 28)
        self.assertEqual(
            _parse_date_range("2025-12-31", "2026-01-01")[0].strftime("%Y-%m-%d"),
            "2025-12-31",
        )
        with self.assertRaises(ValueError):
            _parse_date_range("2025-02-30", "2025-03-01")
        with self.assertRaisesRegex(ValueError, "不能晚于"):
            _parse_date_range("2026-01-02", "2026-01-01")

    def test_calendar_weekday_uses_monday_based_index(self):
        import calendar

        self.assertEqual(calendar.monthrange(2024, 1)[0], 0)
        self.assertEqual(calendar.monthrange(2024, 9)[0], 6)

    def test_city_table_configs_are_registered_and_complete(self):
        from gui.widgets import TableConfig

        expected = {
            "重要场景地市-天": ("appdbv3.a_overview_ispm_lte_city_d", "重要场景-地市天", 84),
            "5G容量报表-地市级": ("appdbv3.a_adhoc_capacity_nr_city", "5G容量报表 - 地市级", 29),
            "4G小区性能KPI报表-地市": ("appdbv3.a_common_pm_lte", "公共_4G小区性能KPI报表_小区", 10),
            "5G小区性能KPI报表-地市": ("appdbv3.a_common_pm_sacu", "公共_5G小区性能KPI报表_小区", 8),
        }
        for name, (source_table, fieldtype, field_count) in expected.items():
            config = TableConfig.get_table_config(name)
            self.assertIsNotNone(config)
            self.assertEqual(config["table_name"], source_table)
            self.assertEqual(config["table_key"], fieldtype)
            self.assertEqual(config["fieldtype"], fieldtype)
            self.assertEqual(len(config["fields"]), field_count)
            fields = [item["feild"] for item in config["fields"]]
            self.assertEqual(len(fields), len(set(fields)))
            self.assertIn("starttime", fields)
            self.assertIn("city", fields)
            self.assertEqual(config["indexcount"], 0)
            self.assertEqual(config["tableParams"], {
                "supporteddimension": config["tableParams"]["supporteddimension"],
                "supportedtimedimension": config["tableParams"]["supportedtimedimension"],
            })

        city_kpi_fields = {
            item["feild"] for item in TableConfig.get_table_config(
                "5G小区性能KPI报表-地市"
            )["fields"]
        }
        self.assertNotIn("endtime", city_kpi_fields)

    def test_city_table_payload_preserves_fields_and_conditions(self):
        from core.payload_builder_mixin import PayloadBuilderMixin
        from gui.widgets import TableConfig

        class Builder(PayloadBuilderMixin):
            pass

        config = TableConfig.get_table_config("5G小区性能KPI报表-地市")
        payload = Builder().build_payload_from_config(
            config["table_key"], config["fieldtype"],
            [
                {"field": "starttime", "operator": ">=", "value": "2026-08-18"},
                {"field": "starttime", "operator": "<=", "value": "2026-08-18"},
                {"field": "city", "operator": "in", "value": "广州,深圳"},
            ],
            config["api_type"], dimension_override=config["dimension"],
            fields_override=config["fields"], table_name=config["table_name"],
            table_params=config["tableParams"], indexcount=config["indexcount"],
        )
        columns = [column["data"] for column in payload["columns"]]
        result = [item["feild"] for item in payload["result"]["result"]]
        self.assertEqual(columns, result)
        self.assertEqual(payload["indexcount"], config["indexcount"])
        self.assertEqual(payload["result"]["tableParams"], config["tableParams"])
        self.assertEqual(payload["geographicdimension"], config["dimension"]["geographicdimension"])
        self.assertEqual(payload["cityField"], "city")
        self.assertEqual(payload["where"][-1]["feild"], "city")
        self.assertEqual(payload["where"][-1]["val"], "广州,深圳")
        self.assertEqual(payload["where"][1]["val"], "2026-08-18 23:59:59")

    def test_vonr_warning_payload_contains_radio_call_metrics_once(self):
        from gui.field_configs import VONR_WARNING_FIELDS
        from gui.payload_templates import get_vonr_warning_payload

        expected = {
            "vonr_local_radio_single_voice_call": "VONR_语音本端无线单通通话数",
            "vonr_local_radio_dx_call": "VONR_语音本端无线断续通话数",
            "vonr_ans_voice_call": "VONR_语音通话总数",
            "vonr_local_radio_dtdx_rate": "VONR_单通断续次数占比",
        }
        payload = get_vonr_warning_payload("2026-08-18", "2026-08-18", "阳江")
        columns = [column["data"] for column in payload["columns"]]
        result = {item["feild"]: item for item in payload["result"]["result"]}

        self.assertEqual(len(columns), len(set(columns)))
        self.assertEqual(set(columns), set(result))
        self.assertEqual(
            {field: result[field]["feildName"] for field in expected}, expected
        )

        config = {item["feild"]: item for item in VONR_WARNING_FIELDS}
        self.assertEqual(
            {field: config[field]["feildName"] for field in expected}, expected
        )
        for field in expected:
            self.assertEqual(config[field]["datatype"], "character varying")
            self.assertEqual(config[field]["columntype"], "1")
            self.assertEqual(config[field]["table"], "csem.f_nk_vonr_keykpi_cell_d")


if __name__ == "__main__":
    unittest.main()
