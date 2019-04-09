import pytest

from allot import allot, allot_method, Pass, AllotError


def test_pass_basic():
    @allot
    def g(obj):
        return "base"

    @g.register(int)
    def f_small_integer(i):
        if i > 10:
            return Pass
        return "small integer"

    assert g("notint") == "base"
    assert g(1) == "small integer"
    assert g(11) == "base"


def test_pass_error():
    @allot
    def g(obj):
        return Pass

    with pytest.raises(AllotError, match=r"of g pass for object 'something'"):
        g("something")


def test_pass_error_method():
    class C:
        @allot_method
        def m(self, obj):
            return Pass

    with pytest.raises(AllotError, match=r"of m pass for object 'thing'"):
        C().m("thing")
