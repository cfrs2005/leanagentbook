"""Dependency-enabled Ed25519 and real ONNX health/recovery acceptance tests."""
import argparse
import json
from pathlib import Path
import tempfile
import unittest

from ota import Store, canonical, digest

MODEL_DIR = None


class SignedUpdateTests(unittest.TestCase):
    def setUp(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.key = Ed25519PrivateKey.generate()
        self.store = Store(self.tmp.name, self.key.public_key())
        self.float = (MODEL_DIR / 'float.onnx').read_bytes()
        self.quantized = (MODEL_DIR / 'int8.onnx').read_bytes()
        self.assertEqual(self.install(1, self.float), 'activated')

    def health(self, path):
        import numpy as np
        import onnxruntime as ort
        session = ort.InferenceSession(str(path), providers=['CPUExecutionProvider'])
        if session.get_inputs()[0].shape != [1, 16] or session.get_outputs()[0].shape != [1, 3]:
            return False
        data = np.load(MODEL_DIR / 'data.npz')
        # Golden examples from validation, not the test set.
        x, y = data['x_validation'][:32], data['y_validation'][:32]
        values = np.vstack([session.run(['logits'], {'features': row[None, :]})[0] for row in x])
        return np.isfinite(values).all() and np.mean(values.argmax(1) == y) >= 0.80

    def envelope(self, version, payload, **changes):
        metadata = {'version': version, 'sha256': digest(payload), 'size': len(payload),
                    'contract': 'features16-logits3-v1', 'runtime': 'onnxruntime-cpu', 'percent': 100}
        metadata.update(changes)
        return metadata, self.key.sign(canonical(metadata))

    def install(self, version, payload, **kwargs):
        metadata, signature = self.envelope(version, payload)
        return self.store.install(metadata, signature, payload, self.health, **kwargs)

    def unchanged(self):
        self.assertEqual(self.store.active_bytes(), self.float)

    def test_real_quantized_model_activation(self):
        self.assertEqual(self.install(2, self.quantized), 'activated')
        self.assertEqual(self.store.active_bytes(), self.quantized)

    def test_damaged_signature(self):
        from cryptography.exceptions import InvalidSignature
        metadata, signature = self.envelope(2, self.quantized)
        with self.assertRaises(InvalidSignature):
            self.store.install(metadata, bytes([signature[0] ^ 1])+signature[1:], self.quantized, self.health)
        self.unchanged()

    def test_metadata_tamper(self):
        from cryptography.exceptions import InvalidSignature
        metadata, signature = self.envelope(2, self.quantized)
        metadata['percent'] = 50
        with self.assertRaises(InvalidSignature):
            self.store.install(metadata, signature, self.quantized, self.health)
        self.unchanged()

    def test_payload_tamper(self):
        metadata, signature = self.envelope(2, self.quantized)
        with self.assertRaisesRegex(ValueError, 'Corrupt'):
            self.store.install(metadata, signature, self.quantized+b'x', self.health)
        self.unchanged()

    def test_signed_incompatible_contract(self):
        metadata, signature = self.envelope(2, self.quantized, contract='wrong-v2')
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            self.store.install(metadata, signature, self.quantized, self.health)
        self.unchanged()

    def test_signed_wrong_runtime(self):
        metadata, signature = self.envelope(2, self.quantized, runtime='rknn')
        with self.assertRaisesRegex(ValueError, 'Incompatible'):
            self.store.install(metadata, signature, self.quantized, self.health)
        self.unchanged()

    def test_offline_uses_existing_inference(self):
        self.assertEqual(self.install(2, self.quantized, online=False), 'offline-kept-local')
        self.unchanged()
        self.assertTrue(self.health(Path(self.tmp.name)/(digest(self.float)+'.onnx')))

    def test_download_interruption(self):
        with self.assertRaises(InterruptedError):
            self.install(2, self.quantized, crash='download')
        self.unchanged()
        self.assertEqual(self.install(2, self.quantized), 'activated')

    def test_restart_after_activation(self):
        with self.assertRaises(InterruptedError):
            self.install(2, self.quantized, crash='activate')
        restarted = Store(self.tmp.name, self.key.public_key())
        restarted.recover()
        self.unchanged()
        self.assertEqual(restarted.state()['highest'], 2)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.install(2, self.quantized)

    def test_real_health_failure_rolls_back(self):
        self.assertEqual(self.install(2, b'not an ONNX protobuf'), 'rolled-back')
        self.unchanged()
        self.assertTrue(self.health(Path(self.tmp.name)/(digest(self.float)+'.onnx')))

    def test_stale_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Stale'):
            self.install(1, self.float)
        self.unchanged()

    def test_canary_excludes_device(self):
        metadata, signature = self.envelope(2, self.quantized, percent=0)
        self.assertEqual(self.store.install(metadata, signature, self.quantized, self.health), 'outside-canary')
        self.unchanged()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    MODEL_DIR = args.models
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(SignedUpdateTests)
    names = [test.id() for test in suite]
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    report = {'tests': names, 'run': result.testsRun, 'failures': len(result.failures),
              'errors': len(result.errors), 'successful': result.wasSuccessful(),
              'signature': 'Ed25519 ephemeral teaching keys; private key never saved',
              'health': 'real ORT CPU inference on 32 validation samples',
              'limits': 'single process; exception injection, not physical power-cut testing'}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x') as stream:
        json.dump(report, stream, indent=2)
    raise SystemExit(0 if result.wasSuccessful() else 1)
