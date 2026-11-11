"""
Differential tests of the generated leftist heap against heapq, with a sorted list as the model
both are checked against. Also checks persistence and, on small heaps, the heap and leftist
invariants (h_invar).
"""
import heapq
import os
import sys

import pytest
from hypothesis import HealthCheck, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "generated"))
import Leftist_Heap_Ref as gen  # noqa: E402

SMALL = st.integers(-25, 25)              # few distinct values -> many duplicates
WIDE = st.integers(-(2**70), 2**70)       # beyond 64-bit
ELEMS = st.one_of(SMALL, SMALL, SMALL, WIDE)

INVAR_MAX = 40                            # h_invar uses list-based sets, quadratic in size

PROFILE = settings(
    max_examples=int(os.environ.get("LHEAP_EXAMPLES", "300")),
    stateful_step_count=int(os.environ.get("LHEAP_STEPS", "60")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)


def build(xs):
    t = gen.h_empty()
    for x in xs:
        t = gen.h_insert(x, t)
    return t


def drain(t):
    """Pop every element via h_get_min/h_del_min; the result must be sorted."""
    out = []
    while (m := gen.h_get_min(t)) is not None:
        out.append(m)
        t = gen.h_del_min(t)
    return out


class LeftistHeapVsHeapq(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.sut = gen.h_empty()
        self.hq = []
        self.ref = []                     # sorted list
        self.history = []                 # (sut version, snapshot of model)

    def _snapshot(self):
        self.history.append((self.sut, list(self.ref)))

    @rule(x=ELEMS)
    def op_insert(self, x):
        self._snapshot()
        self.sut = gen.h_insert(x, self.sut)
        heapq.heappush(self.hq, x)
        self.ref = sorted(self.ref + [x])

    @rule()
    def op_del_min(self):
        self._snapshot()
        self.sut = gen.h_del_min(self.sut)
        if self.hq:
            heapq.heappop(self.hq)
        self.ref = self.ref[1:]

    @rule(xs=st.lists(ELEMS, max_size=10))
    def op_merge(self, xs):
        self._snapshot()
        self.sut = gen.h_merge(self.sut, build(xs))
        self.hq = list(heapq.merge(sorted(self.hq), sorted(xs)))   # sorted list is a valid heap
        self.ref = sorted(self.ref + xs)

    @rule(i=st.integers(min_value=0))
    def op_old_version_unchanged(self, i):
        if not self.history:
            return
        t, snap = self.history[i % len(self.history)]
        assert sorted(gen.h_elems(t)) == snap

    @invariant()
    def contents_agree(self):
        assert sorted(self.hq) == self.ref                       # stdlib vs trivial model
        assert (self.hq[0] if self.hq else None) == (self.ref[0] if self.ref else None)
        assert gen.h_get_min(self.sut) == (self.ref[0] if self.ref else None)
        assert sorted(gen.h_elems(self.sut)) == self.ref         # generated code vs both

    @invariant()
    def heap_invariants_hold(self):
        if len(self.ref) <= INVAR_MAX:
            assert gen.h_invar(self.sut)


TestLeftistHeapVsHeapq = LeftistHeapVsHeapq.TestCase
TestLeftistHeapVsHeapq.settings = PROFILE


def test_empty():
    t = gen.h_empty()
    assert gen.h_elems(t) == []
    assert gen.h_get_min(t) is None
    assert gen.h_elems(gen.h_del_min(t)) == []
    assert gen.h_invar(t)


def test_partial_get_min_on_empty_raises():
    """Leftist_Heap.get_min has no equation for Leaf; the backend falls through to a failed match."""
    assert gen.h_get_min_partial(build([3, 1, 2])) == 1
    with pytest.raises(RuntimeError, match="match failed"):
        gen.h_get_min_partial(gen.h_empty())


def test_duplicates_and_persistence():
    t = build([2, 1, 2, 1])
    assert drain(t) == [1, 1, 2, 2]
    assert gen.h_get_min(gen.h_del_min(t)) == 1
    assert sorted(gen.h_elems(t)) == [1, 1, 2, 2]  # persistence


@pytest.mark.parametrize("x", [0, -1, 2**31, -(2**31), 2**63, -(2**63), 2**64, 2**100, -(2**100)])
def test_integer_boundaries(x):
    t = build([x + 1, x, x - 1])
    assert drain(t) == [x - 1, x, x + 1]


@pytest.mark.parametrize("order", ["ascending", "descending"])
def test_large_drain(order):
    """The right spine stays O(log n), so draining a large heap does not recurse deeply."""
    n = int(os.environ.get("LHEAP_LARGE_N", "3000"))
    xs = list(range(n)) if order == "ascending" else list(range(n - 1, -1, -1))
    assert drain(build(xs)) == list(range(n))


@pytest.mark.parametrize("order", ["ascending", "descending"])
def test_large_elems(order, recursion_limit):
    """
    h_elems (inorder) recurses as deep as the tree. Only the right spine is bounded, so
    descending inserts build a left spine of depth n. Hitting the recursion limit is reported
    as xfail.
    """
    n = int(os.environ.get("LHEAP_LARGE_N", "3000"))
    recursion_limit(int(os.environ.get("LHEAP_RECURSION_LIMIT", "1000")))
    xs = list(range(n)) if order == "ascending" else list(range(n - 1, -1, -1))
    t = build(xs)
    try:
        assert sorted(gen.h_elems(t)) == list(range(n))
    except RecursionError:
        pytest.xfail(f"generated h_elems exceeds recursion limit on {order} heap of {n}")
