"""
Differential tests of the generated red-black tree map against sortedcontainers.SortedDict, with
a plain dict as the model both are checked against. Also checks persistence, the red-black and
sortedness invariants (r_invar), and the height bound 2*log2(n+1).
"""
import math
import os
import sys

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule
from sortedcontainers import SortedDict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated"))
import RBT_Map_Ref as gen  # noqa: E402

SMALL = st.integers(-25, 25)              # few distinct keys -> many collisions / deletes of present keys
WIDE = st.integers(-(2**70), 2**70)       # beyond 64-bit
KEYS = st.one_of(SMALL, SMALL, SMALL, WIDE)
VALS = st.one_of(st.integers(-1000, 1000), st.integers(-(2**70), 2**70))

PROFILE = settings(
    max_examples=int(os.environ.get("RBT_EXAMPLES", "300")),
    stateful_step_count=int(os.environ.get("RBT_STEPS", "60")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)


def height_bound(n):
    return 2 * math.log2(n + 1)


class RBTVsSortedDict(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.sut = gen.r_empty()
        self.sd = SortedDict()
        self.ref = {}
        self.history = []  # (sut version, snapshot of model items)

    def _snapshot(self):
        self.history.append((self.sut, sorted(self.ref.items())))

    @rule(k=KEYS, v=VALS)
    def op_update(self, k, v):
        self._snapshot()
        self.sut = gen.r_update(k, v, self.sut)
        self.sd[k] = v
        self.ref[k] = v

    @rule(k=KEYS)
    def op_delete(self, k):
        self._snapshot()
        self.sut = gen.r_delete(k, self.sut)
        self.sd.pop(k, None)
        self.ref.pop(k, None)

    @rule(data=st.data())
    def op_delete_present(self, data):
        if not self.ref:
            return
        k = data.draw(st.sampled_from(sorted(self.ref)))
        self._snapshot()
        self.sut = gen.r_delete(k, self.sut)
        self.sd.pop(k, None)
        self.ref.pop(k, None)

    @rule(k=KEYS)
    def op_lookup(self, k):
        assert gen.r_lookup(self.sut, k) == self.sd.get(k) == self.ref.get(k)

    @rule(data=st.data())
    def op_lookup_present(self, data):
        if not self.ref:
            return
        k = data.draw(st.sampled_from(sorted(self.ref)))
        assert gen.r_lookup(self.sut, k) == self.ref[k]

    @rule(i=st.integers(min_value=0))
    def op_old_version_unchanged(self, i):
        if not self.history:
            return
        t, snap = self.history[i % len(self.history)]
        assert gen.r_items(t) == snap

    @invariant()
    def contents_agree(self):
        expected = sorted(self.ref.items())
        assert list(self.sd.items()) == expected          # PyPI lib vs trivial model
        assert gen.r_items(self.sut) == expected          # generated code vs both

    @invariant()
    def balanced(self):
        assert gen.r_invar(self.sut)
        assert gen.r_height(self.sut) <= height_bound(len(self.ref))


TestRBTVsSortedDict = RBTVsSortedDict.TestCase
TestRBTVsSortedDict.settings = PROFILE


def test_empty():
    t = gen.r_empty()
    assert gen.r_items(t) == []
    assert gen.r_lookup(t, 0) is None
    assert gen.r_items(gen.r_delete(0, t)) == []
    assert gen.r_invar(t)
    assert gen.r_height(t) == 0


def test_overwrite_and_delete_roundtrip():
    t = gen.r_update(2, 20, gen.r_update(1, 11, gen.r_update(1, 10, gen.r_empty())))
    assert gen.r_items(t) == [(1, 11), (2, 20)]
    assert gen.r_items(gen.r_delete(1, gen.r_delete(1, t))) == [(2, 20)]
    assert gen.r_items(t) == [(1, 11), (2, 20)]  # persistence


@pytest.mark.parametrize("k", [0, -1, 2**31, -(2**31), 2**63, -(2**63), 2**64, 2**100, -(2**100)])
def test_integer_boundaries(k):
    t = gen.r_update(k + 1, 1, gen.r_update(k, k, gen.r_empty()))
    assert gen.r_lookup(t, k) == k
    assert gen.r_lookup(t, k + 1) == 1
    assert gen.r_items(t) == [(k, k), (k + 1, 1)]


@pytest.mark.parametrize("order", ["ascending", "descending"])
def test_large_sequential(order):
    """Sequential insertion, which defeats the splay tree: the red-black tree stays balanced."""
    n = int(os.environ.get("RBT_LARGE_N", "3000"))
    keys = range(n) if order == "ascending" else range(n - 1, -1, -1)
    t = gen.r_empty()
    for k in keys:
        t = gen.r_update(k, -k, t)
    assert gen.r_height(t) <= height_bound(n)
    assert all(gen.r_lookup(t, k) == -k for k in range(n))
    for k in range(0, n, 2):
        t = gen.r_delete(k, t)
    assert gen.r_height(t) <= height_bound(n // 2)
    assert all(gen.r_lookup(t, k) == (None if k % 2 == 0 else -k) for k in range(n))


@pytest.mark.parametrize("order", ["ascending", "descending"])
def test_large_items(order, recursion_limit):
    """r_items (inorder) recurses as deep as the tree, which stays O(log n)."""
    n = int(os.environ.get("RBT_LARGE_N", "3000"))
    recursion_limit(int(os.environ.get("RBT_RECURSION_LIMIT", "1000")))
    keys = range(n) if order == "ascending" else range(n - 1, -1, -1)
    t = gen.r_empty()
    for k in keys:
        t = gen.r_update(k, -k, t)
    assert gen.r_items(t) == [(k, -k) for k in range(n)]
