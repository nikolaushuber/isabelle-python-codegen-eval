# isabelle-python-eval

Differential tests for the [Isabelle Python code generator](https://github.com/pure-py/isabelle-python-codegen):
verified data structures from the AFP are exported to Python and checked against
established Python libraries using Hypothesis.

## Requirements

- Isabelle2025-2 with the `isabelle-python-codegen` and AFP components registered
- [uv](https://docs.astral.sh/uv/)

## Usage

```bash
isabelle build -d . -c Splay_Harness   # regenerate splay_tree/generated/Splay_Ref.py
uv run pytest -v                       # run all tests
```

`-c` forces a rebuild, so the generated code is rewritten even when the
session is up to date.

## Layout

One folder per data structure, e.g. `splay_tree/`:

- `ROOT`, `*.thy`: Isabelle session that exports the code to `generated/`
- `test_*.py`: differential tests against the generated module

To add a data structure, create a new folder in the same way and list it in `ROOTS`.
