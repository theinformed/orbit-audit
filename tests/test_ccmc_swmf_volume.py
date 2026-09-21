import struct
import tempfile
import unittest
from pathlib import Path

import numpy as np

from pipeline.ccmc_swmf_volume import SwmfPlotVolume, read_batl_tree, validate_tree_plot_alignment


def _record(payload: bytes) -> bytes:
    marker = struct.pack("<i", len(payload))
    return marker + payload + marker


class CcmcSwmfVolumeTests(unittest.TestCase):
    def test_selective_plot_reader_and_batl_alignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plot_path = root / "3d__var_1_e20240510-000000-000.out"
            tree_path = plot_path.with_suffix(".tree")
            coordinates = {
                "x": np.asarray([-0.5, 0.5, -0.5, 0.5, -0.5, 0.5, -0.5, 0.5], dtype="<f4"),
                "y": np.asarray([-0.5, -0.5, 0.5, 0.5, -0.5, -0.5, 0.5, 0.5], dtype="<f4"),
                "z": np.asarray([-0.5, -0.5, -0.5, -0.5, 0.5, 0.5, 0.5, 0.5], dtype="<f4"),
            }
            density = np.arange(8, dtype="<f4") + 1
            payload = b"".join(
                [
                    _record(b"2024-05-10T00:00:00; R R R Mp/cc"),
                    _record(struct.pack("<ifiii", 1500, 0.0, -3, 4, 1)),
                    _record(np.asarray([8, 1, 1], dtype="<i4").tobytes()),
                    _record(np.asarray([2, 2, 2, 2.5], dtype="<f4").tobytes()),
                    _record(b"x y z Rho NX NY NZ R"),
                    _record(b"".join(value.tobytes() for value in coordinates.values())),
                    _record(density.tobytes()),
                ]
            )
            plot_path.write_bytes(payload)
            tree_path.write_text(
                "\n".join(
                    [
                        "BATL tree information after #START",
                        "#START",
                        "3 18 1",
                        "2 2 2",
                        "1 1 1",
                        "1 0 0 1 0 30 1 1 1 -100 -100 -100 -100 -100 -100 -100 -100 -100",
                    ]
                )
                + "\n",
                encoding="ascii",
            )

            plot = SwmfPlotVolume(plot_path)
            self.assertEqual(plot.point_count, 8)
            self.assertEqual(plot.block_shape, (2, 2, 2))
            np.testing.assert_array_equal(plot.array("Rho"), density)
            tree = read_batl_tree(tree_path)
            validation = validate_tree_plot_alignment(plot, tree, (-1, -1, -1), (1, 1, 1))
            self.assertEqual(validation["leafBlockCount"], 1)
            self.assertEqual(validation["maximumBlockCentreError"], [0.0, 0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
