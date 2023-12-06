"""
================================================================
The experiment prototype which is the basic class of all experiments.
(:mod:`qurry.qurrium.experiment`)
================================================================

"""
import gc
import os
import json
import warnings
from abc import abstractmethod, abstractproperty, ABC
from uuid import uuid4, UUID
from typing import Union, Optional, NamedTuple, Hashable, Type, Any
from pathlib import Path

from ...tools import ProcessManager, DEFAULT_POOL_SIZE
from ...tools.datetime import current_time, DatetimeDict
from ...capsule import jsonablize, quickJSON
from ...capsule.hoshi import Hoshi
from ...exceptions import (
    QurryInvalidInherition,
    QurryExperimentCountsNotCompleted,
    QurryResetSecurityActivated,
    QurryResetAccomplished,
    QurryProtectContent,
    QurrySummonerInfoIncompletion,
    QurryInvalidArgument,
)
from ..analysis import AnalysisPrototype, QurryAnalysis
from .container import (
    Arguments as ExperimentArgs,
    Commonparams as ExperimentCommonparams,
    Before as ExperimentBefore,
    After as ExperimentAfter,
)
from .analyses import AnalysesContainer
from .export import Export


class ExperimentPrototypeABC(ABC):
    """The experiment prototype which is the basic class of all experiments."""

    @abstractmethod
    class Arguments(NamedTuple):
        """Construct the experiment's parameters for specific options,
        which is overwritable by the inherition class."""

        exp_name: str


