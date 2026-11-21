"""Exercise boundary behavior independently of any provider or network."""
import contextlib
import io
import json
import unittest

from foundations import FIXTURES, check_budget, main, validate_output


class BudgetTests(unittest.TestCase):
    def test_exact_boundary(self):
        self.assertEqual(check_budget(80, 20, 100), 0)

    def test_one_unit_over(self):
        with self.assertRaisesRegex(ValueError, "exceeded"):
            check_budget(81, 20, 100)

    def test_unused_capacity(self):
        self.assertEqual(check_budget(70, 20, 100), 10)

    def test_invalid_budget_types_and_ranges(self):
        for args in [(-1, 20, 100), (80, -1, 100), (0, 0, 0),
                     (True, 20, 100), (80, 2.5, 100), (80, 20, -1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                check_budget(*args)

    def test_zero_input_and_reserve(self):
        self.assertEqual(check_budget(0, 0, 1), 1)


class OutputTests(unittest.TestCase):
    def test_valid_unicode(self):
        self.assertIn("42", validate_output(FIXTURES["valid"])["answer"])

    def test_wrong_fact_also_passes_structure(self):
        self.assertIn("99", validate_output(FIXTURES["wrong-fact"])["answer"])

    def test_wrong_types(self):
        for raw in ['{"answer":true,"source_ids":[]}',
                    '{"answer":"x","source_ids":"id"}',
                    '{"answer":"x","source_ids":[1]}', '[]', 'null']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_output(raw)

    def test_missing_and_extra_fields(self):
        for raw in ['{"answer":"x"}', '{"answer":"x","source_ids":[],"ok":true}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_output(raw)

    def test_empty_answer_rejected(self):
        with self.assertRaises(ValueError):
            validate_output('{"answer":"","source_ids":[]}')

    def test_empty_sources_allowed_by_schema(self):
        self.assertEqual(validate_output('{"answer":"x","source_ids":[]}')["source_ids"], [])

    def test_truncation_and_markdown_rejected(self):
        for raw in [FIXTURES["truncated"], '```json\n{}\n```']:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                validate_output(raw)

    def test_duplicate_key_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_output('{"answer":"x","answer":"y","source_ids":[]}')

    def test_nonstandard_constants_rejected(self):
        for constant in ["NaN", "Infinity", "-Infinity"]:
            with self.subTest(constant=constant), self.assertRaises(ValueError):
                validate_output('{"answer":' + constant + ',"source_ids":[]}')

    def test_oversized_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            validate_output(" " * 4097)


class CliTests(unittest.TestCase):
    def run_cli(self, args):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(args)
        return code, json.loads(stream.getvalue())

    def test_overflow_stops_before_fixture(self):
        code, report = self.run_cli(["--input-units", "81"])
        self.assertEqual(code, 1)
        self.assertFalse(report["fixture_read"])
        self.assertNotIn("output", report)

    def test_all_fixtures(self):
        for scenario, expected in [("valid", 0), ("wrong-fact", 0),
                                   ("invalid", 1), ("truncated", 1)]:
            with self.subTest(scenario=scenario):
                code, report = self.run_cli(["--scenario", scenario])
                self.assertEqual(code, expected)
                self.assertEqual(report["fact_check"], "not_performed")


if __name__ == "__main__":
    unittest.main()
