import re
import sys
import decimal
import collections
import functools
import abc
import typing
from itertools import permutations
from contextlib import contextmanager

import pytest

from allot import allot, allot_method


def test_simple_overloads():
    @allot
    def g(obj):
        return "base"

    def g_int(i):
        return "integer"

    g.register(int, g_int)
    assert g("str") == "base"
    assert g(1) == "integer"
    assert g([1, 2, 3]) == "base"


def test_mro():
    @allot
    def g(obj):
        return "base"

    class A:
        pass

    class C(A):
        pass

    class B(A):
        pass

    class D(C, B):
        pass

    def g_A(a):
        return "A"

    def g_B(b):
        return "B"

    g.register(A, g_A)
    g.register(B, g_B)
    assert g(A()) == "A"
    assert g(B()) == "B"
    assert g(C()) == "A"
    assert g(D()) == "B"


def test_register_decorator():
    @allot
    def g(obj):
        return "base"

    @g.register(int)
    def g_int(i):
        return "int %s" % (i,)

    assert g("") == "base"
    assert g(12) == "int 12"
    assert next(g.dispatch(int)) is g_int
    assert next(g.dispatch(object)) is next(g.dispatch(str))
    # Note: in the assert above this is not g.
    # @singledispatch returns the wrapper.


def test_wrapping_attributes():
    @allot
    def g(obj):
        "Simple test"
        return "Test"

    assert g.__name__ == "g"
    if sys.flags.optimize < 2:
        assert g.__doc__ == "Simple test"


def test_c_classes():
    @allot
    def g(obj):
        return "base"

    @g.register(decimal.DecimalException)
    def _(obj):
        return obj.args

    subn = decimal.Subnormal("Exponent < Emin")
    rnd = decimal.Rounded("Number got rounded")
    assert g(subn) == ("Exponent < Emin",)
    assert g(rnd) == ("Number got rounded",)

    @g.register(decimal.Subnormal)
    def _(obj):
        return "Too small to care."

    assert g(subn) == "Too small to care."
    assert g(rnd) == ("Number got rounded",)


def test_compose_mro():
    # None of the examples in this test depend on haystack ordering.
    c = collections.abc
    mro = functools._compose_mro
    bases = [c.Sequence, c.MutableMapping, c.Mapping, c.Set]
    for haystack in permutations(bases):
        m = mro(dict, haystack)
        assert m == [
            dict,
            c.MutableMapping,
            c.Mapping,
            c.Collection,
            c.Sized,
            c.Iterable,
            c.Container,
            object,
        ]
    bases = [c.Container, c.Mapping, c.MutableMapping, collections.OrderedDict]
    for haystack in permutations(bases):
        m = mro(collections.ChainMap, haystack)
        assert m == [
            collections.ChainMap,
            c.MutableMapping,
            c.Mapping,
            c.Collection,
            c.Sized,
            c.Iterable,
            c.Container,
            object,
        ]

    # If there's a generic function with implementations registered for
    # both Sized and Container, passing a defaultdict to it results in an
    # ambiguous dispatch which will cause a RuntimeError (see
    # test_mro_conflicts).
    bases = [c.Container, c.Sized, str]
    for haystack in permutations(bases):
        m = mro(collections.defaultdict, [c.Sized, c.Container, str])
        assert m == [collections.defaultdict, dict, c.Sized, c.Container, object]

    # MutableSequence below is registered directly on D. In other words, it
    # precedes MutableMapping which means single dispatch will always
    # choose MutableSequence here.
    class D(collections.defaultdict):
        pass

    c.MutableSequence.register(D)
    bases = [c.MutableSequence, c.MutableMapping]
    for haystack in permutations(bases):
        m = mro(D, bases)
        assert m == [
            D,
            c.MutableSequence,
            c.Sequence,
            c.Reversible,
            collections.defaultdict,
            dict,
            c.MutableMapping,
            c.Mapping,
            c.Collection,
            c.Sized,
            c.Iterable,
            c.Container,
            object,
        ]

    # Container and Callable are registered on different base classes and
    # a generic function supporting both should always pick the Callable
    # implementation if a C instance is passed.
    class C(collections.defaultdict):
        def __call__(self):
            pass

    bases = [c.Sized, c.Callable, c.Container, c.Mapping]
    for haystack in permutations(bases):
        m = mro(C, haystack)
        assert m == [
            C,
            c.Callable,
            collections.defaultdict,
            dict,
            c.Mapping,
            c.Collection,
            c.Sized,
            c.Iterable,
            c.Container,
            object,
        ]


