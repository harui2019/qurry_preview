from ..experiment import ExperimentPrototype
from typing import Union, Optional, Hashable, MutableMapping

class ExperimentContainer(dict):
    
    @property
    def lastExp(self) -> Optional[ExperimentPrototype]:
        """The last experiment be called or used.
        Replace the property :prop:`waveNow`. in :cls:`QurryV4`"""
        if self.lastID == None:
            return None
        else:
            return self[self.lastID]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lastID = None
        

    def call(
        self: MutableMapping[Hashable, ExperimentPrototype],
        expID: Optional[Hashable] = None,
    ) -> ExperimentPrototype:
        """Export wave function as `QuantumCircuit`.

        Args:
            wave (Optional[Hashable], optional):
                The key of wave in 'fict' `.waves`.
                If `wave==None`, then chooses `.lastWave` automatically added by last calling of `.addWave`.
                Defaults to None.

        Returns:
            QuantumCircuit: The circuit of wave function.
        """
        
        if expID == None:
            expID = self.lastID
            
        if expID in self:
            self.lastID = expID
            return self[expID]
        else:
            raise KeyError(f"Wave {expID} not found in {self}")

    def __call__(
        self: MutableMapping[Hashable, ExperimentPrototype],
        expID: Union[list[Hashable], Hashable, None] = None,
    ) -> ExperimentPrototype:

        return self.call(expID=expID)