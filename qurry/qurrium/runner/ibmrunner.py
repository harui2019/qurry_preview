"""
================================================================
Runner for IBM backend
(:mod:`qurry.qurrium.runner.ibmrunner`)
================================================================

"""
import warnings
from typing import Literal, Hashable, Union, Optional, Iterable
from qiskit import QuantumCircuit

from ...exceptions import QurryExtraPackageRequired

try:
    from qiskit.providers.ibmq import IBMQBackend  # type: ignore
    from qiskit.providers.ibmq.job import IBMQJob  # type: ignore
    from qiskit.providers.ibmq.exceptions import IBMQBackendApiError  # type: ignore

    QISKIT_IBMQ_PROVIDER = True
except ImportError:
    QISKIT_IBMQ_PROVIDER = False
try:
    from qiskit_ibm_provider import IBMBackend, IBMProvider  # type: ignore
    from qiskit_ibm_provider.job import IBMCircuitJob  # type: ignore
    from qiskit_ibm_provider.exceptions import IBMError  # type: ignore
except ImportError:
    raise QurryExtraPackageRequired(
        "These module requires the install of `qiskit-ibm-provider`,"
        + " please intall it then restart kernel."
    ) from ImportError

from .runner import Runner, retrieve_times_namer
from ..multimanager import MultiManager
from ..container import ExperimentContainer
from ..utils import get_counts_and_exceptions
from ...tools import qurry_progressbar, current_time


