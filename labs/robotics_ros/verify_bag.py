"""Opt-in integration checks, excluded from default test_*.py discovery."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from bag_lab import generate, analyze, dependencies
from core import BASE, validate_manifest


class BagTests(unittest.TestCase):
    def test_real_bag_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate(root)
            report = analyze(root)
            self.assertEqual(sum(x['count'] for x in report['topics'].values()), 440)
            self.assertEqual(report['topics']['/imu']['missing_sequences'], list(range(100, 110)))
            self.assertEqual(report['topics']['/imu']['max_gap_ms'], 220)
            valid = [r['true_error_ns'] for r in report['alignment_after'] if r['imu_seq'] is not None]
            self.assertEqual(valid, [0] * 38)
            self.assertEqual([r['camera_seq'] for r in report['alignment_after'] if r['imu_seq'] is None], [20, 21])
            self.assertTrue(any((r['true_error_ns'] or 0) >= 60_000_000 for r in report['alignment_before']))
            self.assertEqual(report['event']['anomalous_motor_sequences'], list(range(40, 48)))
            self.assertEqual(report['event']['context_rows'], 2)
            db = next((root / 'source_bag').glob('*.db3'))
            self.assertEqual(db.read_bytes()[:16], b'SQLite format 3\x00')
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('SELECT count(*) FROM messages').fetchone()[0], 440)
            # A fresh reader can deserialize every extracted message without the source bag.
            Reader, _, store = dependencies()
            with Reader(root / 'source_bag') as reader:
                expected = {(connection.topic, timestamp): bytes(raw)
                            for connection, timestamp, raw in reader.messages()
                            if BASE + 1_800_000_000 <= timestamp < BASE + 2_600_000_000
                            or connection.topic == '/context'}
            (root / 'source_bag').rename(root / 'hidden_source')
            with Reader(root / 'event_bag') as reader:
                messages = list(reader.messages())
                self.assertEqual(len(messages), 82)
                self.assertEqual({(c.topic, t): bytes(raw) for c, t, raw in messages}, expected)
                for connection, _, raw in messages:
                    store.deserialize_cdr(raw, connection.msgtype)
            manifest = json.loads((root / 'manifest.json').read_text())
            manifest['bag_version'] = 99
            with self.assertRaises(ValueError):
                validate_manifest(manifest)
            metadata = root / 'hidden_source' / 'metadata.yaml'
            metadata.write_text(metadata.read_text().replace('version: 8', 'version: 999'))
            with self.assertRaises(Exception) as failure:
                with Reader(root / 'hidden_source'):
                    pass
            self.assertIn('version', str(failure.exception).lower())


if __name__ == '__main__':
    unittest.main()
