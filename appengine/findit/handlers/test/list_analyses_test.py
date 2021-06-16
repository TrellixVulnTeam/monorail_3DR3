# Copyright 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
import datetime

import webapp2

from testing_utils import testing

from handlers import list_analyses
from libs import analysis_status
from model.wf_analysis import WfAnalysis
from model import result_status
from services import build_failure_analysis


class ListAnalysesTest(testing.AppengineTestCase):
  app_module = webapp2.WSGIApplication(
      [
          ('/list-analyses', list_analyses.ListAnalyses),
      ], debug=True)

  def setUp(self):
    super(ListAnalysesTest, self).setUp()

    self.stored_dates = self._AddAnalysisResults()

  def testListAnalysesHandler(self):
    response = self.test_app.get('/list-analyses')
    self.assertEqual(200, response.status_int)

  def _AddAnalysisResult(self, master_name, builder_name, build_number):
    analysis = WfAnalysis.Create(master_name, builder_name, build_number)
    analysis.status = analysis_status.RUNNING
    analysis.put()
    return analysis

  def _GetSuspectedCLs(self, analysis_result):
    """Returns the suspected CLs we found in analysis."""
    suspected_cls = []
    if not analysis_result or not analysis_result['failures']:
      return suspected_cls

    for failure in analysis_result['failures']:
      for suspected_cl in failure['suspected_cls']:
        cl_info = {
            'repo_name': suspected_cl['repo_name'],
            'revision': suspected_cl['revision'],
            'commit_position': suspected_cl['commit_position'],
            'url': suspected_cl['url']
        }
        if cl_info not in suspected_cls:
          suspected_cls.append(cl_info)
    return suspected_cls

  def _AddAnalysisResults(self):
    """Create and store dummy data."""
    analyses = []
    stored_dates = {}

    def StoreTestBuildDate(analysis_number, start_time):
      if datetime:  # pragma: no cover
        stored_dates[analysis_number] = start_time.strftime(
            '%Y-%m-%d %H:%M:%S UTC')

    for i in range(0, 10):
      analyses.append(self._AddAnalysisResult('m', 'b', i))

    self._AddAnalysisResult('chromium.linux', 'Linux GN', 26120)
    analyses.append(WfAnalysis.Get('chromium.linux', 'Linux GN', 26120))

    analyses[1].status = analysis_status.COMPLETED
    analyses[2].status = analysis_status.COMPLETED
    analyses[3].status = analysis_status.COMPLETED
    analyses[4].status = analysis_status.ERROR
    analyses[7].status = analysis_status.COMPLETED
    analyses[9].status = analysis_status.COMPLETED
    analyses[10].status = analysis_status.COMPLETED

    analyses[2].build_start_time = datetime.datetime.utcnow()
    StoreTestBuildDate(2, analyses[2].build_start_time)
    analyses[7].build_start_time = (
        datetime.datetime.utcnow() - datetime.timedelta(6))
    StoreTestBuildDate(7, analyses[7].build_start_time)
    analyses[10].build_start_time = (
        datetime.datetime.utcnow() - datetime.timedelta(4))
    StoreTestBuildDate(10, analyses[10].build_start_time)

    analyses[1].result = {
        'failures': [{
            'step_name':
                'b',
            'first_failure':
                1,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 1,
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': None,
                'score': 5,
                'hints': {
                    'added x/y/f99_1.cc (and it was in log)': 5,
                },
            }],
        }]
    }

    analyses[2].result = {
        'failures': [{
            'step_name': 'a',
            'first_failure': 2,
            'last_pass': None,
            'supported': True,
            'suspected_cls': [],
        }, {
            'step_name': 'b',
            'first_failure': 1,
            'last_pass': None,
            'supported': True,
            'suspected_cls': [],
        }]
    }

    analyses[3].result = {
        'failures': [{
            'step_name': 'a',
            'first_failure': 3,
            'last_pass': None,
            'supported': True,
            'suspected_cls': [],
        }, {
            'step_name': 'b',
            'first_failure': 2,
            'last_pass': None,
            'supported': True,
            'suspected_cls': [],
        }]
    }

    analyses[7].result = {
        'failures': [{
            'step_name':
                'a',
            'first_failure':
                7,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 7,
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None,
                'score': 1,
                'hints': {
                    'modified f99_2.cc (and it was in log)': 1,
                },
            }, {
                'build_number': 7,
                'repo_name': 'chromium',
                'revision': 'r99_6',
                'commit_position': None,
                'url': None,
                'score': 5,
                'hints': {
                    'added x/y/f99_7.cc (and it was in log)': 5,
                },
            }],
        }, {
            'step_name':
                'b',
            'first_failure':
                7,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 7,
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': 'https://chromium.googlesource.com/chromium/'
                       'src/r99_1',
                'score': 5,
                'hints': {
                    'added x/y/f99_1.cc (and it was in log)': 5,
                },
            }],
        }]
    }

    analyses[9].result = {
        'failures': [{
            'step_name': 'a',
            'first_failure': 9,
            'last_pass': None,
            'supported': True,
            'suspected_cls': [],
        }, {
            'step_name':
                'b',
            'first_failure':
                9,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 9,
                'repo_name': 'chromium',
                'revision': 'r99_9',
                'commit_position': None,
                'url': None,
                'score': 1,
                'hints': {
                    'modified f99_9.cc (and it was in log)': 1,
                },
            }],
        }]
    }

    analyses[10].result = {
        'failures': [{
            'step_name':
                'a',
            'first_failure':
                10,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 10,
                'repo_name': 'chromium',
                'revision': 'r99_10',
                'commit_position': None,
                'url': None,
                'score': 5,
                'hints': {
                    'added x/f99_10.cc (and it was in log)': 5,
                },
            }],
        }, {
            'step_name':
                'b',
            'first_failure':
                10,
            'last_pass':
                None,
            'supported':
                True,
            'suspected_cls': [{
                'build_number': 10,
                'repo_name': 'chromium',
                'revision': 'r99_10',
                'commit_position': None,
                'url': None,
                'score': 1,
                'hints': {
                    'modified x/f99_9.cc (and it was in log)': 1,
                },
            }],
        }]
    }

    for analysis in analyses:
      analysis.suspected_cls = self._GetSuspectedCLs(analysis.result)
      analysis.result_status = (
          build_failure_analysis.GetResultAnalysisStatus(analysis.result))
      analysis.put()

    analyses[1].result_status = result_status.FOUND_INCORRECT
    analyses[1].put()
    analyses[3].result_status = result_status.NOT_FOUND_INCORRECT
    analyses[3].put()
    analyses[10].result_status = result_status.FOUND_CORRECT
    analyses[10].put()

    return stored_dates

  def testDisplayAggregatedBuildAnalysisResults(self):
    """Basic test case, no parameters."""
    expected_result = {
        'analyses': [{
            'master_name':
                'chromium.linux',
            'builder_name':
                'Linux GN',
            'build_number':
                26120,
            'build_start_time':
                self.stored_dates.get(10),
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_10',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Correct - Found'
        }, {
            'master_name':
                'm',
            'builder_name':
                'b',
            'build_number':
                1,
            'build_start_time':
                None,
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Incorrect - Found'
        }, {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 3,
            'build_start_time': None,
            'failure_type': 'test',
            'status': 70,
            'status_description': 'Completed',
            'suspected_cls': [],
            'result_status': 'Incorrect - Not Found'
        }],
        'triage':
            '',
        'days':
            '',
        'count':
            '',
        'result_status':
            ''
    }

    response_json = self.test_app.get('/list-analyses?format=json')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testDisplayAggregatedBuildAnalysisResultsTriage(self):
    """Test for parameter triage."""
    expected_result = {
        'analyses': [{
            'master_name':
                'm',
            'builder_name':
                'b',
            'build_number':
                1,
            'build_start_time':
                None,
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Incorrect - Found'
        }, {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 3,
            'build_start_time': None,
            'failure_type': 'test',
            'status': 70,
            'status_description': 'Completed',
            'suspected_cls': [],
            'result_status': 'Incorrect - Not Found'
        }, {
            'master_name':
                'm',
            'builder_name':
                'b',
            'build_number':
                7,
            'build_start_time':
                self.stored_dates.get(7),
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_2',
                'commit_position': None,
                'url': None
            }, {
                'repo_name': 'chromium',
                'revision': 'r99_6',
                'commit_position': None,
                'url': None
            }, {
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': 'https://chromium.googlesource.com'
                       '/chromium/src/r99_1'
            }],
            'result_status':
                'Untriaged - Found'
        }, {
            'master_name':
                'm',
            'builder_name':
                'b',
            'build_number':
                9,
            'build_start_time':
                None,
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_9',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Untriaged - Found'
        }, {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 2,
            'build_start_time': self.stored_dates.get(2),
            'failure_type': 'test',
            'status': 70,
            'status_description': 'Completed',
            'suspected_cls': [],
            'result_status': 'Untriaged - Not Found'
        }],
        'triage':
            '1',
        'days':
            '',
        'count':
            '',
        'result_status':
            ''
    }

    response_json = self.test_app.get('/list-analyses?format=json&triage=1')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testDisplayAggregatedBuildAnalysisResultsCount(self):
    """Test for parameter count."""
    expected_result = {
        'analyses': [{
            'master_name':
                'chromium.linux',
            'builder_name':
                'Linux GN',
            'build_number':
                26120,
            'build_start_time':
                self.stored_dates.get(10),
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_10',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Correct - Found'
        }, {
            'master_name':
                'm',
            'builder_name':
                'b',
            'build_number':
                1,
            'build_start_time':
                None,
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Incorrect - Found'
        }],
        'triage':
            '',
        'days':
            '',
        'count':
            '2',
        'result_status':
            ''
    }

    response_json = self.test_app.get('/list-analyses?format=json&count=2')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testDisplayAggregatedBuildAnalysisResultsResultStatus(self):
    """Test for parameter result_status."""
    expected_result = {
        'analyses': [{
            'master_name':
                'm',
            'builder_name':
                'b',
            'build_number':
                1,
            'build_start_time':
                None,
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Incorrect - Found'
        }],
        'triage':
            '',
        'days':
            '',
        'count':
            '',
        'result_status':
            '10'
    }

    response_json = self.test_app.get(
        '/list-analyses?format=json&result_status=10')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def DisplayAggregatedBuildAnalysisResultsDays(self):  # pragma: no cover
    """Test for parameter days. Parameter triage will be turned off.

    This test case will only run locally, because it may cause flaky failure.
    """
    expected_result = {
        'analyses': [{
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 2,
            'build_start_time': self.stored_dates.get(2),
            'failure_type': 'test',
            'status': 70,
            'status_description': 'Completed',
            'suspected_cls': [],
            'result_status': 'Untriaged - Not Found'
        }, {
            'master_name':
                'chromium.linux',
            'builder_name':
                'Linux GN',
            'build_number':
                26120,
            'build_start_time':
                self.stored_dates.get(10),
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_10',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Correct - Found'
        }],
        'triage':
            '1',
        'days':
            '5',
        'count':
            '',
        'result_status':
            ''
    }

    response_json = self.test_app.get(
        '/list-analyses?format=json&triage=1&days=5')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def DisplayAggregatedBuildAnalysisResultsStatusDays(self):  # pragma: no cover
    """Test for parameter combination days and result status.

    This test case will only run locally, because it may cause flaky failure.
    """
    expected_result = {
        'analyses': [{
            'master_name':
                'chromium.linux',
            'builder_name':
                'Linux GN',
            'build_number':
                26120,
            'build_start_time':
                self.stored_dates.get(10),
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_10',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Correct - Found'
        }],
        'triage':
            '',
        'days':
            '6',
        'count':
            '',
        'result_status':
            '0'
    }

    response_json = self.test_app.get(
        '/list-analyses?format=json&result_status=0&days=6')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)

  def testResultStatusIsNotSpecified(self):
    expected_result = {
        'analyses': [{
            'master_name':
                'chromium.linux',
            'builder_name':
                'Linux GN',
            'build_number':
                26120,
            'build_start_time':
                self.stored_dates.get(10),
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_10',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Correct - Found'
        }, {
            'master_name':
                'm',
            'builder_name':
                'b',
            'build_number':
                1,
            'build_start_time':
                None,
            'failure_type':
                'test',
            'status':
                70,
            'status_description':
                'Completed',
            'suspected_cls': [{
                'repo_name': 'chromium',
                'revision': 'r99_1',
                'commit_position': None,
                'url': None
            }],
            'result_status':
                'Incorrect - Found'
        }, {
            'master_name': 'm',
            'builder_name': 'b',
            'build_number': 3,
            'build_start_time': None,
            'failure_type': 'test',
            'status': 70,
            'status_description': 'Completed',
            'suspected_cls': [],
            'result_status': 'Incorrect - Not Found'
        }],
        'triage':
            '',
        'days':
            '',
        'count':
            '',
        'result_status':
            ''
    }

    response_json = self.test_app.get(
        '/list-analyses?format=json&result_status=')
    self.assertEqual(200, response_json.status_int)
    self.assertEqual(expected_result, response_json.json_body)
