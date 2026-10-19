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
- `smith/`: about 0.1 s per 5 x 5 matrix, so 200 examples per test by default
  (`SNF_EXAMPLES`, `SNF_MAX_DIM`). This relies on importing
  `Jordan_Normal_Form.Matrix_IArray_Impl` in the harness: by default the code generator
  represents matrices as functions, every matrix product then nests closures, and a 3 x 3 matrix
  takes minutes.
