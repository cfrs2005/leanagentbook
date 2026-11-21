"""Behavior checks against hand-written expectations, using synthetic inputs."""
import json
from pathlib import Path
import tempfile
import unittest

from detector import analyze

DATA = Path(__file__).parent / "data"
HEADER = "time_s,motor_current_a,vibration_mm_s\n"


class DetectorTests(unittest.TestCase):
    def from_text(self, text):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.csv"
            path.write_text(text, encoding="utf-8")
            return analyze(path)

    def test_normal(self):
        report = analyze(DATA / "normal.csv")
        self.assertEqual([e["status"] for e in report["events"]], ["normal", "normal"])
        self.assertFalse(report["automatic_control"])
        self.assertFalse(report["root_cause_confirmed"])

    def test_abnormal_evidence(self):
        report = analyze(DATA / "abnormal.csv")
        event = report["events"][1]
        self.assertEqual(event["status"], "abnormal")
        self.assertEqual(event["evidence"][0]["threshold_hits"],
                         [{"time_s": 6, "value": 9.0}, {"time_s": 7, "value": 10.0}])
        self.assertFalse(event["hypotheses"][0]["confirmed"])

    def test_missing_cells_and_rows(self):
        event = analyze(DATA / "missing.csv")["events"][0]
        self.assertEqual(event["status"], "insufficient_data")
        self.assertIn({"time_s": 1, "field": "motor_current_a"}, event["missing"])
        self.assertIn({"time_s": 2, "field": "vibration_mm_s"}, event["missing"])
        self.assertEqual(event["hypotheses"], [])

    def test_threshold_is_inclusive_and_requires_two_hits(self):
        report = self.from_text(HEADER + "0,8,1\n1,8,1\n2,3,1\n3,3,1\n4,3,1\n")
        self.assertEqual(report["events"][0]["status"], "abnormal")
        report = self.from_text(HEADER + "0,8,1\n1,3,1\n2,3,1\n3,3,1\n4,3,1\n")
        self.assertEqual(report["events"][0]["status"], "normal")

    def test_missing_does_not_erase_anomaly(self):
        event = self.from_text(HEADER + "0,9,1\n1,10,1\n")["events"][0]
        self.assertEqual(event["status"], "abnormal")
        self.assertTrue(event["missing"])
        self.assertEqual(len(event["uncertainty"]), 3)

    def test_full_gap_and_partial_tail(self):
        events = self.from_text(HEADER + "0,3,1\n10,3,1\n")["events"]
        self.assertEqual(len(events), 3)
        self.assertEqual(len(events[1]["missing"]), 10)
        self.assertEqual(events[2]["status"], "insufficient_data")

    def test_reject_invalid_values_and_order(self):
        for body in ["0,nan,1\n", "0,inf,1\n", "0,-1,1\n", "0,x,1\n",
                     "0,1,1\n0,1,1\n", "2,1,1\n1,1,1\n", "3600,1,1\n",
                     "-1,1,1\n", "0.5,1,1\n", "0,1\n", "0,1,1,1\n"]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                self.from_text(HEADER + body)

    def test_reject_empty_or_wrong_header(self):
        for text in ["", HEADER, "time,current,vibration\n0,1,1\n"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.from_text(text)

    def test_reproducible_strict_json(self):
        report = analyze(DATA / "abnormal.csv")
        self.assertEqual(report, analyze(DATA / "abnormal.csv"))
        self.assertEqual(json.loads(json.dumps(report, allow_nan=False)), report)

    def test_input_size_limit(self):
        with self.assertRaisesRegex(ValueError, "1 MiB"):
            self.from_text("x" * (1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main()
