# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import functools
import logging
import time


class cached_property(object):
  """Like @property, except that the result of get is cached on
  self.{'_' + fn.__name__}.

  NOTE: This implementation is not threadsafe.

  >>> class Test(object):
  ...  @cached_property
  ...  def foo(self):
  ...   print "hello"
  ...   return 10
  ...
  >>> t = Test()
  >>> t.foo
  hello
  10
  >>> t.foo
  10
  >>> t.foo = 20
  >>> t.foo
  20
  >>> del t.foo
  >>> t.foo
  hello
  10
  >>>
  """
  def __init__(self, fn):
    self.func = fn
    self._iname = "_" + fn.__name__
    functools.update_wrapper(self, fn)

  def __get__(self, inst, cls=None):
    if inst is None:
      return self
    if not hasattr(inst, self._iname):
      val = self.func(inst)
      # Some methods call out to another layer to calculate the value. This
      # higher layer will assign directly to the property, so we have to do
      # the extra hasattr here to determine if the value has been set as a side
      # effect of func()
      if not hasattr(inst, self._iname):
        setattr(inst, self._iname, val)
    return getattr(inst, self._iname)

  def __delete__(self, inst):
    assert inst is not None
    if hasattr(inst, self._iname):
      delattr(inst, self._iname)


def instance_decorator(dec):
  """Allows a decorator to access 'self'.

  Note: there is a bug in pylint that triggers false positives on decorated
  decorators with arguments. See http://goo.gl/Ln6uyn for details, but in the
  mean time you may have to disable no-value-for-parameter for any code using
  this.
  """
  def layer(self, *args, **kwargs):  # pragma: no cover
    def inner_layer(f):
      return dec(self, f, *args, **kwargs)
    return inner_layer
  return layer


class exponential_retry(object):
  """Decorator which retries the function if an exception is encountered."""

  def __init__(self, tries=5, delay=1.0):
    self.tries = max(1, tries)
    self.delay = max(0, delay)

  def __call__(self, f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):  # pragma: no cover
      retry_delay = self.delay
      for i in xrange(self.tries):
        try:
          return f(*args, **kwargs)
        except Exception:
          if (i+1) >= self.tries:
            raise
          logging.exception('Exception encountered, retrying in %.1f second(s)',
                            retry_delay)
          time.sleep(retry_delay)
          retry_delay *= 2
    return wrapper
