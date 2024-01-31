"""
================================================================
Waves Qurry Analysis (:mod:`qurry.qurrium.wavesqurry.analysis`)
================================================================

It is only for pendings and retrieve to remote backend.
"""

from typing import NamedTuple, Iterable

from ..analysis import AnalysisPrototype


class WavesQurryAnalysis(AnalysisPrototype):
    """The analysis of the experiment."""

    __name__ = "WavesQurryAnalysis"

    class AnalysisInput(NamedTuple):
        """To set the analysis."""

        ultimate_question: str
        """ULtImAte QueStIoN."""

    class AnalysisContent(NamedTuple):
        """Analysis content."""

        utlmatic_answer: int
        """~The Answer to the Ultimate Question of Life, The Universe, and Everything.~"""
        dummy: int
        """Just a dummy field."""

    @property
    def default_side_product_fields(self) -> Iterable[str]:
        """The fields that will be stored as side product."""
        return ["dummy"]