def test_register_abc():
    c = collections.abc
    d = {"a": "b"}
    l = [1, 2, 3]
    s = {object(), None}
    f = frozenset(s)
    t = (1, 2, 3)

    @allot
    def g(obj):
        return "base"

    assert g(d) == "base"
    assert g(l) == "base"
    assert g(s) == "base"
    assert g(f) == "base"
    assert g(t) == "base"
    g.register(c.Sized, lambda obj: "sized")
    assert g(d) == "sized"
    assert g(l) == "sized"
    assert g(s) == "sized"
    assert g(f) == "sized"
    assert g(t) == "sized"
    g.register(c.MutableMapping, lambda obj: "mutablemapping")
    assert g(d) == "mutablemapping"
    assert g(l) == "sized"
    assert g(s) == "sized"
    assert g(f) == "sized"
    assert g(t) == "sized"
    g.register(collections.ChainMap, lambda obj: "chainmap")
    assert g(d) == "mutablemapping"  # irrelevant ABCs registered
    assert g(l) == "sized"
    assert g(s) == "sized"
    assert g(f) == "sized"
    assert g(t) == "sized"
    g.register(c.MutableSequence, lambda obj: "mutablesequence")
    assert g(d) == "mutablemapping"
    assert g(l) == "mutablesequence"
    assert g(s) == "sized"
    assert g(f) == "sized"
    assert g(t) == "sized"
    g.register(c.MutableSet, lambda obj: "mutableset")
    assert g(d) == "mutablemapping"
    assert g(l) == "mutablesequence"
    assert g(s) == "mutableset"
    assert g(f) == "sized"
    assert g(t) == "sized"
    g.register(c.Mapping, lambda obj: "mapping")
    assert g(d) == "mutablemapping"  # not specific enough
    assert g(l) == "mutablesequence"
    assert g(s) == "mutableset"
    assert g(f) == "sized"
    assert g(t) == "sized"
    g.register(c.Sequence, lambda obj: "sequence")
    assert g(d) == "mutablemapping"
    assert g(l) == "mutablesequence"
    assert g(s) == "mutableset"
    assert g(f) == "sized"
    assert g(t) == "sequence"
    g.register(c.Set, lambda obj: "set")
    assert g(d) == "mutablemapping"
    assert g(l) == "mutablesequence"
    assert g(s) == "mutableset"
    assert g(f) == "set"
    assert g(t) == "sequence"
    g.register(dict, lambda obj: "dict")
    assert g(d) == "dict"
    assert g(l) == "mutablesequence"
    assert g(s) == "mutableset"
    assert g(f) == "set"
    assert g(t) == "sequence"
    g.register(list, lambda obj: "list")
    assert g(d) == "dict"
    assert g(l) == "list"
    assert g(s) == "mutableset"
    assert g(f) == "set"
    assert g(t) == "sequence"
    g.register(set, lambda obj: "concrete-set")
    assert g(d) == "dict"
    assert g(l) == "list"
    assert g(s) == "concrete-set"
    assert g(f) == "set"
    assert g(t) == "sequence"
    g.register(frozenset, lambda obj: "frozen-set")
    assert g(d) == "dict"
    assert g(l) == "list"
    assert g(s) == "concrete-set"
    assert g(f) == "frozen-set"
    assert g(t) == "sequence"
    g.register(tuple, lambda obj: "tuple")
    assert g(d) == "dict"
    assert g(l) == "list"
    assert g(s) == "concrete-set"
    assert g(f) == "frozen-set"
    assert g(t) == "tuple"


def test_c3_abc():
    c = collections.abc
    mro = functools._c3_mro

    class A(object):
        pass

    class B(A):
        def __len__(self):
            return 0  # implies Sized

    @c.Container.register
    class C(object):
        pass

    class D(object):
        pass  # unrelated

    class X(D, C, B):
        def __call__(self):
            pass  # implies Callable

    expected = [X, c.Callable, D, C, c.Container, B, c.Sized, A, object]
    for abcs in permutations([c.Sized, c.Callable, c.Container]):
        assert mro(X, abcs=abcs) == expected
    # unrelated ABCs don't appear in the resulting MRO
    many_abcs = [c.Mapping, c.Sized, c.Callable, c.Container, c.Iterable]
    assert mro(X, abcs=many_abcs) == expected


def test_false_meta():
    # see issue23572
    class MetaA(type):
        def __len__(self):
            return 0

    class A(metaclass=MetaA):
        pass

    class AA(A):
        pass

    @allot
    def fun(a):
        return "base A"

    @fun.register(A)
    def _(a):
        return "fun A"

    aa = AA()
    assert fun(aa) == "fun A"


