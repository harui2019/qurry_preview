from .attrdict import argdict, argTuple
from .jsonablize import Parse as jsonablize, quickJSONExport, keyTupleLoads
from .configuration import Configuration
from .gitsync import syncControl

from .tagmaps.tagmaps import TagMap
from .tagmaps.quantity import quantitiesMean, tagMapQuantityMean, Q

# class MoriWrapper():
  
  
"""
# Mori 🌳 🍛 - Qurry Data Structure Complex

- *A side product of Qurry 🍛 - The Measuring Tool for Renyi Entropy, Loschmidt Echo, and Magnetization Squared, The Library of Some Common Cases*

This is a package which indepents from the data structure of Qurry 🍛 for easier version control and not designed for general use like Gajima 🔄 🍛, the progress bar module also divided from Qurry 🍛.

**This module is far from finish and will update frenquently with the development of Qurry 🍛 .**

---

## Why this name ?

I'm a DeadBeat, the fan of Hololive VTuber Mori Calliope, and want to name something after her for a not short time.

---

## Git Subtree Command

`git subtree push --prefix qurrium/mori git@github.com:harui2019/mori.git master`

---

## Configurate Environment

- **`Python 3.9.7+` installed by Anaconda**
  - on
    - **Ubuntu 20.04 LTS/18.04 LTS** on `x86_64` **(recommended)**
    - **Windows 10/11** on `x86_64`
      - We recommend to use Linux based system, due to the GPU acceleration of `Qiskit`, `qiskit-aer-gpu` only works with Nvidia CUDA on Linux.

"""