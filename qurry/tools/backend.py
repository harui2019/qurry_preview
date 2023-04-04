from qiskit import __qiskit_version__
from qiskit.providers import Backend, BackendV1, BackendV2

try:
    from qiskit.providers.ibmq import AccountProvider
    from qiskit import IBMQ
    qiskit_ibmq_provider_deprecated = False
except ImportError:
    qiskit_ibmq_provider_deprecated = True

from qiskit_ibm_provider import IBMProvider
from qiskit_aer import AerProvider
from qiskit_aer.version import get_version_info as get_version_info_aer

import requests
import pkg_resources
from random import random
from typing import Optional, Hashable, Union

from .command import cmdWrapper, pytorchCUDACheck
from ..hoshi import Hoshi


def _local_version() -> dict[str, dict[str, any]]:
    installed_packages = pkg_resources.working_set
    local_version_dict = {}
    for i in installed_packages:
        if i.key == 'qiskit':
            local_version_dict[i.key] = {
                'dist': i,
                'local_version': i.version,
            }
        elif i.key == 'qiskit-aer-gpu':
            local_version_dict[i.key] = {
                'dist': i,
                'local_version': i.version,
            }
    return local_version_dict


def _version_check():
    """Version check to remind user to update qiskit if needed.
    """

    check_msg = Hoshi([
        ('divider', 60),
        ('h3', 'Qiskit version outdated warning'),
        ('txt', "Please keep mind on your qiskit version, a very outdated version may cause some problems.")
    ], ljust_describe_len=40)
    local_version_dict = _local_version()
    for k, v in local_version_dict.items():
        try:
            response = requests.get(f'https://pypi.org/pypi/{k}/json')
            latest_version = response.json()['info']['version']
            latest_version_tuple = tuple(map(int, latest_version.split('.')))
            local_version_tuple = tuple(
                map(int, v['local_version'].split('.')))

            if latest_version_tuple > local_version_tuple:
                check_msg.newline({
                    'type': 'itemize',
                    'description': f'{k}',
                    'value': f"{v['local_version']}/{latest_version}",
                    'hint': 'The Local version/The Latest version on PyPI.',
                })
        except Exception as e:
            check_msg.newline({
                'type': 'itemize',
                'description': f"Request error due to '{e}'",
                'value': None,
            })

    for k, v in __qiskit_version__.items():
        check_msg.newline({
            'type': 'itemize',
            'description': f'{k}',
            'value': str(v),
            'listing_level': 2
        })

    if 'qiskit-aer-gpu' in local_version_dict:
        check_msg.newline(
            ('txt', "If version of 'qiskit-aer' is not same with 'qiskit-aer-gpu', it may cause GPU backend not working."))
        check_msg.newline({
            'type': 'itemize',
            'description': 'qiskit-aer',
            'value': get_version_info_aer(),
        })
        check_msg.newline({
            'type': 'itemize',
            'description': 'qiskit-aer-gpu',
            'value': local_version_dict['qiskit-aer-gpu']['local_version'],
        })

    pytorchCUDACheck()

    return check_msg


def version_check():
    """Version check to remind user to update qiskit if needed.
    """
    check_msg = _version_check()
    print(check_msg)
    return check_msg


async def _async_version_check():
    """Version check to remind user to update qiskit if needed.
    """
    check_msg = _version_check()
    return check_msg


