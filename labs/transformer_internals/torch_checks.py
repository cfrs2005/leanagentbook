"""Optional real torch tests; run in the pinned lab environment."""
import unittest
import torch
from attention import IDS, TinyBlock, make_model, verify


class AttentionTests(unittest.TestCase):
    def setUp(self):
        self.model = make_model()
        self.ids = torch.tensor(IDS)

    def test_numerical_invariants(self):
        self.assertTrue(all(verify(self.model, self.ids)[-1].values()))

    def test_prefill_then_two_token_chunk(self):
        with torch.no_grad():
            full, _, _ = self.model(self.ids)
            _, cache, _ = self.model(self.ids[:, :4])
            tail, cache, trace = self.model(self.ids[:, 4:], cache)
        torch.testing.assert_close(full[:, 4:], tail, atol=1e-12, rtol=0)
        self.assertEqual(list(cache[0].shape), [1, 2, 6, 4])
        self.assertEqual(trace['allowed'].tolist(), [[True]*5+[False], [True]*6])

    def test_batch(self):
        ids = self.ids.repeat(2, 1)
        self.assertTrue(all(verify(self.model, ids)[-1].values()))

    def test_single_token(self):
        _, _, trace = self.model(self.ids[:, :1])
        self.assertTrue(torch.equal(trace['weights'], torch.ones(1, 2, 1, 1)))

    def test_invalid_dimensions(self):
        for width, heads in [(7, 2), (8, 3), (0, 2), (8, 0)]:
            with self.assertRaises(ValueError):
                TinyBlock(width, heads)

    def test_empty_input(self):
        with self.assertRaises(ValueError):
            self.model(torch.empty((1, 0), dtype=torch.long))


if __name__ == '__main__':
    unittest.main()
