import pytest

from allot import allot, allot_method, Pass


def test_allot_nofunc():
    with pytest.raises(TypeError):
        allot("not a func")
