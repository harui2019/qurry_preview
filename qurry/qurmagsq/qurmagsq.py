from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.quantum_info import Operator

import time
import numpy as np
from pathlib import Path
from itertools import permutations
from typing import Union, Optional, NamedTuple, Hashable, Type, Any

from ..tools import ProcessManager, workers_distribution, DEFAULT_POOL_SIZE
from ..qurrium import (
    QurryV5Prototype,
    ExperimentPrototype,
    AnalysisPrototype,
)


def _magnetsqCell(
    idx: int,
    singleCounts: dict[str, int],
    shots: int,
) -> tuple[int, float]:
    """Calculate the magnitudes square cell

    Args:
        idx (int): Index of the cell (counts).
        singleCounts (dict[str, int]): Counts measured by the single quantum circuit.

    Returns:
        tuple[int, float]: Index, one of magnitudes square.
    """
    magnetsqCell = np.float64(0)
    for bits in singleCounts:
        if (bits == '00') or (bits == '11'):
            magnetsqCell += np.float64(singleCounts[bits])/shots
        else:
            magnetsqCell -= np.float64(singleCounts[bits])/shots
    return idx, magnetsqCell


def _magnetic_square_core(
    counts: list[dict[str, int]],
    shots: int,
    num_qubits: int,
    workers_num: Optional[int] = None,
) -> dict[str, float]:
    """Computing specific quantity.
    Where should be overwritten by each construction of new measurement.

    Returns:
        tuple[dict, dict]:
            Magnitudes square of experiment.
    """

    # Determine worker number
    launch_worker = workers_distribution(workers_num)

    length = len(counts)
    Begin = time.time()

    if launch_worker == 1:
        magnetsqCellList: list[float] = []
        print(
            f"| Without multi-processing to calculate overlap of {length} counts. It will take a lot of time to complete.")
        for i, c in enumerate(counts):
            magnetsqCell = 0
            checkSum = 0
            print(
                f"| Calculating magnetsq on {i}" +
                f" - {i}/{length} - {round(time.time() - Begin, 3)}s.", end="\r")

            magnetsqCell = _magnetsqCell(i, c, shots)
            magnetsqCellList.append(magnetsqCell)
            print(
                f"| Calculating magnetsq end - {i}/{length}" +
                f" - {round(time.time() - Begin, 3)}s." +
                " "*30, end="\r")
            assert checkSum != shots, f"count index:{i} may not be contained by '00', '11', '01', '10'."

    else:
        print(
            f"| With {launch_worker} workers to calculate overlap of {length} counts.")
        pool = ProcessManager(launch_worker)
        magnetsqCellList = pool.starmap(
            _magnetsqCell, [(i, c, shots) for i, c in enumerate(counts)])
        print(f"| Calculating overlap end - {round(time.time() - Begin, 3)}s.")

    magnetsq = (sum(magnetsqCellList) + num_qubits)/(num_qubits**2)

    quantity = {
        'magnetsq': magnetsq,
        'countsNum': len(counts),
    }
    return quantity


class MagnetSquareAnalysis(AnalysisPrototype):
    """

    'qurmagsq' may be read as `qurmask`

    """

    __name__ = 'qurmaqsq.MagsqAnalysis'
    shortName = 'qurmagsq.report'

    class analysisInput(NamedTuple):
        """To set the analysis."""
        shots: int
        num_qubits: int

    class analysisContent(NamedTuple):
        """The content of the analysis."""

        magsq: float
        """The magnitude square."""
        countsNum: Optional[int] = None

    @classmethod
    def quantities(
        cls,
        counts: list[dict[str, int]],
        shots: int,
        num_qubits: int,
        workers_num: Optional[int] = None,
    ) -> dict[str, float]:
        """Computing specific quantity.
        Where should be overwritten by each construction of new measurement.

        Returns:
            tuple[dict, dict]:
                Counts, purity, entropy of experiment.
        """

        return _magnetic_square_core(
            counts=counts,
            shots=shots,
            num_qubits=num_qubits,
            workers_num=workers_num,
        )

class MagnetSquareExperiment(ExperimentPrototype):
    
    __name__ = 'qurmagsq.MagsqExperiment'
    shortName = 'qurmagsq.exp'
    
    class arguments(NamedTuple):
        """Arguments for the experiment."""
        expName: str = 'exps'
        num_qubits: int = 0
        workers_num: int = DEFAULT_POOL_SIZE
        
    @classmethod
    @property
    def analysis_container(cls) -> Type[MagnetSquareAnalysis]:
        """The container class responding to this QurryV5 class.
        """
        return MagnetSquareAnalysis
    
    def analyze(
        self,
        workers_num: Optional[int] = None,
    ) -> MagnetSquareAnalysis:
        """Calculate entangled entropy with more information combined.

        Args:
            workers_num (Optional[int], optional): 
                Number of multi-processing workers, 

        Returns:
            dict[str, float]: A dictionary contains magnitudes square and number of counts.
        """
        
        self.args: MagnetSquareExperiment.arguments
        shots = self.commons.shots
        num_qubits = self.args.num_qubits
        counts = self.afterwards.counts
        
        qs = self.analysis_container.quantities(
            shots=shots,
            counts=counts,
            num_qubits=num_qubits,
            workers_num=workers_num,
        )
        
        serial = len(self.reports)
        analysis = self.analysis_container(
            serial=serial,
            shots=shots,
            **qs,
        )
        
        self.reports[serial] = analysis
        return analysis
    
