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

## Layout

One folder per data structure, e.g. `splay_tree/`:

- `ROOT`, `*.thy`: Isabelle session that exports the code to `generated/`
- `test_*.py`: differential tests against the generated module

To add a data structure, create a new folder in the same way and list it in `ROOTS`.
