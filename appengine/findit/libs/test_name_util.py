# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility functions for processing test names."""

import re

# Regular expression used to get the suite name of a normalized gtest name.
GTEST_REGEX = re.compile(r'^([a-zA-Z_]\w*)\.[a-zA-Z_]\w*$')

# Used to identify the prefix in gtests.
_GTEST_PREFIXES = ['PRE_', '*']

# Regular expressions to identify parameterized gtests. Note that instantiation
# names can be empty. For example: ColorSpaceTest.testNullTransform/1.
_VALUE_PARAMETERIZED_GTESTS_REGEX = re.compile(
    r'^([\w\*]+/)?(\w+\.\w+)/[\w\*]+$')
_TYPE_PARAMETERIZED_GTESTS_REGEX = re.compile(
    r'^([\w\*]+/)?(\w+)/[\w\*]+\.(\w+)$')

# Regular expression for a blink_web_test name.
_LAYOUT_TEST_NAME_PATTERN = re.compile(r'^(([^/]+/)+[^/]+\.[a-zA-Z]+).*$')
_VIRTUAL_LAYOUT_TEST_NAME_PATTERN = re.compile(r'^virtual/[^/]+/(.*)$')

# Regular expression used to get the suite name of a normalized java test name.
_JAVA_TEST_REGEX = re.compile(r'(?:[a-zA-Z_]\w*\.)*([a-zA-Z_]\w*)#[a-zA-Z_]\w+')


def RemoveParametersFromGTestName(test_name):
  """Removes parameters from parameterized gtest names.

  There are two types of parameterized gtest: value-parameterized tests and
  type-paramerized tests, and for example:
  value-parameterized:
    'A/ColorSpaceTest.testNullTransform/11'
  type-parameterized:
    '1/GLES2DecoderPassthroughFixedCommandTest/5.InvalidCommand'

  After removing the parameters, the examples become
  'ColorSpaceTest.testNullTransform' and
  'GLES2DecoderPassthroughFixedCommandTest.InvalidCommand' respectively.

  For more information of parameterized gtests, please refer to:
  https://github.com/google/googletest/blob/master/googletest/docs/
  AdvancedGuide.md
  """
  value_match = _VALUE_PARAMETERIZED_GTESTS_REGEX.match(test_name)
  if value_match:
    return value_match.group(2)

  type_match = _TYPE_PARAMETERIZED_GTESTS_REGEX.match(test_name)
  if type_match:
    return type_match.group(2) + '.' + type_match.group(3)

  return test_name


def ReplaceParametersFromGtestNameWithMask(test_name):
  """Replaces the parameters parts of gtest names with mask: '*'.

  This method works the same way as |RemoveParametersFromGTestName| except that
  the parameters parts are replaced with '*' instead of being removed. For
  example, 'A/suite.test/8' -> '*/suite.test/*'.

  Args:
    test_name: Original test names, may contain parameters.

  Returns:
    A test name with parameters being replaced with '*'.
  """
  value_match = _VALUE_PARAMETERIZED_GTESTS_REGEX.match(test_name)
  if value_match:
    suite_test = value_match.group(2)
    prefix_mask = '*/' if value_match.group(1) else ''
    return '%s%s/*' % (prefix_mask, suite_test)

  type_match = _TYPE_PARAMETERIZED_GTESTS_REGEX.match(test_name)
  if type_match:
    suite = type_match.group(2)
    test = type_match.group(3)
    prefix_mask = '*/' if type_match.group(1) else ''
    return '%s%s/*.%s' % (prefix_mask, suite, test)

  return test_name


def RemoveAllPrefixesFromGTestName(test):
  """Removes prefixes from test names.

  Args:
    test (str): A test's name, eg: 'suite1.PRE_test1'.

  Returns:
    base_test (str): A base test name, eg: 'suite1.test1'.
  """
  test_name_start = max(test.find('.'), 0)
  if test_name_start == 0:
    return test

  test_suite = test[:test_name_start]
  test_name = test[test_name_start + 1:]

  for prefix in _GTEST_PREFIXES:
    while test_name.startswith(prefix):
      test_name = test_name[len(prefix):]

  base_test = '%s.%s' % (test_suite, test_name)
  return base_test