class backendWrapper:
    """A wrapper for :class:`qiskit.providers.Backend` to provide more convenient way to use.


    :cls:`QasmSimulator('qasm_simulator')` and :cls:`AerSimulator('aer_simulator')` are using same simulating methods.
    So call 'qasm_simulator' and 'aer_simulator' used in :meth:`Aer.get_backend` are a container of multiple method of simulation
    like 'statevector', 'density_matrix', 'stabilizer' ... which is not a name of simulating method.

    - :cls:`QasmSimulator('qasm_simulator')` has:

        `('automatic', 'statevector', 'density_matrix', 'stabilizer', 'matrix_product_state', 'extended_stabilizer')`

    - :cls:`AerSimulator('aer_simulator')`  has:

        `('automatic', 'statevector', 'density_matrix', 'stabilizer', 'matrix_product_state', 'extended_stabilizer', 'unitary', 'superop')`
        Even parts of method has GPU support by :module:`qiskit-aer-gpu`

    ```txt
    +--------------------------+---------------+
    | Method                   | GPU Supported |
    +==========================+===============+
    | ``automatic``            | Sometimes     |
    +--------------------------+---------------+
    | ``statevector``          | Yes           |
    +--------------------------+---------------+
    | ``density_matrix``       | Yes           |
    +--------------------------+---------------+
    | ``stabilizer``           | No            |
    +--------------------------+---------------+
    | ``matrix_product_state`` | No            |
    +--------------------------+---------------+
    | ``extended_stabilizer``  | No            |
    +--------------------------+---------------+
    | ``unitary``              | Yes           |
    +--------------------------+---------------+
    | ``superop``              | No            |
    +--------------------------+---------------+
    ```
    (from doc of :cls:`AerSimulator`)

    So this wrapper only call :cls:`AerSimulator('aer_simulator')` as simulator backend,
    and use :meth:`set_option` to get different backends.

    """

    isAerGPU = False

    @staticmethod
    def _shorten_name(
        name: str,
        drop: list[str] = [],
        exclude: list[str] = [],
    ) -> str:
        if name in exclude:
            return name

        drop = sorted(drop, key=len, reverse=True)
        for _s in drop:
            if _s in name:
                return name.replace(_s, "")

        return name

    @staticmethod
    def _hint_ibmq_sim(name: str) -> str:
        return 'ibm'+name if not 'ibm' in name else name

    def _update_callsign(self) -> None:
        self.backend_callsign = {
            **self.backend_ibmq_callsign,
            **self.backend_aer_callsign,
        }

    def _update_backend(self) -> None:
        self.backend = {
            **self.backend_ibmq,
            **self.backend_aer,
        }

    def __init__(
        self,
        realProvider: Optional[Union[IBMProvider, 'AccountProvider']] = None,
    ) -> None:

        self._AerProvider = AerProvider()
        self._AerOwnedBackends = self._AerProvider.backends()
        if 'GPU' in self._AerOwnedBackends[0].available_devices():
            self.isAerGPU = True

        self.backend_aer_callsign = {
            'state': 'statevector',
            'aer_state': 'aer_statevector',
            'aer_density': 'aer_density_matrix',

            'aer_state_gpu': 'aer_statevector_gpu',
            'aer_density_gpu': 'aer_density_matrix_gpu',
        }
        self.backend_aer: dict[str, Backend] = {
            self._shorten_name(b.name(), ['_simulator']): b for b in self._AerOwnedBackends if b.name() not in [
                # NOTE: Deprecated backend
                'qasm_simulator', 'statevector_simulator', 'unitary_simulator'
            ]
        }
        if self.isAerGPU:
            self.backend_aer = {
                "aer_gpu": self._AerOwnedBackends[0],
                **self.backend_aer,
            }
            self.backend_aer["aer_gpu"].set_options(device='GPU')

        self.backend_ibmq_callsign = {}
        self.backend_ibmq = {}
        self._RealProvider = None
        if not realProvider is None:
            self._RealProvider = IBMProvider
            if isinstance(realProvider, IBMProvider):
                self.backend_ibmq = {
                    b.name: b for b in realProvider.backends()
                }
            else:
                self.backend_ibmq = {
                    b.name(): b for b in realProvider.backends()
                }
            self.backend_ibmq_callsign = {
                self._shorten_name(
                    bn, ['ibm_', 'ibmq_'], ['ibmq_qasm_simulator']
                ): bn for bn in self.backend_ibmq
            }
            self.backend_ibmq_callsign['ibmq_qasm'] = 'ibmq_qasm_simulator'

        self._update_callsign()
        self._update_backend()

    def __repr__(self):
        if self._RealProvider is None:
            return f'<BackendWrapper with AerProvider>'
        else:
            return f'<BackendWrapper with AerProvider and {self._RealProvider.__repr__()[1:-1]}>'

    def make_callsign(
        self,
        sign: Hashable = 'Galm 2',
        who: str = 'solo_wing_pixy',
    ) -> None:

        if sign == 'Galm 2' or who == 'solo_wing_pixy':
            if random() <= 0.2:
                print(
                    "Those who survive a long time on the battlefield start to think they're invincible. I bet you do, too, Buddy.")

        if who in self.backend_aer:
            self.backend_aer_callsign[sign] = who
        elif who in self.backend_ibmq:
            self.backend_ibmq_callsign[sign] = who
        else:
            raise ValueError(f"'{who}' unknown backend.")

        self._update_callsign()

    def add_backend(
        self,
        name: str,
        backend: Backend,
        callsign: Hashable = None,
    ) -> None:
        self.backend_ibmq[name] = backend
        self._update_backend()
        if not callsign is None:
            self.backend_ibmq_callsign[callsign] = name
            self._update_callsign()

    def __call__(
        self,
        backend_name: str,
    ) -> Union[Backend, BackendV1, BackendV2]:
        # if 'qasm' in backend_name:
        #     warnings.warn(
        #         "We use 'AerSimulator' as replacement of 'QASMSimulator' "+
        #         "due to they are the same things, "+
        #         "more info checks the doc of 'backendWrapper'."
        #     )
        #     backend_name = 'aer'
        if backend_name in self.backend_callsign:
            backend_name = self.backend_callsign[backend_name]
        elif backend_name in self.backend:
            ...
        else:
            raise ValueError(
                f"'{backend_name}' unknown backend or backend callsign.")

        return self.backend[backend_name]


