# Copyright 2014 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import mock
import unittest

from libs import time_util


class TimeUtilTest(unittest.TestCase):

  def testConvertToTimestamp(self):
    self.assertEqual(
        1490918400, time_util.ConvertToTimestamp(
            datetime(2017, 03, 31, 0, 0, 0)))

  def testRemoveMicrosecondsFromDelta(self):
    date1 = datetime(2016, 5, 1, 1, 1, 1, 1)
    date2 = datetime(2016, 5, 1, 1, 1, 1, 2)
    delta = date2 - date1

    self.assertEqual(
        time_util.RemoveMicrosecondsFromDelta(delta).microseconds, 0)

  def testFormatTimedelta(self):
    self.assertIsNone(time_util.FormatTimedelta(None))
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 0)), '00:00:00')
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 1)), '00:00:01')
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 60)), '00:01:00')
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 3600)), '01:00:00')
    self.assertEqual(time_util.FormatTimedelta(timedelta(0, 0, 1)), '00:00:00')
    self.assertEqual(
        time_util.FormatTimedelta(
            datetime(2018, 1, 2, 1) - datetime(2018, 1, 1, 1), with_days=True),
        '1 day, 00:00:00')
    self.assertEqual(
        time_util.FormatTimedelta(
            datetime(2018, 1, 3, 1) - datetime(2018, 1, 1), with_days=True),
        '2 days, 01:00:00')

  def testFormatDatetime(self):
    self.assertIsNone(time_util.FormatDatetime(None))
    self.assertEqual(
        time_util.FormatDatetime(datetime(2016, 1, 2, 1, 2, 3)),
        '2016-01-02 01:02:03 UTC')
    self.assertEqual(
        time_util.FormatDatetime(datetime(2016, 1, 2, 1, 2, 3), day_only=True),
        '2016-01-02')

  def testFormatDuration(self):
    date1 = datetime(2016, 5, 1, 1, 1, 1)
    date2 = datetime(2016, 5, 1, 1, 2, 1)
    self.assertIsNone(time_util.FormatDuration(None, date1))
    self.assertIsNone(time_util.FormatDuration(date1, None))
    self.assertEqual('00:01:00', time_util.FormatDuration(date1, date2))

  def testMicrosecondsToDatetime(self):
    self.assertEqual(
        datetime(2016, 2, 1, 22, 59, 34),
        time_util.MicrosecondsToDatetime(1454367574000000))
    self.assertIsNone(time_util.MicrosecondsToDatetime(None))

  def testTimeZoneInfo(self):
    naive_time = datetime(2016, 9, 1, 10, 0, 0)

    tz = time_util.TimeZoneInfo('+0800')
    self.assertEqual(tz.LocalToUTC(naive_time), datetime(2016, 9, 1, 2, 0, 0))

    tz_negative = time_util.TimeZoneInfo('-0700')
    self.assertEqual(
        tz_negative.LocalToUTC(naive_time), datetime(2016, 9, 1, 17, 0, 0))

  def testDatetimeFromString(self):
    self.assertEqual(None, time_util.DatetimeFromString('None'))
    self.assertEqual(None, time_util.DatetimeFromString(None))
    iso_time_str = '2016-01-02T01:02:03.123456'
    iso_time_datetime = time_util.DatetimeFromString(iso_time_str)
    # Check that our function reverses datetime.isoformat
    self.assertEqual(iso_time_datetime.isoformat(), iso_time_str)
    self.assertEqual(iso_time_datetime,
                     time_util.DatetimeFromString(iso_time_datetime))

    bq_time_str = '	2018-03-27 08:39:00 UTC'
    bq_time_datetime = datetime(2018, 3, 27, 8, 39)
    self.assertEqual(bq_time_datetime,
                     time_util.DatetimeFromString(bq_time_str))
    with self.assertRaises(ValueError):
      time_util.DatetimeFromString('Yesterday, at 5 o\'clock')

  def testSecondsToHMS(self):
    self.assertIsNone(time_util.SecondsToHMS(None))
    self.assertEqual('00:00:00', time_util.SecondsToHMS(0))
    self.assertEqual('00:00:01', time_util.SecondsToHMS(1))
    self.assertEqual('00:01:01', time_util.SecondsToHMS(61))

  def testGetMostRecentUTCMidnight(self):
    self.assertEqual(datetime, type(time_util.GetMostRecentUTCMidnight()))

  @mock.patch.object(
      time_util,
      'GetMostRecentUTCMidnight',
      return_value=datetime(2017, 3, 19, 0, 0, 0))
  def testGetStartEndDates(self, _):
    self.assertEqual(
        (datetime(2017, 3, 18, 0, 0, 0), datetime(2017, 3, 20, 0, 0, 0)),
        time_util.GetStartEndDates(None, None))
    self.assertEqual((None, datetime(2017, 3, 20, 0, 0, 0)),
                     time_util.GetStartEndDates(None, '2017-03-19'))
    self.assertEqual(
        (datetime(2017, 3, 18, 0, 0, 0), datetime(2017, 3, 20, 0, 0, 0)),
        time_util.GetStartEndDates('2017-03-18', None))
    self.assertEqual(
        (datetime(2017, 3, 15, 0, 0, 0), datetime(2017, 3, 16, 0, 0, 0)),
        time_util.GetStartEndDates('2017-03-15', '2017-03-16'))

  @mock.patch.object(
      time_util,
      'GetMostRecentUTCMidnight',
      return_value=datetime(2017, 3, 19, 0, 0, 0))
  def testGetStartEndDatesDefaultStartDefaultEnd(self, _):
    default_start = datetime(2017, 3, 15, 0, 0, 0)
    default_end = datetime(2017, 3, 16, 0, 0, 0)
    self.assertEqual((default_start, default_end),
                     time_util.GetStartEndDates(
                         None,
                         None,
                         default_start=default_start,
                         default_end=default_end))
    self.assertEqual((default_start, datetime(2017, 3, 20, 0, 0, 0)),
                     time_util.GetStartEndDates(
                         None, '2017-03-19', default_start=default_start))

    self.assertEqual((datetime(2017, 3, 18, 0, 0, 0), default_end),
                     time_util.GetStartEndDates(
                         '2017-03-18', None, default_end=default_end))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 4, 27, 8, 0, 0))
  def testGetPSTNow(self, _):
    self.assertEqual(datetime(2017, 4, 27, 0, 0, 0), time_util.GetPSTNow())

  def testConvertPSTToUTC(self):
    self.assertEqual(
        datetime(2017, 4, 27, 8, 0, 0),
        time_util.ConvertPSTToUTC(datetime(2017, 4, 27, 0, 0, 0)))

  def testConvertUTCToPST(self):
    self.assertEqual(
        datetime(2017, 4, 27, 0, 0, 0),
        time_util.ConvertUTCToPST(datetime(2017, 4, 27, 8, 0, 0)))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 4, 27, 8, 0, 0))
  def testGetDatetimeBeforeNow(self, _):
    self.assertEqual(
        datetime(2017, 4, 26, 8, 0, 0), time_util.GetDatetimeBeforeNow(days=1))
    self.assertEqual(
        datetime(2017, 4, 27, 7, 0, 0), time_util.GetDatetimeBeforeNow(hours=1))
    self.assertEqual(
        datetime(2017, 4, 26, 7, 0, 0),
        time_util.GetDatetimeBeforeNow(days=1, hours=1))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2018, 4, 27, 8, 0, 0))
  def testGetPreviousWeekMonday(self, _):
    self.assertEqual(
        datetime(2018, 4, 16, 0, 0, 0), time_util.GetPreviousWeekMonday())

  def testGetMidnight(self):
    self.assertEqual(
        datetime(2018, 4, 16, 0, 0, 0),
        time_util.GetMidnight(datetime(2018, 4, 16, 1, 2, 3)))
