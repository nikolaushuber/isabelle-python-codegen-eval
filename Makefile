# Build the Isabelle harnesses, run the differential tests, and benchmark the generated
# references in CPython (.venv) and PyPy (.venv-pypy).

ISABELLE ?= isabelle
UV ?= uv
PYPY ?= pypy@3.11
# extra arguments for bench/run.py, e.g. make bench BENCH_ARGS="--quick --only rbt_map"
BENCH_ARGS ?=
# extra arguments for bench/calls.py, e.g. make calls CALLS_ARGS="--elements 10000"
CALLS_ARGS ?=

CPYTHON_RUN = $(UV) run
PYPY_RUN = UV_PROJECT_ENVIRONMENT=.venv-pypy $(UV) run --python $(PYPY) --no-dev

.PHONY: default build test test-pypy test-all pypy-env bench bench-pypy bench-all plot calls clean-bench

default: test

# regenerate */generated/ for every harness listed in ROOTS
build:
	$(ISABELLE) build -c -D .

test:
	$(CPYTHON_RUN) pytest

test-pypy: pypy-env
	$(PYPY_RUN) pytest

test-all: test test-pypy

# create or update the PyPy environment (downloads PyPy on first use)
pypy-env:
	UV_PROJECT_ENVIRONMENT=.venv-pypy $(UV) sync --python $(PYPY) --no-dev

# results go to bench/out/cpython/ and bench/out/pypy/
bench:
	$(CPYTHON_RUN) python bench/run.py $(BENCH_ARGS)

bench-pypy: pypy-env
	$(PYPY_RUN) python bench/run.py $(BENCH_ARGS)

bench-all: bench bench-pypy plot

# compares every bench/out/*/results.json in bench/out/benchmark.png and .pdf (matplotlib: CPython only)
plot:
	$(CPYTHON_RUN) python bench/plot.py

# function calls per benchmark, reference vs library (sys.setprofile hook, CPython):
# bench/out/cpython/calls.json and calls.tex (LaTeX tabular)
calls:
	$(CPYTHON_RUN) python bench/calls.py --latex $(CALLS_ARGS)

clean-bench:
	rm -rf bench/out/cpython bench/out/pypy bench/out/benchmark.png bench/out/benchmark.pdf