def test_mro_conflicts():
    c = collections.abc

    @allot
    def g(arg):
        return "base"

    class O(c.Sized):
        def __len__(self):
            return 0

    o = O()
    assert g(o) == "base"
    g.register(c.Iterable, lambda arg: "iterable")
    g.register(c.Container, lambda arg: "container")
    g.register(c.Sized, lambda arg: "sized")
    g.register(c.Set, lambda arg: "set")
    assert g(o) == "sized"
    c.Iterable.register(O)
    assert g(o) == "sized"  # because it's explicitly in __mro__
    c.Container.register(O)
    assert g(o) == "sized"  # see above: Sized is in __mro__
    c.Set.register(O)
    assert g(o) == "set"  # because c.Set is a subclass of
    # c.Sized and c.Container
    class P:
        pass

    p = P()
    assert g(p) == "base"
    c.Iterable.register(P)
    assert g(p) == "iterable"
    c.Container.register(P)
    with pytest.raises(RuntimeError) as re_one:
        g(p)
    assert str(re_one.value) in (
        (
            "Ambiguous dispatch: <class 'collections.abc.Container'> "
            "or <class 'collections.abc.Iterable'>"
        ),
        (
            "Ambiguous dispatch: <class 'collections.abc.Iterable'> "
            "or <class 'collections.abc.Container'>"
        ),
    )

    class Q(c.Sized):
        def __len__(self):
            return 0

    q = Q()
    assert g(q) == "sized"
    c.Iterable.register(Q)
    assert g(q) == "sized"  # because it's explicitly in __mro__
    c.Set.register(Q)
    assert g(q) == "set"  # because c.Set is a subclass of
    # c.Sized and c.Iterable
    @allot
    def h(arg):
        return "base"

    @h.register(c.Sized)
    def _(arg):
        return "sized"

    @h.register(c.Container)
    def _(arg):
        return "container"

    # Even though Sized and Container are explicit bases of MutableMapping,
    # this ABC is implicitly registered on defaultdict which makes all of
    # MutableMapping's bases implicit as well from defaultdict's
    # perspective.
    with pytest.raises(RuntimeError) as re_two:
        h(collections.defaultdict(lambda: 0))
    assert str(re_two.value) in (
        (
            "Ambiguous dispatch: <class 'collections.abc.Container'> "
            "or <class 'collections.abc.Sized'>"
        ),
        (
            "Ambiguous dispatch: <class 'collections.abc.Sized'> "
            "or <class 'collections.abc.Container'>"
        ),
    )

    class R(collections.defaultdict):
        pass

    c.MutableSequence.register(R)

    @allot
    def i(arg):
        return "base"

    @i.register(c.MutableMapping)
    def _(arg):
        return "mapping"

    @i.register(c.MutableSequence)
    def _(arg):
        return "sequence"

    r = R()
    assert i(r) == "sequence"

    class S:
        pass

    class T(S, c.Sized):
        def __len__(self):
            return 0

    t = T()
    assert h(t) == "sized"
    c.Container.register(T)
    assert h(t) == "sized"  # because it's explicitly in the MRO

    class U:
        def __len__(self):
            return 0

    u = U()
    assert h(u) == "sized"  # implicit Sized subclass inferred
    # from the existence of __len__()
    c.Container.register(U)
    # There is no preference for registered versus inferred ABCs.
    with pytest.raises(RuntimeError) as re_three:
        h(u)
    assert str(re_three.value) in (
        (
            "Ambiguous dispatch: <class 'collections.abc.Container'> "
            "or <class 'collections.abc.Sized'>"
        ),
        (
            "Ambiguous dispatch: <class 'collections.abc.Sized'> "
            "or <class 'collections.abc.Container'>"
        ),
    )

    class V(c.Sized, S):
        def __len__(self):
            return 0

    @allot
    def j(arg):
        return "base"

    @j.register(S)
    def _(arg):
        return "s"

    @j.register(c.Container)
    def _(arg):
        return "container"

    v = V()
    assert j(v) == "s"
    c.Container.register(V)
    assert j(v) == "container"  # because it ends up right after
    # Sized in the MRO


@contextmanager
def swap_attr(obj, attr, new_val):
    if hasattr(obj, attr):
        real_val = getattr(obj, attr)
        setattr(obj, attr, new_val)
        try:
            yield real_val
        finally:
            setattr(obj, attr, real_val)
    else:
        setattr(obj, attr, new_val)
        try:
            yield
        finally:
            if hasattr(obj, attr):
                delattr(obj, attr)


