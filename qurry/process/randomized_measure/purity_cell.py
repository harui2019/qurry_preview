"""
================================================================
Postprocessing - Randomized Measure - Purity Cell
(:mod:`qurry.process.randomized_measure.purity_cell`)
================================================================

"""

import warnings
from typing import Union, Literal
import numpy as np

from ..utils import (
    ensemble_cell as ensemble_cell_py,
    cycling_slice as cycling_slice_py,
)
from ..exceptions import (
    PostProcessingCythonImportError,
    PostProcessingCythonUnavailableWarning,
    PostProcessingRustImportError,
    PostProcessingRustUnavailableWarning,
)


try:
    from ...boost.randomized import purityCellCore  # type: ignore

    CYTHON_AVAILABLE = True
    FAILED_PYX_IMPORT = None
except ImportError as err:
    FAILED_PYX_IMPORT = err
    CYTHON_AVAILABLE = False
    # pylint: disable=invalid-name, unused-argument

    def purityCellCore(*args, **kwargs):
        """Dummy function for purityCellCore."""
        raise PostProcessingCythonImportError(
            "Cython is not available, using python to calculate purity cell."
        ) from FAILED_PYX_IMPORT

    # pylint: enable=invalid-name, unused-argument

try:
    # Proven import point for rust modules
    # from ..boorust.randomized import (  # type: ignore
    #     purity_cell_rust as purity_cell_rust_source,  # type: ignore
    #     entangled_entropy_core_rust as entangled_entropy_core_rust_source,  # type: ignore
    # )

    from ...boorust import randomized  # type: ignore

    purity_cell_rust_source = randomized.purity_cell_rust

    RUST_AVAILABLE = True
    FAILED_RUST_IMPORT = None
except ImportError as err:
    RUST_AVAILABLE = False
    FAILED_RUST_IMPORT = err

    def purity_cell_rust_source(*args, **kwargs):
        """Dummy function for purity_cell_rust."""
        raise PostProcessingRustImportError(
            "Rust is not available, using python to calculate purity cell."
        ) from FAILED_RUST_IMPORT


ExistingProcessBackendLabel = Literal["Cython", "Rust", "Python"]
BackendAvailabilities: dict[
    ExistingProcessBackendLabel, Union[bool, ImportError, None]
] = {
    "Cython": CYTHON_AVAILABLE if CYTHON_AVAILABLE else FAILED_PYX_IMPORT,
    "Rust": RUST_AVAILABLE if RUST_AVAILABLE else FAILED_RUST_IMPORT,
    "Python": True,
}
DEFAULT_PROCESS_BACKEND: ExistingProcessBackendLabel = (
    "Rust" if RUST_AVAILABLE else ("Cython" if CYTHON_AVAILABLE else "Python")
)


# Randomized measure
def purity_cell_py(
    idx: int,
    single_counts: dict[str, int],
    bitstring_range: tuple[int, int],
    subsystem_size: int,
) -> tuple[int, np.float64]:
    """Calculate the purity cell, one of overlap, of a subsystem by Python.

    Args:
        idx (int): Index of the cell (counts).
        single_counts (dict[str, int]): Counts measured by the single quantum circuit.
        bitstring_range (tuple[int, int]): The range of the subsystem.
        subsystem_size (int): Subsystem size included.

    Returns:
        tuple[int, float]: Index, one of overlap purity.
    """

    shots = sum(single_counts.values())

    _dummy_string = "".join(str(ds) for ds in range(subsystem_size))
    if _dummy_string[bitstring_range[0] : bitstring_range[1]] == cycling_slice_py(
        _dummy_string, bitstring_range[0], bitstring_range[1], 1
    ):
        single_counts_under_degree = dict.fromkeys(
            [k[bitstring_range[0] : bitstring_range[1]] for k in single_counts], 0
        )
        for bitstring in list(single_counts):
            single_counts_under_degree[
                bitstring[bitstring_range[0] : bitstring_range[1]]
            ] += single_counts[bitstring]

    else:
        single_counts_under_degree = dict.fromkeys(
            [
                cycling_slice_py(k, bitstring_range[0], bitstring_range[1], 1)
                for k in single_counts
            ],
            0,
        )
        for bitstring in list(single_counts):
            single_counts_under_degree[
                cycling_slice_py(bitstring, bitstring_range[0], bitstring_range[1], 1)
            ] += single_counts[bitstring]

    _purity_cell = np.float64(0)
    for s_ai, s_ai_meas in single_counts_under_degree.items():
        for s_aj, s_aj_meas in single_counts_under_degree.items():
            _purity_cell += ensemble_cell_py(
                s_ai, s_ai_meas, s_aj, s_aj_meas, subsystem_size, shots
            )

    return idx, _purity_cell