def _circuit_method_core(
    idx: int,
    tgtCircuit: QuantumCircuit,
    expName: str,
    i: int,
    j: int,
):
    """The core method of the circuit method.

    Returns:
        QuantumCircuit: The circuit.
    """
    num_qubits = tgtCircuit.num_qubits
    
    qFunc = QuantumRegister(num_qubits, 'q1')
    cMeas = ClassicalRegister(2, 'c1')
    qcExp = QuantumCircuit(qFunc, cMeas)
    qcExp.name = f"{expName}-{idx}-{i}-{j}"

    qcExp.append(tgtCircuit, [qFunc[i] for i in range(num_qubits)])
    qcExp.barrier()
    qcExp.measure(qFunc[i], cMeas[0])
    qcExp.measure(qFunc[j], cMeas[1])

    return qcExp

class MagnetSquare(QurryV5Prototype):

    __name__ = 'qurmagsq.MagnetSquare'
    shortName = 'qurmagsq'
    
    @classmethod
    @property
    def experiment(cls) -> Type[MagnetSquareExperiment]:
        """The container class responding to this QurryV5 class.
        """
        return MagnetSquareExperiment
    
    def paramsControl(
        self,
        expName: str = 'exps',
        waveKey: Hashable = None,
        **otherArgs: any
    ) -> tuple[MagnetSquareExperiment.arguments, MagnetSquareExperiment.commonparams, dict[str, Any]]:
        """Handling all arguments and initializing a single experiment.

        Args:
            waveKey (Hashable):
                The index of the wave function in `self.waves` or add new one to calaculation,
                then choose one of waves as the experiment material.
                If input is `QuantumCircuit`, then add and use it.
                If input is the key in `.waves`, then use it.
                If input is `None` or something illegal, then use `.lastWave'.
                Defaults to None.

            expName (str, optional):
                Naming this experiment to recognize it when the jobs are pending to IBMQ Service.
                This name is also used for creating a folder to store the exports.
                Defaults to `'exps'`.

            otherArgs (any):
                Other arguments.

        Returns:
            dict: The export will be processed in `.paramsControlCore`
        """
        
        num_qubits = self.waves[waveKey].num_qubits
        expName = f"w={waveKey}-Nq={num_qubits}.{self.shortName}"
        
        return self.experiment.filter(
            expName=expName,
            waveKey=waveKey,
            num_qubits=num_qubits,
            **otherArgs,
        )
        
    def method(
        self,
        expID: Hashable,
    ) -> list[QuantumCircuit]:

        assert expID in self.exps
        assert self.exps[expID].commons.expID == expID
        args: MagnetSquareExperiment.arguments = self.exps[expID].args
        commons: MagnetSquareExperiment.commonparams = self.exps[expID].commons
        circuit = self.waves[commons.waveKey]
        assert circuit.num_qubits == args.num_qubits

        permut = [b for b in permutations([a for a in range(args.num_qubits)], 2)]
        pool = ProcessManager(args.workers_num)

        qcList = pool.starmap(
            _circuit_method_core, [(
                idx, circuit, args.expName, i, j
            ) for idx, (i, j) in enumerate(permut)])
        if isinstance(commons.serial, int):
            print(
                f"| Build circuit: {commons.waveKey}, worker={args.workers_num}," +
                f" serial={commons.serial}, by={commons.summonerName} done."
            )
        else:
            print(f"| Build circuit: {commons.waveKey} done.", end="\r")

        return qcList
    
    def measure(
        self,
        wave: Union[QuantumCircuit, any, None] = None,
        expName: str = 'exps',
        *args,
        saveLocation: Optional[Union[Path, str]] = None,
        mode: str = 'w+',
        indent: int = 2,
        encoding: str = 'utf-8',
        jsonablize: bool = False,
        **otherArgs: any
    ) -> Hashable:
        """

        Args:
            wave (Union[QuantumCircuit, int, None], optional):
                The index of the wave function in `self.waves` or add new one to calaculation,
                then choose one of waves as the experiment material.
                If input is `QuantumCircuit`, then add and use it.
                If input is the key in `.waves`, then use it.
                If input is `None` or something illegal, then use `.lastWave'.
                Defaults to None.

            expName (str, optional):
                Naming this experiment to recognize it when the jobs are pending to IBMQ Service.
                This name is also used for creating a folder to store the exports.
                Defaults to `'exps'`.

            otherArgs (any):
                Other arguments.

        Returns:
            dict: The output.
        """

        IDNow = self.result(
            wave=wave,
            expName=expName,
            saveLocation=None,
            **otherArgs,
        )
        assert IDNow in self.exps, f"ID {IDNow} not found."
        assert self.exps[IDNow].commons.expID == IDNow
        currentExp = self.exps[IDNow]

        if isinstance(saveLocation, (Path, str)):
            currentExp.write(
                saveLocation=saveLocation,
                mode=mode,
                indent=indent,
                encoding=encoding,
                jsonablize=jsonablize,
            )

        return IDNow
