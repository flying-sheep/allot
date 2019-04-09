allot
=====

Like ``functools.singledispatch``, but will allow to register multiple functions for each class.

If a registered function decides it cannot handle the value after inspecting it, it can give up and let others try their luck:

.. code:: python

   from allot import allot, Pass

   @allot
   def f(obj):
       return 'object'

   @f.register(int)
   def f_small_integer(obj):
       if obj > 10:
           return Pass
       return 'small integer'

   assert f('a string') == 'object'
   assert f(3) == 'small integer'
   assert f(10) == 'object'
