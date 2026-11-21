"""Standard-library-only checks; real dependency tests live in verify_ota.py."""
import json
from pathlib import Path
import tempfile
import unittest

from labs.edge_cloud.ota import atomic_json, canonical, cohort, digest, Store


class PortableTests(unittest.TestCase):
    def test_canonical_order(self):
        self.assertEqual(canonical({'b': 2, 'a': 1}), canonical({'a': 1, 'b': 2}))
        with self.assertRaises(ValueError):
            canonical({'bad': float('nan')})

    def test_digest(self):
        self.assertEqual(digest(b'abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad')

    def test_cohort_stable_and_extremes(self):
        self.assertFalse(cohort('device', 0))
        self.assertTrue(cohort('device', 100))
        self.assertEqual(cohort('device', 10), cohort('device', 10))
        with self.assertRaises(ValueError):
            cohort('device', 101)

    def test_atomic_file_and_pending_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'active.json'
            atomic_json(path, {'active': {'version': 2}, 'previous': {'version': 1},
                               'pending': True, 'highest': 2})
            state = Store(tmp, None).recover()
            self.assertEqual(state['active']['version'], 1)
            self.assertEqual(state['highest'], 2)
            self.assertFalse(state['pending'])
            self.assertEqual(json.loads(path.read_text()), state)

    def test_offline_never_uses_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp, None)
            self.assertEqual(store.install({}, b'', b'', None, online=False), 'offline-kept-local')
            self.assertIsNone(store.active_bytes())


if __name__ == '__main__':
    unittest.main()
