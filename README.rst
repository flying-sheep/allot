allot |b-pypi| |b-travis| |b-codecov|
=====================================

.. |b-pypi| image:: https://img.shields.io/pypi/v/allot.svg
   :target: https://pypi.org/project/allot
.. |b-travis| image:: https://travis-ci.com/flying-sheep/allot.svg?branch=master
   :target: https://travis-ci.com/flying-sheep/allot
.. |b-codecov| image:: https://codecov.io/gh/flying-sheep/allot/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/flying-sheep/allot

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
