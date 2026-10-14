import os
import sys

# The generator is a single module at the repository root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Importing generate_report reads the token at import time; it is never used by these tests.
os.environ.setdefault("GITHUB_TOKEN", "test-token")


import pytest


@pytest.fixture(autouse=True)
def forget_hidden_names():
    """Names hidden from the log by one test must not carry into the next."""
    yield
    import generate_report as g
    g._scrubber.clear()
