"""Standard-library tests for finite constraints; no model imports."""
import json
import unittest
from constrained_model import OBJECTS, allowed_next, encode_object, decode_native, validate_enum


class ConstraintTests(unittest.TestCase):
    def test_codec_and_schema(self):
        for value in OBJECTS:
            encoded = encode_object(value)
            decoded = decode_native(encoded)
            self.assertEqual(json.loads(decoded), value)
            self.assertTrue(validate_enum(decoded)['valid'])
        self.assertFalse(validate_enum('{"answer":"5","source_ids":["record-1"]}')['valid'])
        with self.assertRaises(ValueError):
            encode_object({'answer': '5'})

    def test_prefix_branch_and_rejection(self):
        paths = [[0, 3, 4, 1], [0, 3, 5, 1]]
        self.assertEqual(allowed_next([0, 3], paths), [4, 5])
        self.assertEqual(allowed_next([0, 3, 5], paths), [1])
        self.assertEqual(allowed_next([0, 9], paths), [])


if __name__ == '__main__':
    unittest.main()