class ExperimentPrototype(ExperimentPrototypeABC):
    """The instance of experiment."""

    __name__ = "ExperimentPrototype"
    """Name of the QurryExperiment which could be overwritten."""

    # Experiment Property
    Arguments = ExperimentArgs
    Commonparams = ExperimentCommonparams
    Before = ExperimentBefore
    After = ExperimentAfter

    _unexports = ["side_product", "result"]
    """Unexports properties.
    """
    _deprecated = ["figTranspiled"]
    """Deprecated properties.
        - `figTranspiled` is deprecated since v0.6.0.
    """
    tqdm_handleable = False
    """Whether the method :meth:`
    e` can handle the processing bar from :module:`tqdm`."""

    # Analysis Property
    @classmethod
    def filter(cls, *args, **kwargs) -> tuple[Arguments, Commonparams, dict[str, Any]]:
        """Filter the arguments of experiment.

        Raises:
            ValueError: When input arguments are not positional arguments.

        Returns:
            tuple[argsCore, dict[str, Any]]: argsCore, outfields for other unused arguments.
        """
        if len(args) > 0:
            raise ValueError(
                "args filter can't be initialized with positional arguments."
            )
        infields = {}
        commonsinput = {}
        outfields = {}
        for k, v in kwargs.items():
            if k in cls.Arguments._fields:
                infields[k] = v
            elif k in cls.Commonparams._fields:
                commonsinput[k] = v
            else:
                outfields[k] = v

        return cls.Arguments(**infields), cls.Commonparams(**commonsinput), outfields

    # analysis
    @classmethod
    @abstractproperty
    def analysis_container(cls) -> Type[AnalysisPrototype]:
        """The container of analysis,
        it should be overwritten by each construction of new measurement.
        """

    def __init__(
        self,
        exp_id: str,
        wave_key: Hashable,
        *args,
        serial: Optional[int] = None,
        summoner_id: Optional[str] = None,
        summoner_name: Optional[str] = None,
        beforewards: Optional[ExperimentBefore] = None,
        afterwards: Optional[ExperimentAfter] = None,
        reports: Optional[AnalysesContainer] = None,
        **kwargs,
    ) -> None:
        """Initialize the experiment."""

        if len(args) > 0:
            raise ValueError(
                f"{self.__name__} can't be initialized with positional arguments."
            )
        try:
            if exp_id is not None:
                UUID(exp_id, version=4)
        except ValueError as e:
            exp_id = None
            warnings.warn(
                f"exp_id is not a valid UUID, it will be generated automatically.\n{e}",
                category=QurryInvalidArgument,
            )
        finally:
            if exp_id is None:
                exp_id = str(uuid4())
            else:
                ...

        for i in ["AnalysisInput", "AnalysisContent"]:
            if not hasattr(self.analysis_container, i):
                raise QurryInvalidInherition(
                    f"{self.__name__}._analysis_container() "
                    + f"should be inherited from {AnalysisPrototype.__name__}."
                )
        if "exp_name" not in self.Arguments._fields:
            raise QurryInvalidInherition(
                f"{self.__name__}.arguments should have 'exp_name'."
            )
        duplicate_fields = set(self.Arguments._fields) & set(self.Commonparams._fields)
        if len(duplicate_fields) > 0:
            raise QurryInvalidInherition(
                f"{self.__name__}.arguments and {self.__name__}.commonparams "
                + f"should not have same fields: {duplicate_fields}."
            )

        params = {}
        commons = {}
        outfields = {}
        for k, v in kwargs.items():
            if k in self.Arguments._fields:
                params[k] = v
            elif k in self.Commonparams._fields:
                commons[k] = v
            else:
                outfields[k] = v

        # Dealing special arguments
        if "datetimes" not in commons:
            commons["datetimes"] = DatetimeDict({"bulid": current_time()})
        else:
            commons["datetimes"] = DatetimeDict(commons["datetimes"])
        if "default_analysis" in commons:
            filted_analysis = []
            for raw_input_analysis in commons["default_analysis"]:
                if isinstance(raw_input_analysis, dict):
                    filted_analysis.append(
                        self.analysis_container.input_filter(**raw_input_analysis)[
                            0
                        ]._asdict()
                    )
                elif isinstance(
                    raw_input_analysis, self.analysis_container.AnalysisInput
                ):
                    filted_analysis.append(raw_input_analysis._asdict())
                else:
                    warnings.warn(
                        f"Analysis input {raw_input_analysis} is not a 'dict' or "
                        + "'.analysis_container.AnalysisInput', it will be ignored."
                    )
            commons["default_analysis"] = filted_analysis
        else:
            commons["default_analysis"] = []
        if "tags" in commons:
            if isinstance(commons["tags"], list):
                commons["tags"] = tuple(commons["tags"])

        self.args: self.Arguments = self.Arguments(**params)
        self.commons = self.Commonparams(
            exp_id=exp_id,
            serial=serial,
            wave_key=wave_key,
            summoner_id=summoner_id,
            summoner_name=summoner_name,
            **commons,
        )
        self.outfields: dict[str, Any] = outfields
        self.beforewards = (
            beforewards
            if isinstance(beforewards, self.Before)
            else self.Before(
                circuit=[],
                fig_original=[],
                job_id="",
                exp_name=self.args.exp_name,
                side_product={},
            )
        )
        self.afterwards = (
            afterwards
            if isinstance(afterwards, self.After)
            else self.After(
                result=[],
                counts=[],
            )
        )
        self.reports = (
            reports if isinstance(reports, AnalysesContainer) else AnalysesContainer()
        )

        _summon_check = {
            "serial": self.commons.serial,
            "summoner_id": self.commons.summoner_id,
            "summoner_name": self.commons.summoner_name,
        }
        _summon_detect = any((not v is None) for v in _summon_check.values())
        _summon_fulfill = all((not v is None) for v in _summon_check.values())
        if _summon_detect:
            if not _summon_fulfill:
                summon_msg = Hoshi(ljust_description_len=20)
                summon_msg.newline(("divider",))
                summon_msg.newline(("h3", "Summoner Info Incompletion"))
                summon_msg.newline(("itemize", "Summoner info detect.", _summon_detect))
                summon_msg.newline(
                    ("itemize", "Summoner info fulfilled.", _summon_fulfill)
                )
                for k, v in _summon_check.items():
                    summon_msg.newline(
                        ("itemize", k, str(v), f"fulfilled: {not v is None}", 2)
                    )
                warnings.warn(
                    "Summoner data is not completed, it will export in single experiment mode.",
                    category=QurrySummonerInfoIncompletion,
                )
                summon_msg.print()

        self.after_lock = False
        """Protect the :cls:`afterward` content to be overwritten. 
        When setitem is called and completed, it will be setted as `False` automatically.
        """
        self.mute_auto_lock = False
        """Whether mute the auto-lock message."""

    def reset_counts(self, summoner_id: str) -> None:
        """Reset the counts of the experiment."""
        if summoner_id == self.commons.summoner_id:
            self.afterwards = self.afterwards._replace(counts=[])
            gc.collect()
        else:
            warnings.warn(
                "The summoner_id is not matched, "
                + "the counts will not be reset, it can only be activated by multimanager.",
                category=QurryResetSecurityActivated,
            )

    def unlock_afterward(self, mute_auto_lock: bool = False):
        """Unlock the :cls:`afterward` content to be overwritten.

        Args:
            mute_auto_lock (bool, optional):
                Mute anto-locked message for the unlock of this time. Defaults to False.
        """
        self.after_lock = True
        self.mute_auto_lock = mute_auto_lock

    def __setitem__(self, key, value) -> None:
        if key in self.beforewards._fields:
            self.beforewards = self.beforewards._replace(**{key: value})

        elif key in self.afterwards._fields:
            if self.after_lock and isinstance(self.after_lock, bool):
                self.afterwards = self.afterwards._replace(**{key: value})
            else:
                raise QurryProtectContent(
                    f"Can't set value to :cls:`afterward` field {key} "
                    + "because it's locked, use `.unlock_afterward()` "
                    + "to unlock before setting item ."
                )

        elif key in self._deprecated:
            ...
            # print(f"| Warning: {key} is deprecated.")

        else:
            raise ValueError(
                f"{key} is not a valid field of "
                + f"'{self.Before.__name__}' and '{self.After.__name__}'."
            )

        gc.collect()
        if self.after_lock is not False:
            self.after_lock = False
            if not self.mute_auto_lock:
                print(
                    "after_lock is locked automatically now, you can unlock by "
                    + "using `.unlock_afterward()` to set value to :cls:`afterward`."
                )
            self.mute_auto_lock = False

    def __getitem__(self, key) -> Any:
        if key in self.beforewards._fields:
            return getattr(self.beforewards, key)
        if key in self.afterwards._fields:
            return getattr(self.afterwards, key)
        if key in self._deprecated:
            warnings.warn("This property is deprecated.", DeprecationWarning)
            return "Deprecated"
        raise ValueError(
            f"{key} is not a valid field of "
            + f"'{self.Before.__name__}' and '{self.After.__name__}'."
        )

    # analysis
    @classmethod
    @abstractmethod
    def quantities(cls) -> dict[str, Any]:
        """Computing specific squantity.
        Where should be overwritten by each construction of new measurement.
        """

    @abstractmethod
    def analyze(self) -> AnalysisPrototype:
        """Analyzing the example circuit results in specific method.

        Args:
            allArgs: all arguments will pass to `.quantities`.

        Returns:
            analysis: Analysis of the counts from measurement.
        """

    def clear_analysis(self, *args, security: bool = False, mute: bool = False) -> None:
        """Reset the measurement and release memory.

        Args:
            args (any):
                Positional arguments handler to protect other keyword arguments.
                It's useless, umm...😐
            security (bool, optional): Security for reset. Defaults to `False`.
            mute (bool, optional): Mute the warning when reset activated. Defaults to `False`.
        """

        if security and isinstance(security, bool):
            self.reports = AnalysesContainer()
            gc.collect()
            if not mute:
                warnings.warn(
                    "The measurement has reset and release memory allocating.",
                    category=QurryResetAccomplished,
                )
        else:
            warnings.warn(
                "Reset does not execute to prevent executing accidentally, "
                + "if you are sure to do this, then use '.reset(security=True)'."
                + (
                    "Attention: any position arguments are not available on this method."
                    if len(args) > 0
                    else ""
                ),
                category=QurryResetSecurityActivated,
            )

    # show info
    def __hash__(self) -> int:
        return hash(self.commons.exp_id)

    # pylint: disable=invalid-name

    @property
    def exp_id(self) -> property:
        """ID of experiment."""
        return self.commons.exp_id

    # pylint: enable=invalid-name

    def __repr__(self) -> str:
        return (
            f"<{self.__name__} with exp_id={self.commons.exp_id}, "
            + f"{self.args.__repr__()}, "
            + f"{self.commons.__repr__()}, "
            + f"{len(self.outfields)} unused arguments, "
            + f"{len(self.Before._fields)} preparing dates, "
            + f"{len(self.After._fields)} experiment result datasets, "
            + f"and {len(self.reports)} analysis>"
        )

    def statesheet(
        self,
        report_expanded: bool = False,
        hoshi: bool = False,
    ) -> Hoshi:
        """Show the state of experiment.

        Args:
            report_expanded (bool, optional): Show more infomation. Defaults to False.
            hoshi (bool, optional): Showing name of Hoshi. Defaults to False.

        Returns:
            Hoshi: Statesheet of experiment.
        """

        info = Hoshi(
            [
                ("h1", f"{self.__name__} with exp_id={self.commons.exp_id}"),
            ],
            name="Hoshi" if hoshi else "QurryExperimentSheet",
        )
        info.newline(("itemize", "arguments"))
        for k, v in self.args._asdict().items():
            info.newline(("itemize", str(k), str(v), "", 2))

        info.newline(("itemize", "commonparams"))
        for k, v in self.commons._asdict().items():
            info.newline(
                (
                    "itemize",
                    str(k),
                    str(v),
                    (
                        ""
                        if k != "exp_id"
                        else "This is ID is generated by Qurry "
                        + "which is different from 'job_id' for pending."
                    ),
                    2,
                )
            )

        info.newline(
            (
                "itemize",
                "outfields",
                len(self.outfields),
                "Number of unused arguments.",
                1,
            )
        )
        for k, v in self.outfields.items():
            info.newline(("itemize", str(k), v, "", 2))

        info.newline(("itemize", "beforewards"))
        for k, v in self.beforewards._asdict().items():
            if isinstance(v, str):
                info.newline(("itemize", str(k), str(v), "", 2))
            else:
                info.newline(("itemize", str(k), len(v), f"Number of {k}", 2))

        info.newline(("itemize", "afterwards"))
        for k, v in self.afterwards._asdict().items():
            if k == "job_id":
                info.newline(
                    (
                        "itemize",
                        str(k),
                        str(v),
                        "If it's null meaning this experiment "
                        + "doesn't use online backend like IBMQ.",
                        2,
                    )
                )
            elif isinstance(v, str):
                info.newline(("itemize", str(k), str(v), "", 2))
            else:
                info.newline(("itemize", str(k), len(v), f"Number of {k}", 2))

        info.newline(
            ("itemize", "reports", len(self.reports), "Number of analysis.", 1)
        )
        if report_expanded:
            for ser, item in self.reports.items():
                info.newline(
                    (
                        "itemize",
                        "serial",
                        f"k={ser}, serial={item.header.serial}",
                        None,
                        2,
                    )
                )
                info.newline(("txt", item, 3))

        return info

    # Export

    _rjust_len = 3
    """The length of the string to be right-justified for serial number 
    when :prop:`exp_name` is duplicated."""
    _required_folder = ["args", "advent", "legacy", "tales", "reports"]
    """Folder for saving exported files."""

    def export(self) -> Export:
        """Export the data of experiment.

        For the `.write` function actually exports 4 different files
        respecting to `adventure`, `legacy`, `tales`, and `reports` like:

        ```python
        files = {
            'folder': './blabla_experiment/',
            'qurryinfo': './blabla_experiment/qurryinfo.json',

            'args': './blabla_experiment/args/blabla_experiment.id={exp_id}.args.json',
            'advent': './blabla_experiment/advent/blabla_experiment.id={exp_id}.advent.json',
            'legacy': './blabla_experiment/legacy/blabla_experiment.id={exp_id}.legacy.json',
            'tales.dummyx1': './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyx1.json',
            'tales.dummyx2': './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyx2.json',
            ...
            'tales.dummyxn': './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyxn.json',
            'reports': ./blabla_experiment/reports/blabla_experiment.id={exp_id}.reports.json,
            'reports.tales.dummyz1':
                './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyz1.reports.json',
            'reports.tales.dummyz2':
                './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyz2.reports.json',
            ...
            'reports.tales.dummyzm':
                './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyzm.reports.json',
        }
        ```
        which `blabla_experiment` is the example filename.
        If this experiment is called by :cls:`multimanager`,
        then the it will be named after `summoner_name` as known as the name of :cls:`multimanager`.

        ```python
        files = {
            'folder': './BLABLA_project/',
            'qurryinfo': './BLABLA_project/qurryinfo.json',

            'args': './BLABLA_project/args/index={serial}.id={exp_id}.args.json',
            'advent': './BLABLA_project/advent/index={serial}.id={exp_id}.advent.json',
            'legacy': './BLABLA_project/legacy/index={serial}.id={exp_id}.legacy.json',
            'tales.dummyx1': './BLABLA_project/tales/index={serial}.id={exp_id}.dummyx1.json',
            'tales.dummyx2': './BLABLA_project/tales/index={serial}.id={exp_id}.dummyx2.json',
            ...
            'tales.dummyxn': './BLABLA_project/tales/index={serial}.id={exp_id}.dummyxn.json',
            'reports': ./BLABLA_project/reports/index={serial}.id={exp_id}.reports.json,
            'reports.tales.dummyz1':
                './BLABLA_project/tales/index={serial}.id={exp_id}.dummyz1.reports.json',
            'reports.tales.dummyz2':
                './BLABLA_project/tales/index={serial}.id={exp_id}.dummyz2.reports.json',
            ...
            'reports.tales.dummyzm':
                './BLABLA_project/tales/index={serial}.id={exp_id}.dummyzm.reports.json',
        }
        ```
        which `BLBLA_project` is the example :cls:`multimanager` name
        stored at :prop:`commonparams.summoner_name`.
        At this senerio, the `exp_name` will never apply as filename.

        - reports formats.

        ```
        reports = {
            1: { ...quantities, 'input': { ... }, 'header': { ... }, },
            2: { ...quantities, 'input': { ... }, 'header': { ... }, },
            ...
            {serial}: { ...quantities, 'input': { ... }, 'header': { ... }, },
        }
        ```

        - tales_reports formats.

        ```
        tales_reports = {
            'dummyz1': {
                1: { ... },
                2: { ... },
                ...
                {serial}: { ... },
            },
            'dummyz2': {
                1: { ... },
                2: { ... },
                ...
                {serial}: { ... },
            },
            ...
            'dummyz': {
                1: { ... },
                2: { ... },
                ...
                {serial}: { ... },
            },
        }
        ```

        Returns:
            Export: A namedtuple containing the data of experiment
                which can be more easily to export as json file.
        """

        # args, commons, outfields

        # commons: dict[str, Any] = jsonablize(self.commons._asdict())
        # commons["backend"] = (
        #     self.commons.backend
        #     if isinstance(self.commons.backend, str)
        #     else backendName(self.commons.backend)
        # )

        # adventures, legacy, tales
        # tales: dict[str, str] = {}
        # adventures = {}
        # for k, v in self.beforewards._asdict().items():
        #     if k == "side_product":
        #         tales = {**tales, **v}
        #     elif k in self._unexports:
        #         ...
        #     else:
        #         adventures[k] = v
        # gc.collect()
        adventures, tales = self.beforewards.export(unexports=self._unexports)

        # legacy = {}
        # for k, v in self.afterwards._asdict().items():
        #     if k == "side_product":
        #         tales = {**tales, **v}
        #     elif k in self._unexports:
        #         ...
        #     else:
        #         legacy[k] = v
        # gc.collect()
        legacy = self.afterwards.export(unexports=self._unexports)

        # reports
        # reports: dict[str, dict[str, Any]] = {}  # reports formats.
        # # tales_reports formats.
        # tales_reports: dict[str, dict[str, dict[str, Any]]] = {}
        # for k, al in self.reports.items():
        #     report_main, report_tales = al.export()
        #     reports[k] = report_main
        #     for tk, tv in report_tales.items():
        #         if tk not in tales_reports:
        #             tales_reports[tk] = {}
        #         tales_reports[tk][k] = tv

        reports, tales_reports = self.reports.export()

        # filename
        filename = ""
        folder = ""

        # multi-experiment mode
        if all(
            (not v is None)
            for v in [
                self.commons.serial,
                self.commons.summoner_id,
                self.commons.summoner_id,
            ]
        ):
            folder += f"./{self.commons.summoner_name}/"
            filename += f"index={self.commons.serial}.id={self.commons.exp_id}"
        else:
            repeat_times = 1
            tmp = (
                folder
                + f"./{self.beforewards.exp_name}.{str(repeat_times).rjust(self._rjust_len, '0')}/"
            )
            while os.path.exists(tmp):
                repeat_times += 1
                tmp = (
                    folder
                    + f"./{self.beforewards.exp_name}."
                    + f"{str(repeat_times).rjust(self._rjust_len, '0')}/"
                )
            folder = tmp
            filename += (
                f"{self.beforewards.exp_name}."
                + f"{str(repeat_times).rjust(self._rjust_len, '0')}.id={self.commons.exp_id}"
            )

        self.commons = self.commons._replace(filename=filename)
        files = {
            "folder": folder,
            "qurryinfo": folder + "qurryinfo.json",
            "args": folder + f"args/{filename}.args.json",
            "advent": folder + f"advent/{filename}.advent.json",
            "legacy": folder + f"legacy/{filename}.legacy.json",
        }
        for k in tales:
            files[f"tales.{k}"] = folder + f"tales/{filename}.{k}.json"
        files["reports"] = folder + f"reports/{filename}.reports.json"
        for k in tales_reports:
            files[f"reports.tales.{k}"] = folder + f"tales/{filename}.{k}.reports.json"

        return Export(
            exp_id=self.commons.exp_id,
            exp_name=self.beforewards.exp_name,
            serial=self.commons.serial,
            summoner_id=self.commons.summoner_id,
            summoner_name=self.commons.summoner_name,
            filename=filename,
            files={k: str(Path(v)) for k, v in files.items()},
            args=jsonablize(self.args._asdict()),
            commons=self.commons.export(),
            outfields=jsonablize(self.outfields),
            adventures=jsonablize(adventures),
            legacy=jsonablize(legacy),
            tales=jsonablize(tales),
            reports=reports,
            tales_reports=tales_reports,
        )

    def write(
        self,
        save_location: Optional[Union[Path, str]] = None,
        mode: str = "w+",
        indent: int = 2,
        encoding: str = "utf-8",
        jsonable: bool = False,
        # zip: bool = False,
        mute: bool = False,
        _qurryinfo_hold_access: Optional[str] = None,
    ) -> tuple[str, dict[str, str]]:
        """Export the experiment data, if there is a previous export, then will overwrite.

        - example of filename:

        ```python
        files = {
            'folder': './blabla_experiment/',
            'qurrtinfo': './blabla_experiment/qurrtinfo',

            'args': './blabla_experiment/args/blabla_experiment.id={exp_id}.args.json',
            'advent': './blabla_experiment/advent/blabla_experiment.id={exp_id}.advent.json',
            'legacy': './blabla_experiment/legacy/blabla_experiment.id={exp_id}.legacy.json',
            'tales.dummyx1': './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyx1.json',
            'tales.dummyx2': './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyx2.json',
            ...
            'tales.dummyxn': './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyxn.json',
            'reports': ./blabla_experiment/reports/blabla_experiment.id={exp_id}.reports.json,
            'reports.tales.dummyz1':
                './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyz1.reports.json',
            'reports.tales.dummyz2':
                './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyz2.reports.json',
            ...
            'reports.tales.dummyzm':
                './blabla_experiment/tales/blabla_experiment.id={exp_id}.dummyzm.reports.json',
        }
        ```

        Args:
            save_location (Optional[Union[Path, str]], optional):
                Where to save the export content as `json` file.
                If `save_location == None`, then use the value in `self.commons` to be exported,
                if it's None too, then raise error.
                Defaults to `None`.

            mode (str):
                Mode for :func:`open` function, for :func:`mori.quickJSON`. Defaults to 'w+'.
            indent (int, optional):
                Indent length for json, for :func:`mori.quickJSON`. Defaults to 2.
            encoding (str, optional):
                Encoding method, for :func:`mori.quickJSON`. Defaults to 'utf-8'.
            jsonable (bool, optional):
                Whether to transpile all object to jsonable via :func:`mori.jsonablize`,
                for :func:`mori.quickJSON`. Defaults to False.
            mute (bool, optional):
                Whether to mute the output, for :func:`mori.quickJSON`. Defaults to False.
            _qurryinfo_hold_access (str, optional):
                Whether to hold the I/O of `qurryinfo`, then export by :cls:`multimanager`,
                it should be control by :cls:`multimanager`.
                Defaults to None.

        Returns:
            dict[any]: the export content.
        """

        if isinstance(save_location, Path):
            ...
        elif isinstance(save_location, str):
            save_location = Path(save_location)
        elif save_location is None:
            save_location = Path(self.commons.save_location)
            if self.commons.save_location is None:
                raise ValueError(
                    "save_location is None, please provide a valid save_location"
                )
        else:
            raise TypeError(
                f"save_location must be Path or str, not {type(save_location)}"
            )

        if self.commons.save_location != save_location:
            self.commons = self.commons._replace(save_location=save_location)

        export_material = self.export()
        for k, v in export_material.files.items():
            self.commons.files[k] = v

        export_set = {}
        # qurryinfo ..........  # file location, dedicated hash
        qurryinfo = {
            export_material.exp_id: export_material.files,
        }
        # args ...............  # arguments, commonparams, outfields, files
        export_set["args"] = {
            "arguments": export_material.args,
            "commonparams": export_material.commons,
            "outfields": export_material.outfields,
            "files": export_material.files,
        }
        # advent .............  # adventures
        export_set["advent"] = {
            "files": export_material.files,
            "adventures": export_material.adventures,
        }
        # legacy .............  # legacy
        export_set["legacy"] = {
            "files": export_material.files,
            "legacy": export_material.legacy,
        }
        # tales ..............  # tales
        for tk, tv in export_material.tales.items():
            if isinstance(tv, (dict, list, tuple)):
                export_set[f"tales.{tk}"] = tv
            else:
                export_set[f"tales.{tk}"] = [tv]
            if f"tales.{tk}" not in export_material.files:
                warnings.warn(f"tales.{tk} is not in export_names, it's not exported.")
        # reports ............  # reports
        export_set["reports"] = {
            "files": export_material.files,
            "reports": export_material.reports,
        }
        # reports.tales ......  # tales_reports
        for tk, tv in export_material.tales_reports.items():
            if isinstance(tv, (dict, list, tuple)):
                export_set[f"reports.tales.{tk}"] = tv
            else:
                export_set[f"reports.tales.{tk}"] = [tv]
            if f"reports.tales.{tk}" not in export_material.files:
                warnings.warn(
                    f"reports.tales.{tk} is not in export_names, it's not exported."
                )
        # Exportation
        folder = save_location / Path(export_material.files["folder"])
        if not os.path.exists(folder):
            os.mkdir(folder)
        for k in self._required_folder:
            if not os.path.exists(folder / k):
                os.mkdir(folder / k)

        for filekey, content in list(export_set.items()) + [("qurryinfo", qurryinfo)]:
            # Exportation of qurryinfo
            if filekey == "qurryinfo":
                if (
                    _qurryinfo_hold_access == self.commons.summoner_id
                    and self.commons.summoner_id is not None
                ):
                    ...
                elif os.path.exists(save_location / export_material.files["qurryinfo"]):
                    with open(
                        save_location / export_material.files["qurryinfo"],
                        "r",
                        encoding="utf-8",
                    ) as f:
                        qurryinfo_found: dict[str, dict[str, str]] = json.load(f)
                        content = {**qurryinfo_found, **content}

            quickJSON(
                content=content,
                filename=str(save_location / export_material.files[filekey]),
                mode=mode,
                indent=indent,
                encoding=encoding,
                jsonable=jsonable,
                mute=mute,
            )

        all_files_location = export_material.files.copy()
        del export_set
        del export_material
        gc.collect()

        return self.commons.exp_id, all_files_location

    @classmethod
    def _read_core(
        cls,
        exp_id: str,
        file_index: dict[str, str],
        save_location: Union[Path, str] = Path("./"),
        encoding: str = "utf-8",
    ) -> "ExperimentPrototype":
        """Core of read function.

        Args:
            exp_id (str): The id of the experiment to be read.
            file_index (dict[str, str]): The index of the experiment to be read.
            save_location (Union[Path, str]): The location of the experiment to be read.
            encoding (str): Encoding method, for :func:`mori.quickJSON`.

        Raises:
            ValueError: 'save_location' needs to be the type of 'str' or 'Path'.
            FileNotFoundError: When `save_location` is not available.

        Returns:
            QurryExperiment: The experiment to be read.
        """

        if isinstance(save_location, (Path, str)):
            save_location = Path(save_location)
        else:
            raise ValueError("'save_location' needs to be the type of 'str' or 'Path'.")
        if not os.path.exists(save_location):
            raise FileNotFoundError(
                f"'save_location' does not exist, '{save_location}'."
            )

        # Construct the experiment
        # arguments, commonparams, outfields
        export_material_set = {}
        (
            export_material_set["arguments"],
            export_material_set["commonparams"],
            export_material_set["outfields"],
        ) = cls.Commonparams.read_as_dict(
            exp_id=exp_id,
            file_index=file_index,
            save_location=save_location,
            encoding=encoding,
        )
        instance = cls(
            **export_material_set["commonparams"],
            **export_material_set["arguments"],
            **export_material_set["outfields"],
            beforewards=cls.Before.read(
                file_index=file_index, save_location=save_location, encoding=encoding
            ),
            afterwards=cls.After.read(
                file_index=file_index, save_location=save_location, encoding=encoding
            ),
            reports=AnalysesContainer(
                **cls.analysis_container.read(
                    file_index=file_index,
                    save_location=save_location,
                    encoding=encoding,
                )
            ),
        )
        return instance

    @classmethod
    def read(
        cls,
        name_or_id: Union[Path, str],
        save_location: Union[Path, str] = Path("./"),
        encoding: str = "utf-8",
        workers_num: Optional[int] = None,
    ) -> list["ExperimentPrototype"]:
        """Read the experiment from file.
        Replacement of :func:`QurryV4().readLegacy`

        Args:
            name_or_id (Union[Path, str]):
                The name or id of the experiment to be read.
            save_location (Union[Path, str], optional):
                The location of the experiment to be read.
                Defaults to Path('./').
            indent (int, optional):
                Indent length for json, for :func:`mori.quickJSON`. Defaults to 2.
            encoding (str, optional):
                Encoding method, for :func:`mori.quickJSON`. Defaults to 'utf-8'.

        Raises:
            ValueError: 'save_location' needs to be the type of 'str' or 'Path'.
            FileNotFoundError: When `save_location` is not available.

        """

        if isinstance(save_location, (Path, str)):
            save_location = Path(save_location)
        else:
            raise ValueError("'save_location' needs to be the type of 'str' or 'Path'.")
        if not os.path.exists(save_location):
            raise FileNotFoundError(
                f"'save_location' does not exist, '{save_location}'."
            )

        export_location = save_location / name_or_id
        if not os.path.exists(export_location):
            raise FileNotFoundError(
                f"'ExportLoaction' does not exist, '{export_location}'."
            )

        qurryinfo: dict[str, dict[str, str]] = {}
        qurryinfo_location = export_location / "qurryinfo.json"
        if not os.path.exists(qurryinfo_location):
            raise FileNotFoundError(
                f"'qurryinfo.json' does not exist at '{save_location}'. "
                + "It's required for loading all experiment data."
            )

        with open(qurryinfo_location, "r", encoding=encoding) as f:
            qurryinfo_found: dict[str, dict[str, str]] = json.load(f)
            qurryinfo = {**qurryinfo_found, **qurryinfo}

        if workers_num is None:
            workers_num = DEFAULT_POOL_SIZE
        pool = ProcessManager(workers_num)

        print(
            f"| {len(qurryinfo)} experiments found, loading by {workers_num} workers."
        )
        quene = pool.starmap(
            cls._read_core,
            [
                (exp_id, fileIndex, save_location, encoding)
                for exp_id, fileIndex in qurryinfo.items()
            ],
        )

        return quene


