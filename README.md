# isabelle-python-eval

Differential tests for the [Isabelle Python code generator](https://github.com/pure-py/isabelle-python-codegen):
verified data structures from the AFP are exported to Python and checked against
established Python libraries using Hypothesis.

## Requirements

- Isabelle2025-2 with the `isabelle-python-codegen` and AFP components registered
- [uv](https://docs.astral.sh/uv/)

## Usage

```bash
isabelle build -c -D .   # regenerate */generated/ for every data structure
uv run pytest -v         # run all tests
```

`-c` forces a rebuild, so the generated code is rewritten even when the
session is up to date. To rebuild a single one: `isabelle build -d . -c Splay_Harness`.

| Folder | Isabelle source | Compared against |
|---|---|---|
| `splay_tree/` | AFP `Splay_Tree.Splay_Map` | `sortedcontainers.SortedDict` |
| `leftist_heap/` | `HOL-Data_Structures.Leftist_Heap` | `heapq` |
| `rbt_map/` | `HOL-Data_Structures.RBT_Map` | `sortedcontainers.SortedDict` |
| `binomial_heap/` | `HOL-Data_Structures.Binomial_Heap` | `heapq` |
| `hermite/` | AFP `Hermite` (Hermite normal form) | `sympy` `hermite_normal_form` |
| `smith/` | AFP `Smith_Normal_Form` (Smith normal form) | `sympy` `smith_normal_form`, `smith_normal_decomp` |

## Layout

One folder per data structure, e.g. `splay_tree/`:

- `ROOT`, `*.thy`: Isabelle session that exports the code to `generated/`
- `test_*.py`: differential tests against the generated module

To add a data structure, create a new folder in the same way and list it in `ROOTS`.

## Testing libraries against verified references

Most folders validate the code generator: a mismatch points at the generated code. In
`hermite/` and `smith/` the direction is reversed: the verified algorithm is the reference and
SymPy is the library under test. The first build of these harnesses also builds their AFP
ancestors (HOL-Analysis, Gauss_Jordan, Echelon_Form, Hermite, and for `smith/` also
Berlekamp_Zassenhaus and Smith_Normal_Form), which takes several minutes.

The verified references are slow, which limits the inputs:

- `hermite/`: about 0.1 s per 5 x 5 matrix, so 200 examples per test by default
  (`HNF_EXAMPLES`, `HNF_MAX_DIM`).
- `smith/`: about 75 ms per 5 x 5 matrix, so 200 examples per test by default
  (`SNF_EXAMPLES`, `SNF_MAX_DIM`). This relies on importing
  `Jordan_Normal_Form.Matrix_IArray_Impl` in the harness: by default the code generator
  represents matrices as functions, every matrix product then nests closures, and a 3 x 3 matrix
  takes minutes. Importing `Python.Python_IArray` as well makes the arrays native Python tuples.

### Native printings: measured gains on `smith/`

To see how much native printings help, they were added one at a time on top of the Smith
reference, each step exported as its own module. All variants returned identical `(P, S, Q)`
on 300 random matrices; times are medians on the benchmark's n x n matrices:

| Step (cumulative) | 5 x 5 | 8 x 8 | calls at 5 x 5 |
|---|---|---|---|
| baseline | 99 ms | 2005 ms | 1,445,120 |
| + `Python.Python_IArray` (tuples, native indexing) | 74 ms | 1379 ms | 965,455 |
| + `upt` as `list(range(i, j))` | 73 ms | 1366 ms | 967,678 |
| + `foldr`/`foldl` as `functools.reduce` | 71 ms | 1293 ms | 914,372 |
| + JNF's `vec_impl`/`mat_impl` as transparent wrappers | 63 ms | 1075 ms | 901,073 |

Only the first step is kept in the harness: it is already part of the backend. Together the
steps gain about 1.6x at 5 x 5 and 1.9x at 8 x 8; the remaining ~900k calls are matrix element
access, scalar products and type-class dictionary lookups, which native printings of library
functions do not remove. Printing JNF's typedef morphisms (`Abs_mat_impl`, `Rep_mat_impl`)
transparently as well fails in the backend ("Unknown statement name").

## Benchmarks

`bench/run.py` times the generated references against the libraries they are tested against,
on the same workloads (map: insert, look up, delete half, list items; heap: build, drain;
matrices: one random n x n integer matrix). It checks that both sides agree and records medians
in `bench/out/results.json`. `bench/plot.py` turns that file into `bench/out/benchmark.png`,
including the slowdown of each reference at the largest size both sides completed; `run.py`
calls it at the end unless given `--no-plot`.

```bash
uv run python bench/run.py            # all sizes (a few minutes)
uv run python bench/run.py --quick    # smaller sizes
uv run python bench/run.py --only rbt_map smith
uv run python bench/plot.py          # re-plot bench/out/results.json
```

The generated code runs with Python's default recursion limit, so a failure there (e.g. deep
recursion over a long list) shows up as a cross in the plot, and larger sizes are skipped.

