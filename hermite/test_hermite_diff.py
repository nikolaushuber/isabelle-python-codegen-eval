"""
Differential tests: SymPy's Hermite normal form  vs  the verified AFP Hermite algorithm.

Here the direction is reversed compared to the data structure folders: the Isabelle-generated
code (AFP entry Hermite, proven to compute the unique HNF) is the reference, and SymPy is the
library under test.

Conventions differ and are translated, not compared loosely:
  AFP    row-style HNF  H = P * A: upper echelon, pivots > 0, entries above a pivot in [0, pivot)
  SymPy  column-style HNF W = A * U (Cohen, Algorithm 2.4.5): pivots in the rightmost columns,
         entries right of a pivot in [0, pivot), zero columns dropped
With rot180 reversing rows and columns, rot180(A^T) has row HNF rot180((A * U)^T), so
W = (rot180(hnf_rows(rot180(A^T))))^T without its leading zero columns.

Covered: the default algorithm (any shape and rank), the modulo-D algorithm (Cohen 2.4.8, full
row rank, D a multiple of det W), and check_rank=True, which must fall back for deficient rank.
"""
import importlib
import os
import sys
from math import prod

from hypothesis import HealthCheck, assume, given, settings, strategies as st
from sympy import Matrix, ZZ
from sympy.matrices.normalforms import hermite_normal_form
from sympy.polys.matrices import DomainMatrix
from sympy.polys.matrices.normalforms import hermite_normal_form as dm_hermite_normal_form

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("HNF_GEN_PATH", os.path.join(HERE, "generated")))
gen = importlib.import_module(os.environ.get("HNF_GEN_MODULE", "Hermite_Ref"))

MAX_DIM = int(os.environ.get("HNF_MAX_DIM", "5"))

settings.register_profile(
    "hnf",
    max_examples=int(os.environ.get("HNF_EXAMPLES", "2000")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
PROFILE = settings.get_profile("hnf")


def rot180(m):
    return [row[::-1] for row in m[::-1]]


def transpose(m):
    return [list(col) for col in zip(*m)]


def reference_hnf(a):
    """SymPy-convention HNF of a, computed by the verified row-style algorithm."""
    au = transpose(rot180(gen.hnf_rows(rot180(transpose(a)))))
    cols = [c for c in transpose(au) if any(c)]
    return transpose(cols) if cols else [[] for _ in a]


def to_lists(m):
    return [[int(x) for x in m.row(i)] for i in range(m.rows)] if m.cols else [[] for _ in range(m.rows)]


# ---- input generation ----

SMALL = st.integers(-4, 4)                     # many zeros and common factors
WIDE = st.integers(-(2**40), 2**40)
ENTRY = st.one_of(SMALL, SMALL, SMALL, WIDE)


@st.composite
def dense(draw, rows=None, cols=None, entry=ENTRY):
    m = rows if rows is not None else draw(st.integers(1, MAX_DIM))
    n = cols if cols is not None else draw(st.integers(1, MAX_DIM))
    return [[draw(entry) for _ in range(n)] for _ in range(m)]


@st.composite
def low_rank(draw):
    """Product of an m x r and an r x n matrix: rank at most r, with hidden dependencies."""
    m, n = draw(st.integers(1, MAX_DIM)), draw(st.integers(1, MAX_DIM))
    r = draw(st.integers(1, min(m, n)))
    b = draw(dense(m, r, SMALL))
    c = draw(dense(r, n, SMALL))
    return [[sum(b[i][k] * c[k][j] for k in range(r)) for j in range(n)] for i in range(m)]


@st.composite
def with_repeats(draw):
    """Duplicate, negate or zero some rows and columns of a dense matrix."""
    a = draw(dense())
    for _ in range(draw(st.integers(0, 3))):
        op = draw(st.sampled_from(["dup_row", "neg_row", "zero_row", "dup_col", "zero_col"]))
        i = draw(st.integers(0, len(a) - 1))
        j = draw(st.integers(0, len(a[0]) - 1))
        if op == "dup_row" and len(a) < MAX_DIM + 1:
            a.insert(draw(st.integers(0, len(a))), list(a[i]))
        elif op == "neg_row":
            a[i] = [-x for x in a[i]]
        elif op == "zero_row":
            a[i] = [0] * len(a[i])
        elif op == "dup_col" and len(a[0]) < MAX_DIM + 1:
            for row in a:
                row.append(row[j])
        elif op == "zero_col":
            for row in a:
                row[j] = 0
    return a


MATRICES = st.one_of(dense(), low_rank(), with_repeats())


# ---- tests ----

@PROFILE
@given(MATRICES)
def test_hnf_matches_reference(a):
    assert to_lists(hermite_normal_form(Matrix(a))) == reference_hnf(a)


@PROFILE
@given(MATRICES)
def test_domain_matrix_hnf_matches_reference(a):
    dm = DomainMatrix([[ZZ(x) for x in row] for row in a], (len(a), len(a[0])), ZZ)
    assert to_lists(dm_hermite_normal_form(dm).to_Matrix()) == reference_hnf(a)


@PROFILE
@given(MATRICES, st.integers(1, 6))
def test_hnf_modulo_d_matches_reference(a, k):
    """The mod-D algorithm needs full row rank; D is any positive multiple of det W."""
    w = reference_hnf(a)
    assume(len(w[0]) == len(a))
    d = prod(w[i][i] for i in range(len(a))) * k
    assert to_lists(hermite_normal_form(Matrix(a), D=d)) == w


@PROFILE
@given(MATRICES, st.integers(1, 6))
def test_hnf_check_rank_matches_reference(a, k):
    """With check_rank=True, D is only used for full row rank; otherwise SymPy must fall back."""
    w = reference_hnf(a)
    full = len(w[0]) == len(a)
    d = prod(w[i][i] for i in range(len(a))) * k if full else k
    assert to_lists(hermite_normal_form(Matrix(a), D=d, check_rank=True)) == w


def test_afp_example():
    """Example from the AFP entry; det = 6804 = 1 * 108 * 63."""
    assert gen.hnf_rows([[37, 8, 6], [5, 4, -8], [3, 24, -7]]) == [[1, 44, 57], [0, 108, 52], [0, 0, 63]]


def test_sympy_docstring_example():
    a = [[12, 6, 4], [3, 9, 6], [2, 16, 14]]
    assert reference_hnf(a) == [[10, 0, 2], [0, 15, 3], [0, 0, 2]]
    assert to_lists(hermite_normal_form(Matrix(a))) == reference_hnf(a)