class backendManager(backendWrapper):
    """A wrapper includes accout loading and backend loading.
    And deal wtth either :module:`qiskit-ibmq-provider` or the older version `qiskit.providers.ibmq`."""

    def __init__(
        self,
        hub: Optional[str] = None,
        group: Optional[str] = None,
        project: Optional[str] = None,

        instance: Optional[str] = None,
    ) -> None:

        if instance is not None:
            self.instance = instance
            self.hub, self.group, self.project = instance.split('/')
        else:
            for name in [hub, group, project]:
                if name is None:
                    raise ValueError(
                        "Please provide either instance or hub, group, project.")
            self.instance = f'{hub}/{group}/{project}'
            self.hub = hub
            self.group = group
            self.project = project

        if qiskit_ibmq_provider_deprecated:
            print("| Provider by 'qiskit_ibm_provider'.")
            IBMProvider.load_account()
            newProvider = IBMProvider(instance=self.instance)
            super().__init__(realProvider=newProvider)
        else:
            print("| Provider by 'qiskit.providers.ibmq', which will be deprecated.")
            IBMQ.load_account()
            oldProvider = IBMQ.get_provider(
                hub=self.hub, group=self.group, project=self.project)
            super().__init__(realProvider=oldProvider)

    def save_account(self, **kwargs) -> None:
        """Save account to disk.

        (The following is copied from :func:`qiskit_ibmq_provider.IBMProvider.save_account`)
        Args:
            token: IBM Quantum API token.
            url: The API URL.
                Defaults to https://auth.quantum-computing.ibm.com/api
            instance: The hub/group/project.
            name: Name of the account to save.
            proxies: Proxy configuration. Supported optional keys are
                ``urls`` (a dictionary mapping protocol or protocol and host to the URL of the proxy,
                documented at https://docs.python-requests.org/en/latest/api/#requests.Session.proxies),
                ``username_ntlm``, ``password_ntlm`` (username and password to enable NTLM user
                authentication)
            verify: Verify the server's TLS certificate.
            overwrite: ``True`` if the existing account is to be overwritten.

        """

        if qiskit_ibmq_provider_deprecated:
            IBMProvider.save_account(**kwargs)
        else:
            IBMQ.save_account(**kwargs)
