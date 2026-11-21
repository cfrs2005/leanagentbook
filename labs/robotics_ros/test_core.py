"""Standard-library tests; deliberately never import rosbags."""
import unittest
from core import align, missing_sequences, thin, validate_manifest


class CoreTests(unittest.TestCase):
    def test_missing(self):
        self.assertEqual(missing_sequences([{'seq': 0}, {'seq': 2}], 3), [1])

    def test_incompatible(self):
        for manifest in ({}, {'schema': 1, 'typestore': 'ROS1_NOETIC', 'bag_version': 8},
                         {'schema': 1, 'typestore': 'ROS2_HUMBLE', 'bag_version': 99}):
            with self.assertRaises(ValueError):
                validate_manifest(manifest)

    def test_alignment_gap(self):
        camera = [{'seq': 0, 'header_ns': 70, 'true_ns': 0}]
        imu = [{'seq': 0, 'header_ns': 0, 'true_ns': 0}, {'seq': 1, 'header_ns': 70, 'true_ns': 70}]
        self.assertEqual(align(camera, imu, tolerance_ns=0)[0]['true_error_ns'], 70)
        self.assertEqual(align(camera, imu, 70, 0)[0]['true_error_ns'], 0)
        self.assertIsNone(align(camera, [], 70, 0)[0]['imu_seq'])

    def test_extrema_survive(self):
        rows = [{'seq': i, 'true_ns': i, 'value': value} for i, value in enumerate([0, 12, 1, -2, 3])]
        self.assertEqual([r['seq'] for r in thin(rows)], [0, 1, 3])


if __name__ == '__main__':
    unittest.main()
