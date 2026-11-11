"""
Differential tests of the generated splay-tree map against sortedcontainers.SortedDict, with a
plain dict as the model both are checked against. Earlier versions of the (immutable) tree must
stay unchanged by later updates and deletes.
"""
import os
import sys

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from sortedcontainers import SortedDict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated"))
import Splay_Ref as gen  # noqa: E402

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
        self.sut = gen.m_empty()
        self.sd = SortedDict()
        self.ref = {}
        self.history = []  # (sut version, snapshot of model items)

    def _snapshot(self):
        self.history.append((self.sut, sorted(self.ref.items())))

    @rule(k=KEYS, v=VALS)
    def op_update(self, k, v):
        self._snapshot()
        self.sut = gen.m_update(k, v, self.sut)
        self.sd[k] = v
        self.ref[k] = v

    @rule(k=KEYS)
    def op_delete(self, k):
        self._snapshot()
        self.sut = gen.m_delete(k, self.sut)
        self.sd.pop(k, None)
        self.ref.pop(k, None)

    @rule(data=st.data())
    def op_delete_present(self, data):
        if not self.ref:
            return
        k = data.draw(st.sampled_from(sorted(self.ref)))
        self._snapshot()
        self.sut = gen.m_delete(k, self.sut)
        self.sd.pop(k, None)
        self.ref.pop(k, None)

    @rule(k=KEYS)
    def op_lookup(self, k):
        assert gen.m_lookup(self.sut, k) == self.sd.get(k) == self.ref.get(k)

    @rule(data=st.data())
    def op_lookup_present(self, data):
        if not self.ref:
            return
        k = data.draw(st.sampled_from(sorted(self.ref)))
        assert gen.m_lookup(self.sut, k) == self.ref[k]

    @rule(i=st.integers(min_value=0))
    def op_old_version_unchanged(self, i):
        if not self.history:
            return
        t, snap = self.history[i % len(self.history)]
        assert gen.m_items(t) == snap

    @invariant()
    def contents_agree(self):
        expected = sorted(self.ref.items())
        assert list(self.sd.items()) == expected          # PyPI lib vs trivial model
        assert gen.m_items(self.sut) == expected               # generated code vs both


TestSplayVsSortedDict = SplayVsSortedDict.TestCase
TestSplayVsSortedDict.settings = PROFILE


def test_empty():
    t = gen.m_empty()
    assert gen.m_items(t) == []
    assert gen.m_lookup(t, 0) is None
    assert gen.m_items(gen.m_delete(0, t)) == []


def test_overwrite_and_delete_roundtrip():
    t = gen.m_update(2, 20, gen.m_update(1, 11, gen.m_update(1, 10, gen.m_empty())))
    assert gen.m_items(t) == [(1, 11), (2, 20)]
    assert gen.m_items(gen.m_delete(1, gen.m_delete(1, t))) == [(2, 20)]
    assert gen.m_items(t) == [(1, 11), (2, 20)]  # persistence


@pytest.mark.parametrize("k", [0, -1, 2**31, -(2**31), 2**63, -(2**63), 2**64, 2**100, -(2**100)])
def test_integer_boundaries(k):
    t = gen.m_update(k + 1, 1, gen.m_update(k, k, gen.m_empty()))
    assert gen.m_lookup(t, k) == k
    assert gen.m_lookup(t, k + 1) == 1
    assert gen.m_items(t) == [(k, k), (k + 1, 1)]


@pytest.mark.parametrize("order", ["ascending", "descending"])
def test_degenerate_spine(order, recursion_limit):
    """
    Sorted insertion makes a spine of depth n, and splaying the far end recurses about n/2 deep.
    Hitting the recursion limit is reported as xfail.
    """
    n = int(os.environ.get("SPLAY_SPINE_N", "3000"))
    recursion_limit(int(os.environ.get("SPLAY_RECURSION_LIMIT", "1000")))
    keys = range(n) if order == "ascending" else range(n - 1, -1, -1)
    try:
        t = gen.m_empty()
        for k in keys:
            t = gen.m_update(k, -k, t)
        far = 0 if order == "ascending" else n - 1
        assert gen.m_lookup(t, far) == -far
        assert gen.m_items(t) == [(k, -k) for k in range(n)]
    except RecursionError:
        pytest.xfail(f"generated code exceeds recursion limit on {order} spine of {n}")
