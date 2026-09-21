"""Inspect native CCMC SWMF/GM adaptive-volume output without loading it all.

CCMC ``3d__var_1`` states are SWMF IDL-plot files: Fortran-unformatted
records containing an unstructured, block-ordered cell-centre grid.  The
companion ASCII ``.tree`` file is the authoritative BATL AMR topology.  This
module deliberately stops at validated, read-only access; browser reduction
belongs in a separate event build step on bigmem-PC.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable

import numpy as np


@dataclass(frozen=True)
class Record:
    payload_offset: int
    byte_count: int


@dataclass(frozen=True)
class BatlTree:
    dimensions: int
    info_columns: int
    refinement_ratio: tuple[int, ...]
    root_blocks: tuple[int, ...]
    nodes: np.ndarray

    @property
    def leaves_in_plot_order(self) -> np.ndarray:
        """Return used leaf nodes in the processor/block ordering of ``.out``."""

        leaves = self.nodes[self.nodes[:, 0] == 1]
        return leaves[np.lexsort((leaves[:, 3], leaves[:, 2]))]


def read_batl_tree(path: Path | str) -> BatlTree:
    lines = Path(path).read_text(encoding="ascii").splitlines()
    try:
        start = lines.index("#START")
    except ValueError as error:
        raise ValueError("BATL tree has no #START marker") from error

    dimensions, info_columns, node_count = map(int, lines[start + 1].split())
    refinement_ratio = tuple(map(int, lines[start + 2].split()))
    root_blocks = tuple(map(int, lines[start + 3].split()))
    rows = [tuple(map(int, line.split())) for line in lines[start + 4 :] if line.strip()]
    if len(refinement_ratio) != dimensions or len(root_blocks) != dimensions:
        raise ValueError("BATL dimensional metadata is inconsistent")
    if len(rows) != node_count or any(len(row) != info_columns for row in rows):
        raise ValueError("BATL node table does not match its declared shape")
    nodes = np.asarray(rows, dtype=np.int32)
    return BatlTree(dimensions, info_columns, refinement_ratio, root_blocks, nodes)


def _marker_endian(handle: BinaryIO, file_size: int) -> str:
    marker_bytes = handle.read(4)
    if len(marker_bytes) != 4:
        raise ValueError("empty or truncated SWMF plot file")
    for endian in ("<", ">"):
        length = struct.unpack(f"{endian}i", marker_bytes)[0]
        if not 0 < length < file_size - 8:
            continue
        handle.seek(4 + length)
        trailing = handle.read(4)
        if len(trailing) == 4 and struct.unpack(f"{endian}i", trailing)[0] == length:
            handle.seek(0)
            return endian
    raise ValueError("not a supported Fortran-unformatted SWMF plot file")


def _consume_record(handle: BinaryIO, endian: str) -> Record:
    marker = handle.read(4)
    if len(marker) != 4:
        raise EOFError("missing Fortran record marker")
    byte_count = struct.unpack(f"{endian}i", marker)[0]
    if byte_count < 0:
        raise ValueError("negative Fortran record size")
    payload_offset = handle.tell()
    handle.seek(byte_count, 1)
    trailing = handle.read(4)
    if len(trailing) != 4 or struct.unpack(f"{endian}i", trailing)[0] != byte_count:
        raise ValueError("Fortran record markers do not match")
    return Record(payload_offset, byte_count)


def _record_bytes(handle: BinaryIO, endian: str) -> bytes:
    record = _consume_record(handle, endian)
    end = handle.tell()
    handle.seek(record.payload_offset)
    payload = handle.read(record.byte_count)
    handle.seek(end)
    return payload


class SwmfPlotVolume:
    """Memory-mapped, selective reader for one native SWMF plot frame."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        file_size = self.path.stat().st_size
        with self.path.open("rb") as handle:
            self.endian = _marker_endian(handle, file_size)
            self.headline = _record_bytes(handle, self.endian).decode("ascii", errors="replace").strip()
            header = _record_bytes(handle, self.endian)
            if len(header) == 20:
                self.float_size = 4
                values = struct.unpack(f"{self.endian}ifiii", header)
            elif len(header) == 24:
                self.float_size = 8
                values = struct.unpack(f"{self.endian}idiii", header)
            else:
                raise ValueError(f"unsupported SWMF numeric header size: {len(header)}")
            self.iteration, self.runtime, signed_dimensions, self.parameter_count, self.variable_count = values
            self.dimensions = abs(signed_dimensions)
            grid_payload = _record_bytes(handle, self.endian)
            self.grid = np.frombuffer(grid_payload, dtype=f"{self.endian}i4").astype(np.int64)
            if self.grid.size != self.dimensions:
                raise ValueError("grid dimensionality does not match the SWMF header")
            self.point_count = abs(math.prod(map(int, self.grid)))

            parameter_payload = _record_bytes(handle, self.endian) if self.parameter_count else b""
            parameter_values = np.frombuffer(parameter_payload, dtype=self.float_dtype)
            if parameter_values.size != self.parameter_count:
                raise ValueError("parameter record has the wrong length")
            names = _record_bytes(handle, self.endian).decode("ascii", errors="strict").split()
            expected_names = self.dimensions + self.variable_count + self.parameter_count
            if len(names) != expected_names:
                raise ValueError(f"expected {expected_names} names, found {len(names)}")
            self.coordinate_names = tuple(names[: self.dimensions])
            self.variable_names = tuple(names[self.dimensions : self.dimensions + self.variable_count])
            parameter_names = names[-self.parameter_count :] if self.parameter_count else []
            self.parameters = dict(zip(parameter_names, map(float, parameter_values), strict=True))

            coordinate_record = _consume_record(handle, self.endian)
            expected_coordinates = self.dimensions * self.point_count * self.float_size
            if coordinate_record.byte_count != expected_coordinates:
                raise ValueError("coordinate record has the wrong length")
            stride = self.point_count * self.float_size
            self._records = {
                name: Record(coordinate_record.payload_offset + index * stride, stride)
                for index, name in enumerate(self.coordinate_names)
            }
            for name in self.variable_names:
                record = _consume_record(handle, self.endian)
                if record.byte_count != stride:
                    raise ValueError(f"variable {name} has the wrong record length")
                self._records[name] = record
            if handle.tell() != file_size:
                raise ValueError("plot file has trailing data; use a multi-frame reader for .outs files")

    @property
    def float_dtype(self) -> np.dtype:
        return np.dtype(f"{self.endian}f{self.float_size}")

    def array(self, name: str) -> np.memmap:
        try:
            record = self._records[name]
        except KeyError as error:
            raise KeyError(f"unknown SWMF field {name!r}") from error
        return np.memmap(
            self.path,
            dtype=self.float_dtype,
            mode="r",
            offset=record.payload_offset,
            shape=(self.point_count,),
        )

    @property
    def block_shape(self) -> tuple[int, ...]:
        shape = tuple(int(round(self.parameters.get(name, 0))) for name in ("NX", "NY", "NZ")[: self.dimensions])
        if any(value <= 0 for value in shape):
            raise ValueError("plot metadata does not declare a positive block shape")
        return shape

    def summary(self) -> dict[str, object]:
        return {
            "path": str(self.path),
            "bytes": self.path.stat().st_size,
            "headline": self.headline,
            "iteration": int(self.iteration),
            "runtimeSeconds": float(self.runtime),
            "dimensions": self.dimensions,
            "grid": list(map(int, self.grid)),
            "pointCount": self.point_count,
            "blockShape": list(self.block_shape),
            "blockCount": self.point_count // math.prod(self.block_shape),
            "coordinates": list(self.coordinate_names),
            "variables": list(self.variable_names),
            "parameters": self.parameters,
        }