class QurryExperiment(ExperimentPrototype):
    """Experiment instance for QurryV5."""

    __name__ = "QurryExperiment"

    class Arguments(NamedTuple):
        """Construct the experiment's parameters for specific options,
        which is overwritable by the inherition class.
        """

        exp_name: str = "exps"
        sampling: int = 1

    @classmethod
    @property
    def analysis_container(cls) -> Type[QurryAnalysis]:
        return QurryAnalysis

    @classmethod
    def quantities(
        cls,
        shots: int = None,
        counts: list[dict[str, int]] = None,
        ultimate_question: str = "",
    ) -> dict[str, float]:
        """Computing specific squantity.
        Where should be overwritten by each construction of new measurement.

        Returns:
            dict[str, float]: Counts, purity, entropy of experiment.
        """

        if shots is None or counts is None:
            print(
                "| shots or counts is None, "
                + "but it doesn't matter with ultimate question over all."
            )
        print("| ultimate_question:", ultimate_question)
        dummy = -100
        utlmatic_answer = (42,)
        return {
            "dummy": dummy,
            "utlmatic_answer": utlmatic_answer,
        }

    def analyze(
        self,
        ultimate_question: str = "",
        shots: Optional[int] = None,
    ):
        """Analysis of the experiment.
        Where should be overwritten by each construction of new measurement.
        """

        if shots is None:
            shots = self.commons.shots
        if len(self.afterwards.counts) < 1:
            raise QurryExperimentCountsNotCompleted(
                "The counts of the experiment is not completed. So there is no data to analyze."
            )

        qs = self.quantities(
            shots=shots,
            counts=self.afterwards.counts,
            ultimate_question=ultimate_question,
        )

        serial = len(self.reports)
        analysis = self.analysis_container(
            ultimate_question=ultimate_question,
            serial=serial,
            **qs,
        )

        self.reports[serial] = analysis
        return analysis
