from qiskit import QuantumCircuit
from qiskit.providers import Backend
from qiskit.providers.ibmq import IBMQBackend, IBMQJobManager, AccountProvider
from qiskit.providers.ibmq.managed import ManagedJobSet, IBMQJobManagerInvalidStateError
from qiskit.providers.ibmq.exceptions import IBMQError

from typing import Literal, NamedTuple, Any
from abc import abstractmethod

from .multimanager import MultiManager

class Runner:
    """Pending and Retrieve Jobs from remote backend."""
    
    currentManager: MultiManager
    backend: Backend

    pendingIDs: str
    reports: dict[str, dict]
    
    @abstractmethod
    def pending(self, *args, **kwargs):
        pass
    
    @abstractmethod
    def retrieve(self, *args, **kwargs):
        pass


# Using for Third-Party Backend

class ThirdPartyRunner(Runner):
    """Pending and Retrieve Jobs from Third-Parties' backend."""
    
    currentManager: MultiManager
    backend: Backend

    pendingIDs: str
    reports: dict[str, dict]

    def __init__(
        self, 
        manager: MultiManager, 
        backend: Backend,
        
        max_experiments: int = 200,
        **otherArgs: any
    ):
        self.currentManager = manager
        self.backend = backend
        self.circWithSerial = {}
        
    @abstractmethod
    def pending(self, *args, **kwargs):
        pass
    
    @abstractmethod
    def retrieve(self, *args, **kwargs):
        pass