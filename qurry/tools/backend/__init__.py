"""
================================================================
Backend tools for Qurry. (:mod:`qurry.tools.backend`)
================================================================

"""
from .import_manage import (
    DummyProvider,
    IBM_AVAILABLE,
    IBMQ_AVAILABLE,
    shorten_name,
    version_check,
    backendName,
    _real_backend_loader,
    fack_backend_loader,
    IBMQ,
    IBMProvider,
    GeneralAerProvider,
    GeneralAerSimulator,
    GeneralAerBackend,
)
from .backend_manager import BackendWrapper, BackendManager
