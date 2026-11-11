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
stays under Python's recursion limit. `-c` rewrites the generated code even when a session is up
to date. To rebuild a single harness: `isabelle build -d . -c -o python_tail_calls=true Splay_Harness`.

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

## Benchmarks

`bench/run.py` times the generated references against the libraries they are tested against,
on the same workloads (map: insert, look up, delete half, list items; heap: build, drain;
matrices: one random n x n integer matrix). It checks that both sides agree and records medians
in `bench/out/<interpreter>/results.json`, so CPython and PyPy runs sit side by side. Each
measurement is the median of 15 timed runs (`--repeats`) after 10 untimed warm-up runs
(`--warmup`), which PyPy's JIT needs. `bench/plot.py` combines all results into
`bench/out/benchmark.png` (and `.pdf`): time against size per benchmark and interpreter, and the
slowdown of each reference against its library.

```bash
make bench-all                             # CPython, then PyPy, then the plot
make bench                                 # CPython only
make bench-pypy                            # PyPy only
make plot                                  # re-plot everything in bench/out/*/
make bench BENCH_ARGS="--quick --only rbt_map smith"
make calls                                 # function calls, also as LaTeX (calls.tex)
```

`bench/calls.py` (`make calls`) runs each workload once under a `sys.setprofile` hook and counts
function calls for both sides: Python-level calls, calls into C, and objects built from HOL
datatypes (dataclass `__init__`). Results go to `bench/out/cpython/calls.json`.

### Impact of caching

`bench/caching.py` (`make bench-caching`) measures the code generator's `python_cache` option,
which memoises values and instances without dictionary arguments with `@functools.cache` (on by
default). It builds every harness twice, as `no_cache` and `cache` (both with
`python_tail_calls`), and runs `bench/run.py` on each copy of the generated code.

The speedup is the median time of `no_cache` divided by that of `cache`, with a 95 % bootstrap
interval over the timed runs. In `bench/out/caching/<interpreter>/`:

- `<variant>/results.json`: the benchmark results of each variant
- `summary.md`: times and speedups at the largest size, then at every size
- `caching.tex`: the largest sizes as a booktabs tabular, for `\input` into a paper

`make plot` also draws each interpreter's `no_cache` reference into the main benchmark plot as a
grey dotted line (`--no-caching-comparison` leaves it out).

```bash
make bench-caching                         # build both, benchmark under CPython, report
make bench-caching-pypy                    # the same builds under PyPy (after bench-caching)
make bench-caching CACHING_ARGS="--quick --only smith"
uv run python bench/caching.py report      # rewrite the tables from the existing results
```

## License

BSD-3-Clause, see `LICENSE`.
