from allot import allot, allot_method, Pass


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
