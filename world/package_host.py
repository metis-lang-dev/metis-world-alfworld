# The shim a generated package carries as its own alf_host.py: the world's host, found by
# walking up to world/alf_host.py, made with this package's directory (its game.json).
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_d = HERE
for _ in range(6):
    _d = os.path.dirname(_d)
    if os.path.exists(os.path.join(_d, "world", "alf_host.py")):
        sys.path.insert(0, os.path.join(_d, "world"))
        break
from alf_host import AlfHost  # noqa: E402

PAIRS = ()


def flips(atom):
    return None


def words(atom, names=None):
    return None


def make(case=None):
    return AlfHost(HERE, case)
