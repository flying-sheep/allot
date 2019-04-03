allot
=====

Like ``functools.singledispatch``, but will allow to register multiple functions for each class.

If a registered function decides it cannot handle the value after inspecting it, it can give up and let others try their luck.

TODO: This is just a straight port of ``singledispatch`` to a class at the moment.
