"""
Differential tests: SymPy's Smith normal form  vs  the verified AFP Smith_Normal_Form algorithm.

As in hermite/, the Isabelle-generated code is the reference and SymPy is the library under test.
The AFP algorithm (Smith_ED_mxn) returns (P, S, Q) with S = P * A * Q, P and Q invertible and S
in Smith normal form. Over ZZ a Smith normal form is unique only up to the signs of its diagonal,
so diagonals are compared in absolute value; SymPy itself normalises to non-negative entries.

Checked for SymPy:
  smith_normal_form / invariant_factors  diagonal agrees with the reference (up to sign)
  smith_normal_decomp                    returns (S, s, t) with S = s * A * t, det s, det t = +-1
Checked for the reference itself (cheap, independent of SymPy): S = P * A * Q, det P, det Q = +-1.

The reference takes about 0.1 s for a 5 x 5 matrix and 2 s for 8 x 8 (with array-backed matrices,
see Smith_Harness.thy), so shapes go up to SNF_MAX_DIM = 5 by default.
"""
import importlib
import os
import sys

from hypothesis import HealthCheck, given, settings, strategies as st
from sympy import Matrix, ZZ
from sympy.matrices.normalforms import invariant_factors, smith_normal_decomp, smith_normal_form

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.environ.get("SNF_GEN_PATH", os.path.join(HERE, "generated")))
gen = importlib.import_module(os.environ.get("SNF_GEN_MODULE", "Smith_Ref"))

MAX_DIM = int(os.environ.get("SNF_MAX_DIM", "5"))

settings.register_profile(
    "snf",
    max_examples=int(os.environ.get("SNF_EXAMPLES", "200")),
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)
PROFILE = settings.get_profile("snf")


def reference(a):
    """(P, S, Q) from the verified algorithm, as lists of rows."""
    p, (s, q) = gen.snf(len(a[0]), a)
    return p, s, q


def diagonal(m):
    rows = m.rows if isinstance(m, Matrix) else len(m)
    cols = m.cols if isinstance(m, Matrix) else len(m[0])
    return [int(m[i, i] if isinstance(m, Matrix) else m[i][i]) for i in range(min(rows, cols))]


def unimodular(m):
    return abs(Matrix(m).det()) == 1


# ---- input generation ----

SMALL = st.integers(-4, 4)
WIDE = st.integers(-(2**40), 2**40)
ENTRY = st.one_of(SMALL, SMALL, SMALL, WIDE)


@st.composite
def dense(draw, shape, entry=ENTRY):
    m, n = shape
    return [[draw(entry) for _ in range(n)] for _ in range(m)]


@st.composite
def low_rank(draw, shape):
    """Product of an m x r and an r x n matrix: rank at most r, with hidden dependencies."""
    m, n = shape
    r = draw(st.integers(1, min(m, n)))
    b = draw(dense((m, r), SMALL))
    c = draw(dense((r, n), SMALL))
    return [[sum(b[i][k] * c[k][j] for k in range(r)) for j in range(n)] for i in range(m)]


@st.composite
def with_repeats(draw, shape):
    """Copy, negate or zero some rows and columns of a dense matrix (keeping its shape)."""
    a = draw(dense(shape))
    m, n = shape
    for _ in range(draw(st.integers(0, 3))):
        op = draw(st.sampled_from(["copy_row", "neg_row", "zero_row", "copy_col", "zero_col"]))
        i, i2 = draw(st.integers(0, m - 1)), draw(st.integers(0, m - 1))
        j, j2 = draw(st.integers(0, n - 1)), draw(st.integers(0, n - 1))
        if op == "copy_row":
            a[i2] = list(a[i])
        elif op == "neg_row":
            a[i] = [-x for x in a[i]]
        elif op == "zero_row":
            a[i] = [0] * n
        elif op == "copy_col":
            for row in a:
                row[j2] = row[j]
        elif op == "zero_col":
            for row in a:
                row[j] = 0
    return a


@st.composite
def diagonal_like(draw, shape):
    """Diagonal matrices with entries that do not divide each other: exercises the gcd/lcm fix-up."""
    m, n = shape
    d = [draw(st.sampled_from([0, 1, 2, 3, 4, 6, 9, 10, 12, 15, -6, -10])) for _ in range(min(m, n))]
    a = [[d[i] if i == j else 0 for j in range(n)] for i in range(m)]
    if draw(st.booleans()):                                  # hide the diagonal by permuting
        a = draw(st.permutations(a))
        a = [list(r) for r in zip(*draw(st.permutations([list(c) for c in zip(*a)])))]
    return [list(r) for r in a]


SHAPES = st.tuples(st.integers(1, MAX_DIM), st.integers(1, MAX_DIM))
MATRICES = SHAPES.flatmap(
    lambda sh: st.one_of(dense(sh), low_rank(sh), with_repeats(sh), diagonal_like(sh)))


# ---- tests ----

@PROFILE
@given(MATRICES)
def test_reference_is_a_smith_decomposition(a):
    p, s, q = reference(a)
    assert Matrix(p) * Matrix(a) * Matrix(q) == Matrix(s)
    assert unimodular(p) and unimodular(q)
    d = [abs(x) for x in diagonal(s)]
    assert all(d[i + 1] % d[i] == 0 if d[i] else d[i + 1] == 0 for i in range(len(d) - 1))


@PROFILE
@given(MATRICES)
def test_snf_matches_reference(a):
    _, s, _ = reference(a)
    expected = [abs(x) for x in diagonal(s)]
    got = smith_normal_form(Matrix(a), domain=ZZ)
    assert got.shape == (len(a), len(a[0]))
    assert diagonal(got) == expected
    assert all(got[i, j] == 0 for i in range(got.rows) for j in range(got.cols) if i != j)


@PROFILE
@given(MATRICES)
def test_invariant_factors_match_reference(a):
    _, s, _ = reference(a)
    expected = [abs(x) for x in diagonal(s)]
    assert [int(x) for x in invariant_factors(Matrix(a), domain=ZZ)] == expected


@PROFILE
@given(MATRICES)
def test_snf_decomposition_is_valid(a):
    _, s_ref, _ = reference(a)
    snf, s, t = smith_normal_decomp(Matrix(a), domain=ZZ)
    assert diagonal(snf) == [abs(x) for x in diagonal(s_ref)]
    assert s * Matrix(a) * t == snf
    assert unimodular(s) and unimodular(t)


def test_examples():
    """SymPy's docstring example, and diag(4, 6) ~ diag(2, 12)."""
    a = [[12, 6, 4], [3, 9, 6], [2, 16, 14]]
    _, s, _ = reference(a)
    assert [abs(x) for x in diagonal(s)] == [1, 10, 30]
    assert diagonal(smith_normal_form(Matrix(a), domain=ZZ)) == [1, 10, 30]
    a = [[4, 0], [0, 6]]
    _, s, _ = reference(a)
    assert [abs(x) for x in diagonal(s)] == [2, 12]
    assert diagonal(smith_normal_form(Matrix(a), domain=ZZ)) == [2, 12]
