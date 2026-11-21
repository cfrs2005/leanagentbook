"""Standard-library recovery tests; real Parquet test is optional."""
import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import aggregate, consume, decode, export_parquet, generate, oracle, snapshot, BASE


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.jsonl'
        generate(self.source, 250)

    def test_process_crash_windows(self):
        expected, bad = oracle(self.source)
        baseline = self.root / 'baseline.db'
        consume(self.source, baseline)
        for window, code in [('before_commit', 71), ('after_commit', 72)]:
            with self.subTest(window=window):
                database = self.root / f'{window}.db'
                result = subprocess.run([sys.executable, str(Path(__file__).with_name('pipeline.py')),
                                         '--source', str(self.source), '--database', str(database), '--crash', window])
                self.assertEqual(result.returncode, code)
                self.assertEqual(snapshot(database)[1], 3 if window == 'before_commit' else 4)
                consume(self.source, database)
                rows, offset, quarantined = snapshot(database)
                self.assertEqual(snapshot(database), snapshot(baseline))
                self.assertEqual(aggregate(rows), aggregate(expected))
                self.assertEqual(len(rows), 250)
                self.assertEqual(quarantined, bad)
                self.assertEqual(offset, len(self.source.read_text().splitlines()))
                self.assertGreater(sum(row['late'] for row in rows), 0)
                with closing(sqlite3.connect(database)) as db:
                    with db:
                        db.execute('UPDATE state SET offset=0')
                consume(self.source, database)
                self.assertEqual(snapshot(database), snapshot(baseline))

    def test_invalid_and_conflicting_payloads(self):
        valid = dict(schema_version=1, event_id='a', device='d', event_time=BASE, value=1)
        invalid = [dict(valid, value=True), dict(valid, schema_version=2), dict(valid, value=101),
                   dict(valid, event_id=''), None, []]
        for item in invalid:
            with self.assertRaises(ValueError):
                decode(json.dumps(item))
        self.source.write_text('\n'.join(json.dumps(x) for x in [valid, valid, dict(valid, value=2), *invalid]))
        database = self.root / 'state.db'
        consume(self.source, database)
        rows, offset, bad = snapshot(database)
        self.assertEqual((len(rows), offset, bad), (1, 9, 7))
        self.assertEqual(rows[0]['value'], 1)

    def test_source_mutation_rejected(self):
        database = self.root / 'state.db'
        consume(self.source, database)
        self.source.write_text(self.source.read_text() + '{}\n')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            consume(self.source, database)

    @unittest.skipUnless(importlib.util.find_spec('pyarrow'), 'install isolated requirements.txt for real Parquet')
    def test_real_parquet(self):
        database = self.root / 'state.db'
        consume(self.source, database)
        rows, _, _ = snapshot(database)
        path = self.root / 'events.parquet'
        result = export_parquet(rows, path)
        self.assertEqual(result['parquet_rows'], 250)
        self.assertEqual(result['parquet_aggregate'], aggregate(oracle(self.source)[0]))
        self.assertEqual(path.read_bytes()[:4], b'PAR1')
        self.assertEqual(path.read_bytes()[-4:], b'PAR1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