def ReplaceAllPrefixesFromGtestNameWithMask(test_name):
  """Replaces the prefixes parts of gtest names with mask: '*'.

  This method works the same way as |RemoveAllPrefixesFromGTestName| except that
  the prefixes parts are replaced with '*' instead of being removed. For
  example, 'suite.PRE_PRE_test' -> 'suite.*test'.

  Args:
    test_name: Original test names, may contain parameters.

  Returns:
    A test name with prefixes being replaced with '*'.
  """
  test_name_without_prefixes = RemoveAllPrefixesFromGTestName(test_name)
  if test_name_without_prefixes == test_name:
    return test_name

  suite = test_name_without_prefixes.split('.')[0]
  test = test_name_without_prefixes.split('.')[1]
  return '%s.*%s' % (suite, test)


def RemoveSuffixFromBlinkWebTestName(test_name):
  """Removes suffix part from blink_web_test names if applicable.

  For example, 'external/wpt/editing/run/delete.html?1001-2000' should become
  'external/wpt/editing/run/delete.html' after removing the queries.

  Args:
    test_name: Name of the test to be processed.

  Returns:
    A string representing the name after removing suffix.
  """
  match = _LAYOUT_TEST_NAME_PATTERN.match(test_name)
  if match:
    return match.group(1)

  return test_name


def ReplaceSuffixFromBlinkWebTestNameWithMask(test_name):
  """Replaces the suffix parts of blink_web_test names with mask: '*'.

  This method works the same way as |RemoveSuffixFromBlinkWebTestName|
  except that the suffix parts are replaced with '*' instead of being removed.
  For example, 'external/delete.html?1001-2000' -> 'external/delete.html?*'.

  Args:
    test_name: Original test names, may contain suffixes.

  Returns:
    A test name with suffixes being replaced with '*'.
  """
  test_name_without_suffixes = RemoveSuffixFromBlinkWebTestName(test_name)
  if test_name_without_suffixes == test_name:
    return test_name

  return '%s?*' % test_name_without_suffixes


def RemoveVirtualLayersFromBlinkWebTestName(test_name):
  """Removes virtual layers from blink_web_test names if applicable.

  For example, 'virtual/abc/def/g.html' should become 'def/g.html' after
  removing the layers.

  Args:
    test_name: Name of the test to be processed.

  Returns:
    A string representing the name after removing virtual layers.
  """
  match = _VIRTUAL_LAYOUT_TEST_NAME_PATTERN.match(test_name)
  if match:
    return match.group(1)

  return test_name


def GetTestSuiteName(normalized_test_name, step_ui_name):
  """Returns the test suite name of the given test in the given test step.

  Assumption:
    * All gtests are in suite.test format, while other tests are not.
    * All webkit layout tests are in path/to/file.html format.
    * All Java tests are in package.path.to.ClassName#testCase format.
  Currently, only supports these three types, for other type of tests,
  returns None.

  Args:
    normalized_test_name: A normalized test name.

  Returns:
    The test suite name if it's gtest/layout test/java test, otherwise None.
  """
  # TODO(crbug.com/1050188): remove 'webkit_layout_tests' after 2 weeks from the
  # step rename is completed.
  # For blink_web_tests, the suite name is the immediate directory.
  if 'webkit_layout_tests' in step_ui_name or 'blink_web_tests' in step_ui_name:
    index = normalized_test_name.rfind('/')
    if index > 0:
      return normalized_test_name[:index]
    return None

  # For gtests, the suite name is the class name.
  gtest_match = GTEST_REGEX.match(normalized_test_name)
  if gtest_match:
    return gtest_match.group(1)

  # For Java tests, the suite name is the class name.
  java_match = _JAVA_TEST_REGEX.match(normalized_test_name)
  if java_match:
    return java_match.group(1)

  return None
