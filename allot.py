"""
A more fine-grained functools.singledispatch
"""

import types
import weakref
import typing as t
from abc import get_cache_token
from functools import update_wrapper, _find_impl

from get_version import get_version


__version__ = get_version(__file__)


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
        self.dispatch_cache = weakref.WeakKeyDictionary()
        self.cache_token = None
        self.func = func
        self.funcname = getattr(func, "__name__", "allot function")
        update_wrapper(self, func)

    def __call__(self, *args, **kw):
        if not args:
            raise TypeError(f"{self.funcname} requires at least 1 positional argument")

        return self.dispatch(args[0].__class__)(*args, **kw)

    def _clear_cache(self):
        self.dispatch_cache.clear()

    def dispatch(self, cls: t.Type):
        """
        generic_func.dispatch(cls) -> <function implementation>
        Runs the dispatch algorithm to return the best available implementation
        for the given *cls* registered on *generic_func*.
        """
        if self.cache_token is not None:
            current_token = get_cache_token()
            if self.cache_token != current_token:
                self.dispatch_cache.clear()
                self.cache_token = current_token
        try:
            impl = self.dispatch_cache[cls]
        except KeyError:
            try:
                impl = self.registry[cls]
            except KeyError:
                impl = _find_impl(cls, self.registry)
            self.dispatch_cache[cls] = impl
        return impl

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

            # only import typing if annotation parsing is necessary
            from typing import get_type_hints

            argname, cls = next(iter(get_type_hints(func).items()))
            assert isinstance(
                cls, type
            ), f"Invalid annotation for {argname!r}. {cls!r} is not a class."
        self.registry[cls] = func
        if self.cache_token is None and hasattr(cls, "__abstractmethods__"):
            self.cache_token = get_cache_token()
        self.dispatch_cache.clear()
        return func


class allot_method(allot):
    """
    Single-dispatch generic method descriptor.
    Supports wrapping existing descriptors and handles non-descriptor
    callables as instance methods.
    """

    def __get__(self, obj: t.Any, cls: t.Type) -> t.Callable:
        def _method(*args, **kwargs):
            method = self.dispatch(args[0].__class__)
            return method.__get__(obj, cls)(*args, **kwargs)

        _method.__isabstractmethod__ = self.__isabstractmethod__
        _method.register = self.register
        update_wrapper(_method, self.func)
        return _method

    @property
    def __isabstractmethod__(self):
        return getattr(self.func, "__isabstractmethod__", False)
