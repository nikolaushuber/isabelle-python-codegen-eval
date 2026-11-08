# isabelle-python-eval

Differential tests for the [Isabelle Python code generator](https://github.com/pure-py/isabelle-python-codegen):
verified data structures from the AFP are exported to Python and checked against
established Python libraries using Hypothesis.

## Requirements

- Isabelle2025-2 with the `isabelle-python-codegen` and AFP components registered
- [uv](https://docs.astral.sh/uv/)
- optional: PyPy, which `make pypy-env` installs through uv into `.venv-pypy`

## Usage

```bash
make build       # isabelle build -c -D . -o python_tail_calls=true: regenerate */generated/
make test        # run all tests (CPython, .venv)
make test-pypy   # the same under PyPy (.venv-pypy, created on first use)
```

Without make: `isabelle build -c -D . -o python_tail_calls=true` and `uv run pytest -v`.
`python_tail_calls` prints self tail calls as loops, so deep recursion in the generated code
stays under Python's recursion limit.

`-c` forces a rebuild, so the generated code is rewritten even when the
session is up to date. To rebuild a single one: `isabelle build -d . -c -o python_tail_calls=true Splay_Harness`.

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
in `bench/out/<interpreter>/results.json`, so CPython and PyPy runs sit side by side. Each
measurement is the median of 15 timed runs (`--repeats`) after 10 untimed warm-up runs
(`--warmup`), which PyPy's JIT needs. `bench/plot.py` combines all results into `bench/out/benchmark.png` (and `.pdf`): time against size per
benchmark and interpreter, and the slowdown of each reference against its library.

```bash
make bench-all                             # CPython, then PyPy, then the plot
make bench                                 # CPython only
make bench-pypy                            # PyPy only
make plot                                  # re-plot everything in bench/out/*/
make bench BENCH_ARGS="--quick --only rbt_map smith"
make calls                                 # function calls, also as LaTeX (calls.tex)
```

`bench/calls.py` (`make calls`) runs each workload once under a `sys.setprofile` hook and counts function
calls for both sides: Python-level calls, calls into C, and objects built from HOL datatypes
(dataclass `__init__`). Results go to `bench/out/cpython/calls.json`; `--latex` (on by default with `make calls`)
also writes them as a booktabs tabular to `calls.tex`.

### Impact of caching

`bench/caching.py` (`make bench-caching`) measures the code generator's `python_cache` option,
which memoises values and instances without dictionary arguments with `@functools.cache` (on by
default). It builds every harness once per variant, with `isabelle build -c -D .
-o python_tail_calls=true` and the variant's options, and runs `bench/run.py` on each copy of the
generated code (`--generated`):

| variant | `python_cache` |
|---|---|
| `no_cache` | false |
| `cache` (the default) | true |

`python_tail_calls` is on in both builds: printing self tail calls as loops is
not an optimisation but what keeps deep recursion under Python's recursion limit, so it is part
of the translation being measured, not a variable. The builds take about a minute each and leave
`*/generated/` as it was.

The speedup of `cache` is the median time of `no_cache` divided by its own, with a 95 %
bootstrap interval over the timed runs. In `bench/out/caching/<interpreter>/`:

- `<variant>/results.json`: the benchmark results of each variant
- `summary.md`: times and speedups at the largest size, then at every size
- `caching.tex`: the largest sizes as a booktabs tabular, for `\input` into a paper

There are no separate caching plots: `make plot` draws the reference built without caching
(`no_cache`) into the main benchmark plot, as a grey dotted line, for every interpreter with
caching results.

```bash
make bench-caching                         # build both, benchmark under CPython, report
make bench-caching-pypy                    # the same builds under PyPy (after bench-caching)
make bench-caching CACHING_ARGS="--quick --only smith"
uv run python bench/caching.py report      # rewrite the tables from the existing results
```

`bench/plot.py` also draws the `no_cache` reference of each interpreter it finds there into the
main benchmark graph, as a grey dotted line with that interpreter's marker
(`--no-caching-comparison` leaves it out). Only the `no_cache` variant is needed for that, e.g. under
PyPy: `UV_PROJECT_ENVIRONMENT=.venv-pypy uv run --python pypy@3.11 --no-dev python bench/caching.py run --variants no_cache`.

Both environments share `uv.lock`; PyPy (3.11) is why `requires-python` is `>=3.11`, and its
environment leaves out the dev group (matplotlib), so plotting always runs under CPython. SymPy and
the other libraries run under the same interpreter as the references.

The generated code runs with the interpreter's default recursion limit, so a failure there (e.g.
deep recursion over a long list) shows up as a cross in the plot, and larger sizes are skipped.
PyPy counts recursion depth differently: the three tests that xfail on CPython because of the limit
pass under PyPy.