def test_annotations():
    @allot
    def i(arg):
        return "base"

    @i.register
    def _(arg: collections.abc.Mapping):
        return "mapping"

    @i.register
    def _(arg: "collections.abc.Sequence"):
        return "sequence"

    assert i(None) == "base"
    assert i({"a": 1}) == "mapping"
    assert i([1, 2, 3]) == "sequence"
    assert i((1, 2, 3)) == "sequence"
    assert i("str") == "sequence"

    # Registering classes as callables doesn't work with annotations,
    # you need to pass the type explicitly.
    @i.register(str)
    class _:
        def __init__(self, arg):
            self.arg = arg

        def __eq__(self, other):
            return self.arg == other

    assert i("str") == "str"


def test_method_register():
    class A:
        @allot_method
        def t(self, arg):
            self.arg = "base"

        @t.register(int)
        def _(self, arg):
            self.arg = "int"

        @t.register(str)
        def _(self, arg):
            self.arg = "str"

    a = A()

    a.t(0)
    assert a.arg == "int"
    aa = A()
    assert not hasattr(aa, "arg")
    a.t("")
    assert a.arg == "str"
    aa = A()
    assert not hasattr(aa, "arg")
    a.t(0.0)
    assert a.arg == "base"
    aa = A()
    assert not hasattr(aa, "arg")


def test_staticmethod_register():
    class A:
        @allot_method
        @staticmethod
        def t(arg):
            return arg

        @t.register(int)
        @staticmethod
        def _(arg):
            return isinstance(arg, int)

        @t.register(str)
        @staticmethod
        def _(arg):
            return isinstance(arg, str)

    a = A()

    assert A.t(0)
    assert A.t("")
    assert A.t(0.0) == 0.0


def test_classmethod_register():
    class A:
        def __init__(self, arg):
            self.arg = arg

        @allot_method
        @classmethod
        def t(cls, arg):
            return cls("base")

        @t.register(int)
        @classmethod
        def _(cls, arg):
            return cls("int")

        @t.register(str)
        @classmethod
        def _(cls, arg):
            return cls("str")

    assert A.t(0).arg == "int"
    assert A.t("").arg == "str"
    assert A.t(0.0).arg == "base"


def test_callable_register():
    class A:
        def __init__(self, arg):
            self.arg = arg

        @allot_method
        @classmethod
        def t(cls, arg):
            return cls("base")

    @A.t.register(int)
    @classmethod
    def _(cls, arg):
        return cls("int")

    @A.t.register(str)
    @classmethod
    def _(cls, arg):
        return cls("str")

    assert A.t(0).arg == "int"
    assert A.t("").arg == "str"
    assert A.t(0.0).arg == "base"


def test_abstractmethod_register():
    class Abstract(abc.ABCMeta):
        @allot_method
        @abc.abstractmethod
        def add(self, x, y):
            pass

    assert Abstract.add.__isabstractmethod__


def test_type_ann_register():
    class A:
        @allot_method
        def t(self, arg):
            return "base"

        @t.register
        def _(self, arg: int):
            return "int"

        @t.register
        def _(self, arg: str):
            return "str"

    a = A()

    assert a.t(0) == "int"
    assert a.t("") == "str"
    assert a.t(0.0) == "base"


def test_invalid_registrations():
    msg_prefix = "Invalid first argument to `register()`: "
    msg_suffix = (
        ". Use either `@register(some_class)` or plain `@register` on an "
        "annotated function."
    )

    @allot
    def i(arg):
        return "base"

    with pytest.raises(TypeError) as exc:

        @i.register(42)
        def _(arg):
            return "I annotated with a non-type"

    assert str(exc.value).startswith(msg_prefix + "42")
    assert str(exc.value).endswith(msg_suffix)
    with pytest.raises(TypeError) as exc:

        @i.register
        def _(arg):
            return "I forgot to annotate"

    assert str(exc.value).startswith(
        msg_prefix + "<function test_invalid_registrations.<locals>._"
    )
    assert str(exc.value).endswith(msg_suffix)

    # FIXME: The following will only work after PEP 560 is implemented.
    return

    with pytest.raises(TypeError) as exc:

        @i.register
        def _(arg: typing.Iterable[str]):
            # At runtime, dispatching on generics is impossible.
            # When registering implementations with singledispatch, avoid
            # types from `typing`. Instead, annotate with regular types
            # or ABCs.
            return "I annotated with a generic collection"

    assert str(exc.value).startswith(
        msg_prefix
        + "<function TestSingleDispatch.test_invalid_registrations.<locals>._"
    )
    assert str(exc.value).endswith(msg_suffix)


def test_invalid_positional_argument():
    @allot
    def f(*args):
        pass

    msg = "f requires at least 1 positional argument"
    with pytest.raises(TypeError, match=re.escape(msg)):
        f()
