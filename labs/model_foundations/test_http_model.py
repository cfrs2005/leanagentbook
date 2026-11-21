"""Dependency-free contracts for the optional real-model HTTP path."""
import unittest
from http_model import check_generated, validate_request


class ContractTests(unittest.TestCase):
    def test_exact_json_integer(self):
        for raw in ['5', '5.0', '-1', '2e1']:
            self.assertTrue(check_generated(raw, 'integer')['valid'])
        for raw in ['true', '"5"', '5 apples', 'NaN', '1.5', 'null', '{}']:
            self.assertFalse(check_generated(raw, 'integer')['valid'])

    def test_no_json_repair(self):
        self.assertFalse(check_generated('```json\n5\n```', 'integer')['valid'])
        self.assertFalse(check_generated('{"answer":"42"}', 'record')['valid'])
        self.assertTrue(check_generated('{"answer":"99","source_ids":[]}', 'record')['valid'])

    def test_invalid_request_rejected(self):
        request = {'prompt': 'hello', 'temperature': 0.8, 'seed': 7, 'max_new_tokens': 64}
        self.assertEqual(validate_request(request), request)
        for key, value in [('temperature', 0), ('temperature', float('nan')), ('seed', True),
                           ('max_new_tokens', 65), ('prompt', '')]:
            with self.assertRaises(ValueError):
                validate_request({**request, key: value})


if __name__ == '__main__':
    unittest.main()