class IBMRunner(Runner):
    """Pending and Retrieve Jobs from IBM backend."""

    backend: IBMBackend
    """The backend been used."""
    reports: dict[str, dict[str, str]]

    def __init__(
        self,
        besummonned: Hashable,
        multimanager: MultiManager,
        experimental_container: ExperimentContainer,
        backend: Optional[IBMBackend] = None,
        provider: Optional[IBMProvider] = None,
    ):
        assert multimanager.summoner_id == besummonned, (
            "Summoner ID not match, multimanager.summoner_id: "
            + f"{multimanager.summoner_id}, besummonned: {besummonned}"
        )
        if backend is None and provider is None:
            raise ValueError("Either backend or provider should be provided.")

        self.current_multimanager = multimanager
        """The multimanager from Qurry instance."""
        self.backend = backend
        """The backend will be use to pending and retrieve."""
        self.provider = backend.provider if backend is not None else provider
        """The provider will be used to pending and retrieve."""
        self.experiment_container = experimental_container
        """The experimental container from Qurry instance."""

        self.circwserial: dict[int, QuantumCircuit] = {}

        self.reports = {}

    def pending(
        self,
        pending_strategy: Literal["onetime", "each", "tags"] = "onetime",
        backend: Optional[IBMBackend] = None,
    ) -> list[tuple[str, str]]:
        if self.backend is None:
            if backend is None:
                raise ValueError(
                    "At least one of backend and provider should be given."
                )
            print(
                f"| Given backend and provider as {backend.name} and {backend.provider()}."
            )
            self.backend = backend
            self.provider = backend.provider()
        else:
            if backend is not None:
                print(
                    "| Using backend and provider as "
                    + f"{self.backend.name} and {self.backend.provider()}."
                )
            else:
                ...

        distributing_pending_progressbar = qurry_progressbar(
            self.current_multimanager.beforewards.exps_config,
            bar_format="| {n_fmt}/{total_fmt} - Preparing pending pool - {elapsed} < {remaining}",
            # leave=False,
        )

        for id_exec in distributing_pending_progressbar:
            circ_serial_len = len(self.circwserial)
            for idx, circ in enumerate(
                self.experiment_container[id_exec].beforewards.circuit
            ):
                self.current_multimanager.beforewards.circuits_map[id_exec].append(
                    idx + circ_serial_len
                )

                if pending_strategy == "each":
                    self.current_multimanager.beforewards.pending_pool[id_exec].append(
                        idx + circ_serial_len
                    )

                elif pending_strategy == "tags":
                    tags = self.experiment_container[id_exec].commons.tags
                    self.current_multimanager.beforewards.pending_pool[tags].append(
                        idx + circ_serial_len
                    )

                else:
                    if pending_strategy != "onetime":
                        warnings.warn(
                            f"Unknown strategy '{pending_strategy}, use 'onetime'."
                        )
                    self.current_multimanager.beforewards.pending_pool[
                        "_onetime"
                    ].append(idx + circ_serial_len)

                self.circwserial[idx + circ_serial_len] = circ

        current = current_time()
        self.current_multimanager.multicommons.datetimes["pending"] = current

        pendingpool_progressbar = qurry_progressbar(
            self.current_multimanager.beforewards.pending_pool.items(),
            bar_format="| {n_fmt}/{total_fmt} - pending: {desc} - {elapsed} < {remaining}",
            # leave=False,
        )

        for pk, pcirc_idxs in pendingpool_progressbar:
            if len(pcirc_idxs) > 0:
                if pk == "_onetime":
                    pending_tags = []
                elif isinstance(pk, (list, tuple)):
                    pending_tags = list(pk)
                else:
                    pending_tags = [pk]

                all_pending_tags = [
                    str(s)
                    for s in [
                        self.current_multimanager.multicommons.summoner_name,
                        self.current_multimanager.multicommons.summoner_id,
                        *pending_tags,
                        *self.current_multimanager.multicommons.tags,
                    ]
                ]
                if len(all_pending_tags) > 8:
                    all_pending_tags = all_pending_tags[:8]
                    warnings.warn(
                        "The max number of tags is 8 in IBMProvider, "
                        + f"but the number of pending tags is {len(all_pending_tags)}, "
                        + "so only take first 8.",
                    )

                pending_job = self.backend.run(
                    circuits=[self.circwserial[idx] for idx in pcirc_idxs],
                    shots=self.current_multimanager.multicommons.shots,
                    job_tags=all_pending_tags,
                    **self.current_multimanager.multicommons.manager_run_args,
                )
                pendingpool_progressbar.set_description_str(
                    f"{pk}/{pending_job.job_id()}/{pending_job.tags()}"
                )
                self.current_multimanager.beforewards.job_id.append(
                    (pending_job.job_id(), pk)
                )
                self.reports[pending_job.job_id()] = {
                    "time": current,
                    "type": "pending",
                }

            else:
                self.current_multimanager.beforewards.job_id.append((None, pk))
                warnings.warn(f"| Pending pool '{pk}' is empty.")

        for id_exec in self.current_multimanager.beforewards.exps_config:
            self.experiment_container[id_exec].commons.datetimes["pending"] = current

        self.current_multimanager.multicommons.datetimes[
            "pendingCompleted"
        ] = current_time()

        return self.current_multimanager.beforewards.job_id

    def retrieve(
        self,
        overwrite: bool = False,
    ) -> list[tuple[str, str]]:
        pending_map: dict[Hashable, Union[IBMCircuitJob, "IBMQJob"]] = {}
        couts_tmp_container: dict[str, dict[str, int]] = {}

        already_retrieved: list[str] = [
            datetimeTag
            for datetimeTag in self.current_multimanager.multicommons.datetimes
            if "retrieve" in datetimeTag
        ]
        retrieve_times = len(already_retrieved)
        retrieve_times_name = retrieve_times_namer(retrieve_times + 1)

        if retrieve_times > 1 and overwrite is False:
            print(f"| retrieve times: {retrieve_times}, overwrite: {overwrite}")
            last_time_date = self.current_multimanager.multicommons.datetimes[
                retrieve_times_namer(retrieve_times)
            ]
            print(
                f"| Last retrieve by: {retrieve_times_namer(retrieve_times)} at {last_time_date}"
            )
            print("| Seems to there are some retrieves before.")
            print("| You can use `overwrite=True` to overwrite the previous retrieve.")

            return self.current_multimanager.beforewards.job_id

        if overwrite:
            print("| Overwrite the previous retrieve.")
        self.current_multimanager.reset_afterwards(security=True, muteWarning=True)
        assert (
            len(self.current_multimanager.afterwards.allCounts) == 0
        ), "All counts should be null."

        current = current_time()
        self.current_multimanager.multicommons.datetimes[retrieve_times_name] = current

        if QISKIT_IBMQ_PROVIDER:
            print("| Downgrade compatibility with qiskit-ibmq-provider is available.")

        retrieve_progressbar = qurry_progressbar(
            self.current_multimanager.beforewards.job_id,
            bar_format="| {n_fmt}/{total_fmt} - retrieve: {desc} - {elapsed} < {remaining}",
            # leave=False,
        )

        if QISKIT_IBMQ_PROVIDER:
            if isinstance(self.backend, IBMQBackend):
                for pending_id, pk in retrieve_progressbar:
                    if pending_id is None:
                        warnings.warn(f"Pending pool '{pk}' is empty.")
                        continue
                    try:
                        retrieve_progressbar.set_description_str(
                            f"{pk}/{pending_id}", refresh=True
                        )
                        pending_map[pk] = self.backend.retrieve_job(job_id=pending_id)
                    except IBMQBackendApiError as e:
                        pending_map[pk] = None
                        retrieve_progressbar.set_description_str(
                            f"{pk}/{pending_id} - Error: {e}", refresh=True
                        )

            else:
                provider: IBMProvider = self.backend.provider
                for pending_id, pk in retrieve_progressbar:
                    if pending_id is None:
                        warnings.warn(f"Pending pool '{pk}' is empty.")
                        continue
                    if isinstance(pk, str):
                        ...
                    elif isinstance(pk, Iterable) and not isinstance(pk, tuple):
                        pk = tuple(pk)
                    try:
                        retrieve_progressbar.set_description_str(
                            f"{pk}/{pending_id}", refresh=True
                        )
                        pending_map[pk] = provider.retrieve_job(job_id=pending_id)
                    except IBMError as e:
                        pending_map[pk] = None
                        retrieve_progressbar.set_description_str(
                            f"{pk}/{pending_id} - Error: {e}", refresh=True
                        )

        else:
            provider: IBMProvider = self.backend.provider
            for pending_id, pk in retrieve_progressbar:
                if pending_id is None:
                    warnings.warn(f"Pending pool '{pk}' is empty.")
                    continue
                try:
                    retrieve_progressbar.set_description_str(
                        f"{pk}/{pending_id}", refresh=True
                    )
                    pending_map[pk] = provider.retrieve_job(job_id=pending_id)
                except IBMError as e:
                    retrieve_progressbar.set_description_str(
                        f"{pk}/{pending_id} - Error: {e}", refresh=True
                    )
                    pending_map[pk] = None

        pendingpool_progressbar = qurry_progressbar(
            self.current_multimanager.beforewards.pending_pool.items(),
            bar_format=(
                "| {n_fmt}/{total_fmt} - get counts: {desc} - {elapsed} < {remaining}"
            ),
            # leave=False,
        )

        for pk, pcircs in pendingpool_progressbar:
            if len(pcircs) > 0:
                pending_job = pending_map[pk]
                if pending_job is not None:
                    pendingpool_progressbar.set_description_str(
                        f"{pk}/{pending_job.job_id()}/{pending_job.tags()}",
                        refresh=True,
                    )
                    self.reports[pending_job.job_id()] = {
                        "time": current,
                        "type": "retrieve",
                    }
                    try:
                        counts, exceptions = get_counts_and_exceptions(
                            result=pending_job.result(),
                            result_idx_list=[rk - pcircs[0] for rk in pcircs],
                        )
                    except IBMError as e:
                        counts, exceptions = [{}], {pending_job.job_id(): e}
                else:
                    pendingpool_progressbar.set_description_str(
                        f"{pk} failed - No available tags", refresh=True
                    )

                    counts, exceptions = get_counts_and_exceptions(
                        result=None, result_idx_list=[rk - pcircs[0] for rk in pcircs]
                    )
                    pendingpool_progressbar.set_description_str(
                        f"{pk} failed - No available tags - {len(counts)}", refresh=True
                    )
                for rk in pcircs:
                    couts_tmp_container[rk] = counts[rk - pcircs[0]]
                    pendingpool_progressbar.set_description_str(
                        f"{pk} - Packing: {rk} with len {len(counts[rk - pcircs[0]])}",
                        refresh=True,
                    )
                if len(exceptions) > 0:
                    if "exceptions" not in self.current_multimanager.outfields:
                        self.current_multimanager.outfields["exceptions"] = {}
                    for result_id, exception_item in exceptions.items():
                        self.current_multimanager.outfields["exceptions"][
                            result_id
                        ] = exception_item
            else:
                warnings.warn(f"Pending pool '{pk}' is empty.")

        distributing_progressbar = qurry_progressbar(
            self.current_multimanager.beforewards.circuits_map.items(),
            bar_format=(
                "| {n_fmt}/{total_fmt} - Distributing {desc} - {elapsed} < {remaining}"
            ),
            # leave=False,
        )
        for current_id, idx_circs in distributing_progressbar:
            distributing_progressbar.set_description_str(
                f"{current_id} with {len(idx_circs)} circuits", refresh=True
            )
            self.experiment_container[current_id].reset_counts(
                summoner_id=self.current_multimanager.summoner_id
            )
            for idx in idx_circs:
                self.experiment_container[current_id].afterwards.counts.append(
                    couts_tmp_container[idx]
                )
            self.experiment_container[current_id].commons.datetimes[
                retrieve_times_name
            ] = current
            self.current_multimanager.afterwards.allCounts[
                current_id
            ] = self.experiment_container[current_id].afterwards.counts

        return self.current_multimanager.beforewards.job_id
