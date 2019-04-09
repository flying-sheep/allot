"""
A more fine-grained functools.singledispatch
"""

import typing as t
from functools import update_wrapper, _compose_mro

from get_version import get_version


__version__ = get_version(__file__)


Pass = object()


class allot:
    """
    Single-dispatch generic function decorator.
    Transforms a function into a generic function, which can have different
    behaviours depending upon the type of its first argument. The decorated
    function acts as the default implementation, and additional
    implementations can be registered using the register() attribute of the
    generic function.
    """

    def __init__(self, func: t.Callable):
        if not callable(func) and not hasattr(func, "__get__"):
            raise TypeError(f"{func!r} is not callable or a descriptor")

        self.registry = {object: func}
        self.func = func
        self.funcname = getattr(func, "__name__", "allot function")
        update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        if not args:
            raise TypeError(f"{self.funcname} requires at least 1 positional argument")

        for func in self.dispatch(args[0].__class__):
            rv = func(*args, **kwargs)
            if rv is not Pass:
                return rv

        raise AllotError(args[0], self)

    def dispatch(self, cls: t.Type) -> t.Generator[t.Callable, None, None]:
        """
        generic_func.dispatch(cls) -> <function implementation>
        Runs the dispatch algorithm to return the best available implementation
        for the given *cls* registered on *generic_func*.
        """
        mro = _compose_mro(cls, self.registry.keys())
        match = None
        for typ in mro:
            if match is not None:
                # If *match* is an implicit ABC but there is another unrelated,
                # equally matching implicit ABC, refuse the temptation to guess.
                if (
                    typ in self.registry
                    and typ not in cls.__mro__
                    and match not in cls.__mro__
                    and not issubclass(match, typ)
                ):
                    raise RuntimeError(f"Ambiguous dispatch: {match} or {typ}")
                yield self.registry.get(match)
            if typ in self.registry:
                match = typ
        yield self.registry.get(match)

    def register(self, cls: t.Type, func: t.Optional[t.Callable] = None) -> t.Callable:
        """
        generic_func.register(cls, func) -> func
        Registers a new implementation for the given *cls* on a *generic_func*.
        """
        if func is None:
            if isinstance(cls, type):
                return lambda f: self.register(cls, f)
            ann = getattr(cls, "__annotations__", {})
            if not ann:
                raise TypeError(
                    f"Invalid first argument to `register()`: {cls!r}. "
                    f"Use either `@register(some_class)` or plain `@register` "
                    f"on an annotated function."
                )
            func = cls

            argname, cls = next(iter(t.get_type_hints(func).items()))
            assert isinstance(
                cls, type
            ), f"Invalid annotation for {argname!r}. {cls!r} is not a class."
        self.registry[cls] = func
        return func


class allot_method(allot):
    """
    Single-dispatch generic method descriptor.
    Supports wrapping existing descriptors and handles non-descriptor
    callables as instance methods.
    """

    def __get__(self, obj: t.Any, cls: t.Type) -> t.Callable:
        def _method(*args, **kwargs):
            for method in self.dispatch(args[0].__class__):
                method = method.__get__(obj, cls)
                rv = method(*args, **kwargs)
                if rv is not Pass:
                    return rv
            raise AllotError(args[0], self)

        _method.__isabstractmethod__ = self.__isabstractmethod__
        _method.register = self.register
        update_wrapper(_method, self.func)
        return _method

    @property
    def __isabstractmethod__(self):
        return getattr(self.func, "__isabstractmethod__", False)


class AllotError(LookupError):
    """
    Exception thrown when all 
    """

    def __init__(self, obj: t.Any, allot: allot):
        super().__init__()
        self.obj = obj
        self.allot = allot

    def __str__(self) -> str:
        return (
            f"All matching registered functions of {self.allot.funcname} "
            f"pass for object {self.obj!r} (of class {type(self.obj)!r})."
        )
