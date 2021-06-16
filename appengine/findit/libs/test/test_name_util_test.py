# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from libs import test_name_util
from waterfall.test import wf_testcase


class TestNameUtilTest(wf_testcase.WaterfallTestCase):

  def testRemoveAllPrefixesFromGTestNameNoPrefix(self):
    test = 'abc_test'
    self.assertEqual(test, test_name_util.RemoveAllPrefixesFromGTestName(test))

  def testReplaceAllPrefixesFromGTestNameWithMaskNoPrefix(self):
    test = 'abc_test'
    self.assertEqual(
        test, test_name_util.ReplaceAllPrefixesFromGtestNameWithMask(test))

  def testRemoveAllPrefixesFromGTestName(self):
    test = 'abc_test.PRE_PRE_test1'
    self.assertEqual('abc_test.test1',
                     test_name_util.RemoveAllPrefixesFromGTestName(test))

  def testRemoveMaskedPrefixesFromGTestName(self):
    test = 'abc_test.*test1'
    self.assertEqual('abc_test.test1',
                     test_name_util.RemoveAllPrefixesFromGTestName(test))

  def testReplaceAllPrefixesFromGTestNameWithMask(self):
    test = 'abc_test.PRE_PRE_test1'
    self.assertEqual(
        'abc_test.*test1',
        test_name_util.ReplaceAllPrefixesFromGtestNameWithMask(test))

  def testRemoveValueParametersFromGTestName(self):
    test_name = 'A/ColorSpaceTest.testNullTransform/12'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

    test_name = 'A/ColorSpaceTest.testNullTransform/bcd'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testRemoveMaskedValueParametersFromGTestNames(self):
    test_name = '*/ColorSpaceTest.testNullTransform/*'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testReplaceValueParametersFromGTestNameWithMask(self):
    test_name = 'A/ColorSpaceTest.testNullTransform/12'
    self.assertEqual(
        '*/ColorSpaceTest.testNullTransform/*',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

    test_name = 'A/ColorSpaceTest.testNullTransform/bcd'
    self.assertEqual(
        '*/ColorSpaceTest.testNullTransform/*',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

  def testRemoveValueParametersWithoutInstantiationName(self):
    test_name = 'ColorSpaceTest.testNullTransform/12'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

    test_name = 'ColorSpaceTest.testNullTransform/bcd'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testRemoveMaskedValueParametersWithoutInstantiationName(self):
    test_name = 'ColorSpaceTest.testNullTransform/*'
    self.assertEqual('ColorSpaceTest.testNullTransform',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testReplaceValueParametersWithMaskWithoutInstantiationName(self):
    test_name = 'ColorSpaceTest.testNullTransform/12'
    self.assertEqual(
        'ColorSpaceTest.testNullTransform/*',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

    test_name = 'ColorSpaceTest.testNullTransform/bcd'
    self.assertEqual(
        'ColorSpaceTest.testNullTransform/*',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

  def testRemoveTypeParametersFromGTestName(self):
    test_name = '1/FixedCommandTest/4.InvalidCommand'
    self.assertEqual('FixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

    test_name = '1/FixedCommandTest/bcd.InvalidCommand'
    self.assertEqual('FixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testRemoveMaskedTypeParametersFromGTestName(self):
    test_name = '*/FixedCommandTest/*.InvalidCommand'
    self.assertEqual('FixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testReplaceTypeParametersFromGTestNameWithMask(self):
    test_name = '1/FixedCommandTest/4.InvalidCommand'
    self.assertEqual(
        '*/FixedCommandTest/*.InvalidCommand',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

    test_name = '1/FixedCommandTest/bcd.InvalidCommand'
    self.assertEqual(
        '*/FixedCommandTest/*.InvalidCommand',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

  def testRemoveTypeParametersWithoutInstantiationName(self):
    test_name = 'FixedCommandTest/4.InvalidCommand'
    self.assertEqual('FixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

    test_name = 'FixedCommandTest/bcd.InvalidCommand'
    self.assertEqual('FixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testRemoveMaskedTypeParametersWithoutInstantiationName(self):
    test_name = 'FixedCommandTest/*.InvalidCommand'
    self.assertEqual('FixedCommandTest.InvalidCommand',
                     test_name_util.RemoveParametersFromGTestName(test_name))

  def testReplaceTypeParametersWithMaskWithoutInstantiationName(self):
    test_name = 'FixedCommandTest/4.InvalidCommand'
    self.assertEqual(
        'FixedCommandTest/*.InvalidCommand',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

    test_name = 'FixedCommandTest/bcd.InvalidCommand'
    self.assertEqual(
        'FixedCommandTest/*.InvalidCommand',
        test_name_util.ReplaceParametersFromGtestNameWithMask(test_name))

  def testRemoveQueriesFromBlinkWebTests(self):
    test_name = 'external/wpt/editing/run/inserttext.html?2001-last'
    self.assertEqual(
        'external/wpt/editing/run/inserttext.html',
        test_name_util.RemoveSuffixFromBlinkWebTestName(test_name))

  def testRemoveMaskedQueriesFromBlinkWebTests(self):
    test_name = 'external/wpt/editing/run/inserttext.html?*'
    self.assertEqual(
        'external/wpt/editing/run/inserttext.html',
        test_name_util.RemoveSuffixFromBlinkWebTestName(test_name))

  def testReplaceQueriesFromBlinkWebTestsWithMask(self):
    test_name = 'external/wpt/editing/run/inserttext.html?2001-last'
    self.assertEqual(
        'external/wpt/editing/run/inserttext.html?*',
        test_name_util.ReplaceSuffixFromBlinkWebTestNameWithMask(test_name))

  def testRemoveVirtualLayersFromBlinkWebTestName(self):
    virtual_test_name = 'virtual/wpt/editing/run/inserttext.html'
    test_name = 'editing/run/inserttext.html'
    self.assertEqual(
        test_name,
        test_name_util.RemoveVirtualLayersFromBlinkWebTestName(
            virtual_test_name))
    self.assertEqual(
        test_name,
        test_name_util.RemoveVirtualLayersFromBlinkWebTestName(test_name))

  def testGetTestSuiteName(self):
    self.assertEqual(
        'a/b/c',
        test_name_util.GetTestSuiteName('a/b/c/page.html',
                                        'blink_web_tests'))
    self.assertIsNone(
        test_name_util.GetTestSuiteName('page.html', 'blink_web_tests'))
    self.assertEqual(
        'suite', test_name_util.GetTestSuiteName('suite.test', 'browser_tests'))
    self.assertEqual(
        'ClassName',
        test_name_util.GetTestSuiteName('org.chromium.package.ClassName#testA',
                                        'base_junittests'))
    self.assertIsNone(
        test_name_util.GetTestSuiteName('__main__.ChromeDriver.testA',
                                        'chromedriver_py_tests'))