def validate_tree_plot_alignment(
    plot: SwmfPlotVolume,
    tree: BatlTree,
    domain_minimum: Iterable[float],
    domain_maximum: Iterable[float],
    *,
    tolerance: float = 1e-5,
) -> dict[str, object]:
    """Verify that BATL leaves map exactly onto plot blocks.

    BATL columns are status, level, processor, block, min/max level,
    integer coordinates, parent, then children.  SWMF writes leaf blocks in
    processor-major, local-block-minor order.
    """

    if tree.dimensions != plot.dimensions:
        raise ValueError("tree and plot dimensions differ")
    leaves = tree.leaves_in_plot_order
    cells_per_block = math.prod(plot.block_shape)
    if plot.point_count != len(leaves) * cells_per_block:
        raise ValueError("tree leaf count does not match plot cell count")

    block_centres = np.column_stack(
        [np.asarray(plot.array(name)).reshape(len(leaves), cells_per_block).mean(axis=1) for name in plot.coordinate_names]
    )
    lower = np.asarray(tuple(domain_minimum), dtype=np.float64)
    upper = np.asarray(tuple(domain_maximum), dtype=np.float64)
    if lower.shape != (plot.dimensions,) or upper.shape != (plot.dimensions,):
        raise ValueError("domain bounds have the wrong dimensionality")
    levels = leaves[:, 1]
    integer_coordinates = leaves[:, 6 : 6 + plot.dimensions]
    expected = lower + (integer_coordinates - 0.5) * (upper - lower) / (2.0 ** levels[:, None])
    absolute_error = np.abs(block_centres - expected)
    maximum_error = absolute_error.max(axis=0)
    if np.any(maximum_error > tolerance):
        raise ValueError(f"plot blocks do not align with BATL leaves: max error {maximum_error.tolist()}")
    return {
        "treeNodeCount": int(len(tree.nodes)),
        "leafBlockCount": int(len(leaves)),
        "parentNodeCount": int(len(tree.nodes) - len(leaves)),
        "levels": {str(int(level)): int(count) for level, count in zip(*np.unique(levels, return_counts=True), strict=True)},
        "maximumBlockCentreError": maximum_error.tolist(),
    }


def _info_bounds(path: Path | str, dimensions: int) -> tuple[list[float], list[float]]:
    labels: dict[str, float] = {}
    for line in Path(path).read_text(encoding="ascii").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                labels[parts[-1]] = float(parts[0])
            except ValueError:
                pass
    lower = [labels[f"XyzMin{index}"] for index in range(1, dimensions + 1)]
    upper = [labels[f"XyzMax{index}"] for index in range(1, dimensions + 1)]
    return lower, upper


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plot", type=Path)
    parser.add_argument("--tree", type=Path)
    parser.add_argument("--info", type=Path)
    arguments = parser.parse_args(argv)
    plot = SwmfPlotVolume(arguments.plot)
    output = plot.summary()
    if arguments.tree:
        if not arguments.info:
            parser.error("--tree validation also requires --info domain bounds")
        tree = read_batl_tree(arguments.tree)
        lower, upper = _info_bounds(arguments.info, plot.dimensions)
        output["topologyValidation"] = validate_tree_plot_alignment(plot, tree, lower, upper)
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
