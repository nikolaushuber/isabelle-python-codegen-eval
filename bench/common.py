"""Paths and helpers shared by the benchmark scripts."""
import os
import platform

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "bench", "out")
INTERPRETER = platform.python_implementation().lower()        # "cpython" or "pypy"
MATRIX_LABEL = "n (n x n matrix)"


def is_matrix(label):
    """Whether a benchmark's size is the n of an n x n matrix (rather than a count of elements)."""
    return label == MATRIX_LABEL
