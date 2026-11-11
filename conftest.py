import sys

import pytest


@pytest.fixture
def recursion_limit():
    """Set the recursion limit for one test; the old limit is restored afterwards."""
    old = sys.getrecursionlimit()
    yield sys.setrecursionlimit
    sys.setrecursionlimit(old)