def purity_cell_cy(
    idx: int,
    single_counts: dict[str, int],
    bitstring_range: tuple[int, int],
    subsystem_size: int,
) -> tuple[int, float]:
    """Calculate the purity cell, one of overlap, of a subsystem by Cython.

    Args:
        idx (int): Index of the cell (counts).
        single_counts (dict[str, int]): Counts measured by the single quantum circuit.
        bitstring_range (tuple[int, int]): The range of the subsystem.
        subsystem_size (int): Subsystem size included.

    Returns:
        tuple[int, float]: Index, one of overlap purity.
    """

    return idx, purityCellCore(dict(single_counts), bitstring_range, subsystem_size)


def purity_cell_rust(
    idx: int,
    single_counts: dict[str, int],
    bitstring_range: tuple[int, int],
    subsystem_size: int,
) -> tuple[int, float]:
    """Calculate the purity cell, one of overlap, of a subsystem by Rust.

    Args:
        idx (int): Index of the cell (counts).
        single_counts (dict[str, int]): Counts measured by the single quantum circuit.
        bitstring_range (tuple[int, int]): The range of the subsystem.
        subsystem_size (int): Subsystem size included.

    Returns:
        tuple[int, float]: Index, one of overlap purity.
    """

    return purity_cell_rust_source(idx, single_counts, bitstring_range, subsystem_size)


def purity_cell(
    idx: int,
    single_counts: dict[str, int],
    bitstring_range: tuple[int, int],
    subsystem_size: int,
    backend: ExistingProcessBackendLabel = DEFAULT_PROCESS_BACKEND,
) -> tuple[int, Union[float, np.float64]]:
    """Calculate the purity cell, one of overlap, of a subsystem.

    Args:
        idx (int): Index of the cell (counts).
        single_counts (dict[str, int]): Counts measured by the single quantum circuit.
        bitstring_range (tuple[int, int]): The range of the subsystem.
        subsystem_size (int): Subsystem size included.
        backend (ExistingProcessBackendLabel, optional):
            Backend for the process. Defaults to DEFAULT_PROCESS_BACKEND.

    Returns:
        tuple[int, float]: Index, one of overlap purity.
    """
    if not RUST_AVAILABLE and backend == "Rust":
        warnings.warn(
            "Rust is not available, using Cython or Python to calculate purity cell."
            + f"Check the error: {FAILED_RUST_IMPORT}",
            PostProcessingRustUnavailableWarning,
        )
        backend = "Cython" if CYTHON_AVAILABLE else "Python"
    if not CYTHON_AVAILABLE and backend == "Cython":
        warnings.warn(
            "Cython is not available, using Python or Rust to calculate purity cell."
            + f"Check the error: {FAILED_PYX_IMPORT}",
            PostProcessingCythonUnavailableWarning,
        )
        backend = "Rust" if RUST_AVAILABLE else "Python"

    if backend == "Cython":
        return purity_cell_cy(idx, single_counts, bitstring_range, subsystem_size)
    if backend == "Rust":
        return purity_cell_rust(idx, single_counts, bitstring_range, subsystem_size)
    return purity_cell_py(idx, single_counts, bitstring_range, subsystem_size)
