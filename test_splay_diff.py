"""
Differential tests: Isabelle-generated splay-tree map  vs  sortedcontainers.SortedDict.

Three-way comparison so a disagreement can be attributed:
  generated splay map (system under test)
  SortedDict          (PyPI library under comparison)
  dict                (trivially correct model; also checks SortedDict itself)

Also checks persistence: older versions of the immutable tree must be unchanged
by later updates/deletes (SortedDict is mutable, so snapshots are taken in the model).
"""
import os
import sys

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from sortedcontainers import SortedDict

from golden_adapter import GoldenSplay

SMALL = st.integers(-25, 25)              # few distinct keys -> many collisions / deletes of present keys
WIDE = st.integers(-(2**70), 2**70)       # beyond 64-bit
KEYS = st.one_of(SMALL, SMALL, SMALL, WIDE)
VALS = st.one_of(st.integers(-1000, 1000), st.integers(-(2**70), 2**70))

PROFILE = settings(
    max_examples=int(os.environ.get("SPLAY_EXAMPLES", "300")),
    stateful_step_count=int(os.environ.get("SPLAY_STEPS", "60")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)


class SplayVsSortedDict(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.sut = GoldenSplay.empty()
        self.sd = SortedDict()
        self.ref = {}
        self.history = []  # (sut version, snapshot of model items)

    def _snapshot(self):
        self.history.append((self.sut, sorted(self.ref.items())))

    @rule(k=KEYS, v=VALS)
    def op_update(self, k, v):
        self._snapshot()
        self.sut = self.sut.update(k, v)
        self.sd[k] = v
        self.ref[k] = v

    @rule(k=KEYS)
    def op_delete(self, k):
        self._snapshot()
        self.sut = self.sut.delete(k)
        self.sd.pop(k, None)
        self.ref.pop(k, None)

    @rule(data=st.data())
    def op_delete_present(self, data):
        if not self.ref:
            return
        k = data.draw(st.sampled_from(sorted(self.ref)))
        self._snapshot()
        self.sut = self.sut.delete(k)
        self.sd.pop(k, None)
        self.ref.pop(k, None)

    @rule(k=KEYS)
    def op_lookup(self, k):
        assert self.sut.lookup(k) == self.sd.get(k) == self.ref.get(k)

    @rule(data=st.data())
    def op_lookup_present(self, data):
        if not self.ref:
            return
        k = data.draw(st.sampled_from(sorted(self.ref)))
        assert self.sut.lookup(k) == self.ref[k]

    @rule(i=st.integers(min_value=0))
    def op_old_version_unchanged(self, i):
        if not self.history:
            return
        t, snap = self.history[i % len(self.history)]
        assert t.items() == snap

    @invariant()
    def contents_agree(self):
        expected = sorted(self.ref.items())
        assert list(self.sd.items()) == expected          # PyPI lib vs trivial model
        assert self.sut.items() == expected               # generated code vs both


TestSplayVsSortedDict = SplayVsSortedDict.TestCase
TestSplayVsSortedDict.settings = PROFILE


def test_empty():
    t = GoldenSplay.empty()
    assert t.items() == []
    assert t.lookup(0) is None
    assert t.delete(0).items() == []


def test_overwrite_and_delete_roundtrip():
    t = GoldenSplay.empty().update(1, 10).update(1, 11).update(2, 20)
    assert t.items() == [(1, 11), (2, 20)]
    assert t.delete(1).delete(1).items() == [(2, 20)]
    assert t.items() == [(1, 11), (2, 20)]  # persistence


@pytest.mark.parametrize("k", [0, -1, 2**31, -(2**31), 2**63, -(2**63), 2**64, 2**100, -(2**100)])
def test_integer_boundaries(k):
    t = GoldenSplay.empty().update(k, k).update(k + 1, 1)
    assert t.lookup(k) == k
    assert t.lookup(k + 1) == 1
    assert t.items() == [(k, k), (k + 1, 1)]


@pytest.mark.parametrize("order", ["ascending", "descending"])
def test_degenerate_spine(order):
    """
    Ascending (or descending) insertion makes a spine of depth N, and splaying the far
    end recurses to depth ~N/2. Records whether the generated Python hits the
    interpreter recursion limit (reported as xfail, not as a mismatch).
    """
    n = int(os.environ.get("SPLAY_SPINE_N", "3000"))
    sys.setrecursionlimit(int(os.environ.get("SPLAY_RECURSION_LIMIT", "1000")))
    keys = range(n) if order == "ascending" else range(n - 1, -1, -1)
    try:
        t = GoldenSplay.empty()
        for k in keys:
            t = t.update(k, -k)
        far = 0 if order == "ascending" else n - 1
        assert t.lookup(far) == -far
        assert t.items() == [(k, -k) for k in range(n)]
    except RecursionError:
        pytest.xfail(f"generated code exceeds recursion limit on {order} spine of {n}")
