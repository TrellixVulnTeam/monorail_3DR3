# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from datetime import datetime
from datetime import timedelta
import json
import logging
import mock
import time

from google.appengine.api import app_identity
from google.appengine.ext import ndb

from common import constants
from common.findit_http_client import FinditHttpClient
from common.swarmbucket import swarmbucket
from common.waterfall import buildbucket_client
from common.waterfall import failure_type
from common.waterfall import try_job_error
from gae_libs import token
from gae_libs.gitiles.cached_gitiles_repository import CachedGitilesRepository
from libs import analysis_status
from libs import time_util
from model import result_status
from model.flake.analysis.flake_try_job import FlakeTryJob
from model.flake.analysis.flake_try_job_data import FlakeTryJobData
from model.wf_analysis import WfAnalysis
from model.wf_build import WfBuild
from model.wf_failure_group import WfFailureGroup
from model.wf_try_job import WfTryJob
from model.wf_try_job_data import WfTryJobData
from services import step_util
from services import swarmbot_util
from services import try_job as try_job_service
from services.parameters import BuildKey
from services.parameters import CompileFailureInfo
from services.parameters import CompileHeuristicResult
from services.parameters import CompileTryJobResult
from services.parameters import RunCompileTryJobParameters
from waterfall import buildbot
from waterfall import waterfall_config
from waterfall.build_info import BuildInfo
from waterfall.test import wf_testcase

_GIT_REPO = CachedGitilesRepository(
    FinditHttpClient(), 'https://chromium.googlesource.com/chromium/src.git')
_CACHE_NAME = (
    'builder_7543a2f22277aaf500e7e9818483b610fa70d34ae4dcf8c4ff9711ff6795d7fd')


class TryJobTest(wf_testcase.WaterfallTestCase):

  def setUp(self):
    super(TryJobTest, self).setUp()
    self.patcher = mock.patch('services.swarmbot_util.GetBotsByDimension')
    self.patcher.start()

  def tearDown(self):
    self.patcher.stop()
    super(TryJobTest, self).tearDown()

  def testShouldBailOutIfBuildHasNoStartTime(self):
    build = WfBuild.Create('m', 'b', 1)
    build.start_time = None
    self.assertTrue(try_job_service._ShouldBailOutForOutdatedBuild(build))

  def testShouldBailOutforOutdatedBuild(self):
    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create('m', 'b', 1)
    build.start_time = yesterday
    self.assertTrue(try_job_service._ShouldBailOutForOutdatedBuild(build))

    build.start_time = yesterday + timedelta(hours=1)
    self.assertFalse(try_job_service._ShouldBailOutForOutdatedBuild(build))

  def testBlameListsIntersect(self):
    self.assertFalse(try_job_service._BlameListsIntersection(['0'], ['1']))
    self.assertFalse(try_job_service._BlameListsIntersection(['1'], []))
    self.assertFalse(try_job_service._BlameListsIntersection([], []))
    self.assertTrue(try_job_service._BlameListsIntersection(['1'], ['1']))
    self.assertTrue(
        try_job_service._BlameListsIntersection(['0', '1'], ['1', '2']))
    self.assertTrue(try_job_service._BlameListsIntersection(['1'], ['1', '2']))

  def testLinkAnalysisToBuildFailureGroup(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    failure_group_key = ['m2', 'b2', 2]
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    try_job_service._LinkAnalysisToBuildFailureGroup(
        master_name, builder_name, build_number, failure_group_key)
    self.assertEqual(
        failure_group_key,
        WfAnalysis.Get(master_name, builder_name,
                       build_number).failure_group_key)

  def testNotNeedANewWaterfallTryJobIfBuildNotCompleted(self):
    master_name = 'master3'
    builder_name = 'builder3'
    build_number = 225

    self.assertFalse(
        try_job_service.NeedANewWaterfallTryJob(master_name, builder_name,
                                                build_number, False, False))

  @mock.patch.object(
      try_job_service, '_ShouldBailOutForOutdatedBuild', return_value=True)
  def testBailOutForTryJobWithOutdatedTimestamp(self, _):
    master_name = 'master1'
    builder_name = 'builder1'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()

    yesterday = datetime.utcnow() - timedelta(days=1)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.start_time = yesterday
    build.put()

    self.assertFalse(
        try_job_service.NeedANewWaterfallTryJob(master_name, builder_name,
                                                build_number, False))

  @mock.patch.object(
      time_util, 'GetUTCNow', return_value=datetime(2017, 9, 6, 0, 0, 0))
  def testNeedANewWaterfallTryJob(self, _):
    master_name = 'master1'
    builder_name = 'builder1'
    build_number = 223
    WfAnalysis.Create(master_name, builder_name, build_number).put()

    yesterday = datetime(2017, 9, 5, 20, 0, 0, 0)
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.start_time = yesterday
    build.put()

    self.assertTrue(
        try_job_service.NeedANewWaterfallTryJob(master_name, builder_name,
                                                build_number, False))

  def testNeedANewWaterfallTryJobForce(self):
    master_name = 'master1'
    builder_name = 'builder1'
    build_number = 223

    self.assertTrue(
        try_job_service.NeedANewWaterfallTryJob(master_name, builder_name,
                                                build_number, True))

  def testSecondAnalysisFailureGroupKeySet(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    master_name_2 = 'm2'
    blame_list = ['a']
    WfAnalysis.Create(master_name, builder_name, build_number).put()
    # Run pipeline with signals that have certain failed output nodes.
    # Observe new group creation.
    self.assertTrue(
        try_job_service.IsBuildFailureUniqueAcrossPlatforms(
            master_name, builder_name, build_number, failure_type.COMPILE,
            blame_list, None, []))

    groups = WfFailureGroup.query(
        WfFailureGroup.build_failure_type == failure_type.COMPILE).fetch()
    WfAnalysis.Create(master_name_2, builder_name, build_number).put()
    # Run pipeline with signals that have the same failed output nodes.
    # Observe no new group creation.
    self.assertFalse(
        try_job_service.IsBuildFailureUniqueAcrossPlatforms(
            master_name_2, builder_name, build_number, failure_type.COMPILE,
            blame_list, None, groups))
    analysis_2 = WfAnalysis.Get(master_name_2, builder_name, build_number)
    self.assertEqual([master_name, builder_name, build_number],
                     analysis_2.failure_group_key)

  def testGetMatchingFailureGroups(self):
    self.assertEqual([],
                     try_job_service.GetMatchingFailureGroups(
                         failure_type.UNKNOWN))

  @mock.patch.object(try_job_service, '_BlameListsIntersection')
  def testGetMatchingGroup(self, mock_fn):
    group1 = WfFailureGroup.Create('m', 'b1', 123)
    group1.suspected_tuples = [['m', 'b1', 123]]
    group1.put()
    group2 = WfFailureGroup.Create('m', 'b2', 123)
    group2.suspected_tuples = [['m', 'b2', 123]]
    group2.put()
    group3 = WfFailureGroup.Create('m', 'b3', 123)
    group3.suspected_tuples = [['m', 'b3', 123]]
    group3.put()
    groups = [group1, group2, group3]
    mock_fn.side_effect = [False, True, True]
    self.assertEqual(
        group3, try_job_service._GetMatchingGroup(groups, [],
                                                  [['m', 'b3', 123]]))

  def testReviveOrCreateTryJobEntityNoTryJob(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1
    result, try_job_key = try_job_service.ReviveOrCreateTryJobEntity(
        master_name, builder_name, build_number, False)
    self.assertTrue(result)
    self.assertIsNotNone(try_job_key)

  def testReviveOrCreateTryJobEntityForce(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfTryJob.Create(master_name, builder_name, build_number).put()
    result, try_job_key = try_job_service.ReviveOrCreateTryJobEntity(
        master_name, builder_name, build_number, True)

    self.assertTrue(result)
    self.assertIsNotNone(try_job_key)

  def testReviveOrCreateTryJobEntityNoNeed(self):
    master_name = 'm1'
    builder_name = 'b'
    build_number = 1

    WfTryJob.Create(master_name, builder_name, build_number).put()
    result, try_job_key = try_job_service.ReviveOrCreateTryJobEntity(
        master_name, builder_name, build_number, False)

    self.assertFalse(result)
    self.assertIsNotNone(try_job_key)

  def testGetSuspectsFromHeuristicResult(self):
    heuristic_result = CompileHeuristicResult.FromSerializable({
        'failures': [{
            'step_name': 'compile',
            'suspected_cls': [
                {
                    'revision': 'r1',
                },
                {
                    'revision': 'r2',
                },
            ],
        },]
    })
    expected_suspected_revisions = ['r1', 'r2']
    self.assertEqual(
        expected_suspected_revisions,
        try_job_service.GetSuspectsFromHeuristicResult(heuristic_result))

  def testNoSuspectsIfNoHeuristicResult(self):

    self.assertEqual([], try_job_service.GetSuspectsFromHeuristicResult(None))

  def testGetResultAnalysisStatusWithTryJobCulpritNotFoundUntriaged(self):
    # Heuristic analysis provided no results, but the try job found a culprit.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_UNTRIAGED
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultAnalysisStatusWithTryJobCulpritNotFoundCorrect(self):
    # Heuristic analysis found no results, which was correct. In this case, the
    # try job result is actually a false positive.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_CORRECT
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultanalysisStatusWithTryJobCulpritNotFoundIncorrect(self):
    # Heuristic analysis found no results and was triaged to incorrect before a
    # try job result was found. In this case the try job result should override
    # the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_INCORRECT
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultanalysisStatusWithTryJobCulpritNoHeuristicResult(self):
    # In this case, the try job found a result before the heuristic result is
    # available. This case should generally never happen, as heuristic analysis
    # is usually much faster than try jobs.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))

    self.assertEqual(status, result_status.FOUND_UNTRIAGED)

  def testGetResultanalysisStatusWithNoTryJobCulpritNoHeuristicResult(self):
    # In this case, the try job completed faster than heuristic analysis
    # (which should never happen) but no results were found.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.put()

    result = {}

    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))
    self.assertIsNone(status)

  def testGetResultanalysisStatusWithTryJobCulpritAndHeuristicResult(self):
    # In this case, heuristic analysis found the correct culprit. The try job
    # result should not overwrite it.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.FOUND_CORRECT
    analysis.put()

    result = {
        'culprit': {
            'compile': {
                'revision': 'rev1',
                'commit_position': 1,
                'url': 'url_1',
                'repo_name': 'chromium'
            }
        }
    }

    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))
    self.assertEqual(status, result_status.FOUND_CORRECT)

  def testGetResultanalysisStatusWithNoCulpritTriagedCorrect(self):
    # In this case, heuristic analysis correctly found no culprit and was
    # triaged, and the try job came back with nothing. The try job result should
    # not overwrite the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_CORRECT
    analysis.put()

    result = {}

    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))
    self.assertEqual(status, result_status.NOT_FOUND_CORRECT)

  def testGetResultanalysisStatusWithNoCulpritTriagedIncorrect(self):
    # In this case, heuristic analysis correctly found no culprit and was
    # triaged, and the try job came back with nothing. The try job result should
    # not overwrite the heuristic result.
    analysis = WfAnalysis.Create('m', 'b', 1)
    analysis.result_status = result_status.NOT_FOUND_INCORRECT
    analysis.put()

    result = {}
    status = try_job_service.GetResultAnalysisStatus(
        analysis, CompileTryJobResult.FromSerializable(result))
    self.assertEqual(status, result_status.NOT_FOUND_INCORRECT)

  @mock.patch.object(buildbot, 'CreateBuildbucketUrl')
  def testGetBuildPropertiesWithSuspectedRevision(self, mock_build_url):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    build_url = 'https://ci.chromium.org/b/800000000001'
    mock_build_url.return_value = build_url

    pipeline_input = RunCompileTryJobParameters(
        build_key=BuildKey(
            master_name=master_name,
            builder_name=builder_name,
            build_number=build_number),
        good_revision='1',
        bad_revision='2',
        suspected_revisions=['rev'])

    expected_properties = {
        'recipe': 'findit/chromium/compile',
        'good_revision': '1',
        'bad_revision': '2',
        'target_mastername': master_name,
        'referenced_build_url': build_url,
        'suspected_revisions': ['rev']
    }
    properties = try_job_service.GetBuildProperties(pipeline_input,
                                                    failure_type.COMPILE)

    self.assertEqual(properties, expected_properties)

  @mock.patch.object(app_identity, 'get_application_id', return_value='app-id')
  @mock.patch.object(token, 'GenerateAuthToken', return_value='secret')
  def testCreatePubSubCallbackForNewPubSubTopic(self, *_):
    result = try_job_service.CreatePubSubCallback('id')
    self.assertDictEqual({'runner_id': 'id'}, result.user_data)
    self.assertEqual('secret', result.auth_token)
    self.assertEqual('projects/app-id/topics/build-change', result.topic)

  @mock.patch.object(try_job_service, 'buildbucket_client')
  def testTriggerTryJob(self, mock_module):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = {
        'properties': {
            'parent_mastername': 'pm',
            'parent_buildername': 'pb'
        }
    }
    build.put()
    build_response = {
        'id': '1',
        'url': 'url',
        'status': 'SCHEDULED',
    }
    results = [(None, buildbucket_client.BuildbucketBuild(build_response))]
    mock_module.TriggerTryJobs.return_value = results

    build_id, error = try_job_service.TriggerTryJob(
        master_name, builder_name, master_name, builder_name, {},
        failure_type.GetDescriptionForFailureType(failure_type.FLAKY_TEST),
        None, None, 'pipeline_id')

    self.assertEqual(build_id, '1')
    self.assertIsNone(error)

  @mock.patch.object(try_job_service, 'buildbucket_client')
  @mock.patch.object(try_job_service, 'GetTrybot')
  def testTriggerTryJobSwarming(self, _mock_waterfall, mock_client):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = {
        'properties': {
            'parent_mastername': 'pm',
            'parent_buildername': 'pb'
        }
    }
    build.put()
    response = {
        'build': {
            'id': '1',
            'url': 'url',
            'status': 'SCHEDULED',
        }
    }
    results = [(None, buildbucket_client.BuildbucketBuild(response['build']))]
    mock_client.TriggerTryJobs.return_value = results

    build_id, error = try_job_service.TriggerTryJob(
        master_name, builder_name, 'luci.chromium.findit', 'findit_variable',
        {}, failure_type.GetDescriptionForFailureType(failure_type.FLAKY_TEST),
        None, None, 'pipeline_id')

    self.assertEqual('luci.chromium.findit',
                     mock_client.TryJob.call_args[0][2]['mastername'])
    self.assertEqual(build_id, '1')
    self.assertIsNone(error)

  @mock.patch.object(try_job_service, 'buildbucket_client')
  def testTriggerTryJobError(self, mock_module):
    master_name = 'm'
    builder_name = 'Mac tests'
    build_number = 1
    build = WfBuild.Create(master_name, builder_name, build_number)
    build.data = {
        'properties': {
            'parent_mastername': 'pm',
            'parent_buildername': 'pb'
        }
    }
    build.put()
    results = [('error', None)]
    mock_module.TriggerTryJobs.return_value = results

    build_id, error = try_job_service.TriggerTryJob(
        master_name, builder_name, master_name, builder_name, {},
        failure_type.GetDescriptionForFailureType(failure_type.FLAKY_TEST),
        None, None, 'pipeline_id')

    self.assertIsNone(build_id)
    self.assertEqual('error', error)

  def testCreateTryJobDataTest(self):
    try_job = WfTryJob.Create('m', 'b', 123)
    try_job.put()
    build_id = 'build_id'
    try_job_service.CreateTryJobData(build_id, try_job.key, False, True,
                                     failure_type.TEST)
    try_job_data = WfTryJobData.Get(build_id)
    self.assertIsNotNone(try_job_data)

  def testUpdateTryJobTest(self):
    WfTryJob.Create('m', 'b', 123).put()
    build_id = 'build_id'
    try_job = try_job_service.UpdateTryJob('m', 'b', 123, build_id,
                                           failure_type.TEST)
    self.assertEqual(try_job.try_job_ids[0], build_id)
    self.assertIsNotNone(try_job.test_results)

  def testCreateTryJobDataCompile(self):
    try_job = WfTryJob.Create('m', 'b', 123)
    try_job.put()
    build_id = 'build_id'
    try_job_service.CreateTryJobData(build_id, try_job.key, True, True,
                                     failure_type.COMPILE)
    try_job_data = WfTryJobData.Get(build_id)
    self.assertIsNotNone(try_job_data)

  def testUpdateTryJobCompile(self):
    WfTryJob.Create('m', 'b', 123).put()
    build_id = 'build_id'
    try_job = try_job_service.UpdateTryJob('m', 'b', 123, build_id,
                                           failure_type.COMPILE)
    self.assertEqual(try_job.try_job_ids[0], build_id)
    self.assertIsNotNone(try_job.compile_results)

  def testUpdateTryJobResultAppendNewResult(self):
    try_job_result = [{'try_job_id': '111'}]
    try_job_service.UpdateTryJobResult(try_job_result, {'try_job_id': '123'},
                                       '123')
    self.assertEqual([{
        'try_job_id': '111'
    }, {
        'try_job_id': '123'
    }], try_job_result)

  def testUpdateTryJobResult(self):
    try_job_result = [{'try_job_id': '111'}, {'try_job_id': '123'}]
    new_result = {'try_job_id': '123', 'url': 'url'}

    expected_updated_result = [{
        'try_job_id': '111'
    }, {
        'try_job_id': '123',
        'url': 'url'
    }]
    try_job_service.UpdateTryJobResult(try_job_result, new_result, '123')
    self.assertEqual(expected_updated_result, try_job_result)

  @mock.patch.object(swarmbucket, 'GetDimensionsForBuilder')
  def testPrepareParametersToScheduleTryJob(self, mock_dimensions):
    mock_dimensions.return_value = ['os:Mac-10.9', 'cpu:x86-64']
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    failure_info = CompileFailureInfo.FromSerializable({
        'is_luci': None,
        'buildbucket_bucket': None,
        'buildbucket_id': None,
        'builds': {
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    })

    expected_parameters = {
        'build_key': {
            'master_name': master_name,
            'builder_name': builder_name,
            'build_number': build_number
        },
        'dimensions': [
            'os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'
        ],
        'cache_name':
            _CACHE_NAME,
        'bad_revision':
            'rev2',
        'suspected_revisions': [],
        'urlsafe_try_job_key':
            'urlsafe_try_job_key'
    }

    self.assertEqual(
        expected_parameters,
        try_job_service.PrepareParametersToScheduleTryJob(
            master_name, builder_name, build_number, failure_info,
            CompileHeuristicResult.FromSerializable({}), 'urlsafe_try_job_key'))

  @mock.patch.object(swarmbucket, 'GetDimensionsForBuilder')
  def testPrepareParametersToScheduleTryJobLUCI(self, mock_fn):
    mock_fn.return_value = [
        'os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'
    ]
    master_name = 'm'
    builder_name = 'b'
    build_number = 1

    failure_info = CompileFailureInfo.FromSerializable({
        'is_luci': True,
        'buildbucket_bucket': 'luci.chromium.ci',
        'buildbucket_id': '8000111222333444555666',
        'builds': {
            '1': {
                'chromium_revision': 'rev2'
            }
        }
    })

    expected_parameters = {
        'build_key': {
            'master_name': master_name,
            'builder_name': builder_name,
            'build_number': build_number
        },
        'dimensions': [
            'os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'
        ],
        'cache_name':
            _CACHE_NAME,
        'bad_revision':
            'rev2',
        'suspected_revisions': [],
        'urlsafe_try_job_key':
            'urlsafe_try_job_key'
    }

    self.assertEqual(
        expected_parameters,
        try_job_service.PrepareParametersToScheduleTryJob(
            master_name, builder_name, build_number, failure_info,
            CompileHeuristicResult.FromSerializable({}), 'urlsafe_try_job_key'))

  def testUpdateTryJobMetadataForBuildError(self):
    error_dict = {'message': 'message', 'reason': 'BUILD_NOT_FOUND'}
    error_code = 30
    try_job_data = WfTryJobData.Create('1')
    try_job_data.try_job_key = WfTryJob.Create('m', 'b', 123).key

    try_job_service.UpdateTryJobMetadata(
        try_job_data,
        failure_type.COMPILE,
        buildbucket_build=None,
        error_dict=error_dict,
        error_code=error_code)
    self.assertEqual(try_job_data.error, error_dict)

  def testUpdateTryJobMetadataUpdateTimestamps(self):
    try_job_id = '1'
    url = 'url'
    build_data = {
        'id': try_job_id,
        'url': url,
        'status': 'STARTED',
        'created_ts': '1454367570000000',
        'started_ts': '1454367571000000',
        'completed_ts': '1454367574000000',
    }
    build = buildbucket_client.BuildbucketBuild(build_data)
    try_job_data = WfTryJobData.Create('1')
    try_job_data.try_job_key = WfTryJob.Create('m', 'b', 123).key

    try_job_service.UpdateTryJobMetadata(
        try_job_data,
        try_job_type=failure_type.COMPILE,
        buildbucket_build=build)
    self.assertEqual(try_job_data.request_time,
                     time_util.MicrosecondsToDatetime('1454367570000000'))
    self.assertEqual(try_job_data.start_time,
                     time_util.MicrosecondsToDatetime('1454367571000000'))
    self.assertEqual(try_job_data.end_time,
                     time_util.MicrosecondsToDatetime('1454367574000000'))

  def testUpdateTryJobMetadata(self):
    try_job_id = '1'
    url = 'url'
    build_data = {
        'id': try_job_id,
        'url': url,
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
    }
    report = {
        'result': {
            'rev1': 'passed',
            'rev2': 'failed'
        },
        'metadata': {
            'regression_range_size': 2
        }
    }
    build = buildbucket_client.BuildbucketBuild(build_data)

    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = WfTryJob.Create('m', 'b', 123).key

    try_job_service.UpdateTryJobMetadata(
        try_job_data,
        failure_type.COMPILE,
        buildbucket_build=build,
        report=report)
    try_job_data = WfTryJobData.Get(try_job_id)
    self.assertIsNone(try_job_data.error)
    self.assertEqual(try_job_data.regression_range_size, 2)
    self.assertEqual(try_job_data.number_of_commits_analyzed, 2)
    self.assertEqual(try_job_data.end_time, datetime(2016, 2, 1, 22, 59, 34))
    self.assertEqual(try_job_data.request_time, datetime(
        2016, 2, 1, 22, 59, 30))
    self.assertEqual(try_job_data.try_job_url, url)

  @mock.patch('services.swarmbot_util.GetBot', return_value='BotName')
  @mock.patch(
      'services.swarmbot_util.GetBuilderCacheName', return_value='CacheName')
  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testRecordCacheStats(self, mock_cl, *_):
    cases = [(None, None, '100', 100), ('100', '100', '200', 200),
             ('100', '200', '100', 200), ('200', '200', '100', 200),
             ('100', '200', '300', 300)]
    for (checked_out_revision, cached_revision, bad_revision,
         synced_revision) in cases:
      mock_commit_position = mock.PropertyMock()
      mock_commit_position.side_effect = filter(None, [
          int(checked_out_revision) if checked_out_revision else None,
          int(cached_revision) if cached_revision else None,
          int(bad_revision) if bad_revision else None,
      ])
      type(mock_cl.return_value).commit_position = mock_commit_position
      build = buildbucket_client.BuildbucketBuild({
          'parameters_json':
              json.dumps({
                  'properties': {
                      'bad_revision': bad_revision
                  }
              })
      })
      report = {
          'last_checked_out_revision': checked_out_revision,
          'previously_cached_revision': cached_revision
      }
      with mock.patch(
          'model.wf_try_bot_cache.WfTryBotCache.AddBot') as mock_add_bot:
        try_job_service._RecordCacheStats(build, report)
        mock_add_bot.assert_called_once_with(
            'BotName',
            int(checked_out_revision) if checked_out_revision else None,
            synced_revision)

  @mock.patch.object(swarmbot_util, 'GetBot', return_value=None)
  @mock.patch.object(swarmbot_util, 'GetBuilderCacheName', return_value=None)
  @mock.patch.object(CachedGitilesRepository, 'GetChangeLog')
  def testRecordCacheStatsNotEnoughInfo(self, mock_fn, *_):
    try_job_service._RecordCacheStats(None, None)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(WfTryJobData, 'put')
  def testUpdateLastBuildbucketResponseNoBuild(self, mock_fn):
    try_job_service._UpdateLastBuildbucketResponse(None, None)
    self.assertFalse(mock_fn.called)

  @mock.patch.object(swarmbucket, 'GetDimensionsForBuilder')
  @mock.patch.object(WfTryJobData, 'put')
  def testUpdateLastBuildbucketResponse(self, _, mock_dimensions):
    mock_dimensions.return_value = ['os:Mac-10.9', 'cpu:x86-64']
    try_job_data = WfTryJobData.Create('m/b/123')
    response = {'id': '1'}
    build = buildbucket_client.BuildbucketBuild(response)
    try_job_service._UpdateLastBuildbucketResponse(try_job_data, build)
    self.assertEqual(try_job_data.last_buildbucket_response, response)

  def testGetErrorForNoError(self):
    build_response = {
        'id':
            1,
        'url':
            'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status':
            'COMPLETED',
        'completed_ts':
            '1454367574000000',
        'created_ts':
            '1454367570000000',
        'result_details_json':
            json.dumps({
                'properties': {
                    'report': {
                        'result': {
                            'rev1': 'passed',
                            'rev2': 'failed'
                        },
                        'metadata': {
                            'regression_range_size': 2
                        }
                    }
                }
            })
    }
    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild(build_response), None, False,
            False), (None, None))
    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild({}), None, False, False),
        (None, None))

  def testGetErrorForTimeout(self):
    expected_error_dict = {
        'message':
            'Try job monitoring was abandoned.',
        'reason': (
            'Timeout after %s hours' %
            waterfall_config.GetTryJobSettings().get('job_timeout_hours'))
    }

    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild({}), None, True, False),
        (expected_error_dict, try_job_error.TIMEOUT))

  def testGetErrorForBuildbucketReportedError(self):
    build_response = {
        'result_details_json':
            json.dumps({
                'error': {
                    'message': 'Builder b not found'
                }
            })
    }

    expected_error_dict = {
        'message': 'Buildbucket reported an error.',
        'reason': 'Builder b not found'
    }

    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild(build_response), None, False,
            False), (expected_error_dict, try_job_error.CI_REPORTED_ERROR))

  def testGetErrorUnknown(self):
    build_response = {
        'result_details_json': json.dumps({
            'error': {
                'abc': 'abc'
            }
        })
    }

    expected_error_dict = {
        'message': 'Buildbucket reported an error.',
        'reason': try_job_service.UNKNOWN
    }

    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild(build_response), None, False,
            False), (expected_error_dict, try_job_error.CI_REPORTED_ERROR))

  def testGetErrorInfraFailure(self):
    build_response = {
        'result':
            'FAILED',
        'failure_reason':
            'INFRA_FAILURE',
        'result_details_json':
            json.dumps({
                'properties': {
                    'report': {
                        'metadata': {
                            'infra_failure': True
                        }
                    }
                }
            })
    }

    expected_error_dict = {
        'message': 'Try job encountered an infra issue during execution.',
        'reason': try_job_service.UNKNOWN
    }

    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild(build_response), None, False,
            False), (expected_error_dict, try_job_error.INFRA_FAILURE))

  def testGetErrorUnexpectedBuildFailure(self):
    build_response = {
        'result':
            'FAILED',
        'failure_reason':
            'BUILD_FAILURE',
        'result_details_json':
            json.dumps({
                'properties': {
                    'report': {
                        'metadata': {
                            'infra_failure': True
                        }
                    }
                }
            })
    }

    expected_error_dict = {
        'message': 'Buildbucket reported a general error.',
        'reason': try_job_service.UNKNOWN
    }

    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild(build_response), None, False,
            False), (expected_error_dict, try_job_error.INFRA_FAILURE))

  def testGetErrorUnknownBuildbucketFailure(self):
    build_response = {
        'result': 'FAILED',
        'failure_reason': 'SOME_FAILURE',
        'result_details_json': json.dumps({
            'properties': {
                'report': {}
            }
        })
    }

    expected_error_dict = {
        'message': 'SOME_FAILURE',
        'reason': try_job_service.UNKNOWN
    }

    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild(build_response), None, False,
            False), (expected_error_dict, try_job_error.UNKNOWN))

  def testGetErrorReportMissing(self):
    build_response = {'result_details_json': json.dumps({'properties': {}})}

    expected_error_dict = {
        'message': 'No result report was found.',
        'reason': try_job_service.UNKNOWN
    }

    self.assertEqual(
        try_job_service._GetError(
            buildbucket_client.BuildbucketBuild(build_response), None, False,
            True), (expected_error_dict, try_job_error.UNKNOWN))

  def testUpdateTryJobResultAnalyzing(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.put()

    try_job_service._UpdateTryJobEntity(
        try_job.key.urlsafe(), failure_type.TEST, try_job_id, 'url',
        buildbucket_client.BuildbucketBuild.STARTED)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.RUNNING, try_job.status)

  def testUpdateFlakeTryJobResult(self):
    master_name = 'm'
    builder_name = 'b'
    step_name = 's'
    test_name = 't'
    git_hash = 'a1b2c3d4'
    try_job_id = '2'
    try_job = FlakeTryJob.Create(master_name, builder_name, step_name,
                                 test_name, git_hash)
    try_job.put()

    try_job_service._UpdateTryJobEntity(
        try_job.key.urlsafe(), failure_type.FLAKY_TEST, try_job_id, 'url',
        buildbucket_client.BuildbucketBuild.STARTED)
    try_job = FlakeTryJob.Get(master_name, builder_name, step_name, test_name,
                              git_hash)
    self.assertEqual(analysis_status.RUNNING, try_job.status)

  def testUpdateCompileTyrJobResultAppend(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [{'try_job_id': '1'}]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    try_job_service._UpdateTryJobEntity(
        try_job.key.urlsafe(), failure_type.COMPILE, try_job_id, 'url',
        buildbucket_client.BuildbucketBuild.COMPLETED)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    self.assertEqual(analysis_status.RUNNING, try_job.status)
    expected_compile_results = [{
        'try_job_id': '1'
    }, {
        'try_job_id': '3',
        'report': None,
        'url': 'url'
    }]
    self.assertEqual(try_job.compile_results, expected_compile_results)

  def testUpdateTryJobResultResultIsNotAtTheEndOfList(self):
    master_name = 'm'
    builder_name = 'b'
    build_number = 1
    try_job_id = '3'

    try_job = WfTryJob.Create(master_name, builder_name, build_number)
    try_job.compile_results = [{'try_job_id': try_job_id}, {'try_job_id': '1'}]
    try_job.status = analysis_status.RUNNING
    try_job.put()

    try_job_service._UpdateTryJobEntity(
        try_job.key.urlsafe(), failure_type.COMPILE, try_job_id, 'url',
        buildbucket_client.BuildbucketBuild.COMPLETED)
    try_job = WfTryJob.Get(master_name, builder_name, build_number)
    expected_compile_results = [{
        'try_job_id': '3',
        'report': None,
        'url': 'url'
    }, {
        'try_job_id': '1'
    }]
    self.assertEqual(analysis_status.RUNNING, try_job.status)
    self.assertEqual(try_job.compile_results, expected_compile_results)

  def testGetOrCreateTryJobDataGet(self):
    try_job_id = '1'
    urlsafe_try_job_key = WfTryJob.Create('m', 'b', 1).key.urlsafe()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)
    try_job_data.put()
    self.assertIsNotNone(
        try_job_service.GetOrCreateTryJobData(failure_type.COMPILE, try_job_id,
                                              urlsafe_try_job_key))

  def testGetOrCreateTryJobDataCreate(self):
    try_job_id = '1'
    urlsafe_try_job_key = FlakeTryJob.Create('m', 'b', 'a', 't',
                                             'gh').key.urlsafe()
    self.assertIsNotNone(
        try_job_service.GetOrCreateTryJobData(failure_type.FLAKY_TEST,
                                              try_job_id, urlsafe_try_job_key))

  @mock.patch.object(swarmbucket, 'GetDimensionsForBuilder')
  def testGetDimensionsFromBuildInfoLuci(self, mocked_dimensions):
    build_info = BuildInfo('m', 'b', 123)
    build_info.is_luci = True
    build_info.buildbucket_bucket = 'bucket'
    build_info.parent_buildername = 'pb'

    try_job_service.GetDimensionsFromBuildInfo(build_info)
    mocked_dimensions.assert_called_once_with('bucket', 'pb')

  @mock.patch.object(time, 'time', return_value=1511298536.959618)
  @mock.patch.object(waterfall_config, 'GetTryJobSettings')
  def testInitializeParams(self, mock_config, _):
    mock_config.return_value = {
        'job_timeout_hours': 1,
        'server_query_interval_seconds': 5,
        'allowed_response_error_times': 5
    }

    try_job_id = '1'
    try_job_type = failure_type.COMPILE
    urlsafe_try_job_key = 'urlsafe_try_job_key'
    expected_params = {
        'try_job_id': try_job_id,
        'try_job_type': try_job_type,
        'urlsafe_try_job_key': urlsafe_try_job_key,
        'deadline': 1511302136.959618,
        'error_count': 0,
        'max_error_times': 5,
        'default_pipeline_wait_seconds': 5,
        'timeout_hours': 1,
        'backoff_time': 5,
    }
    self.assertEqual(
        expected_params,
        try_job_service.InitializeParams(try_job_id, try_job_type,
                                         urlsafe_try_job_key))

  def testGetTryJobDataFlake(self):
    try_job_id = 'try_job_id'
    try_job = FlakeTryJob.Create('m', 'b', 's', 't', 'r1000')
    try_job_data = FlakeTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    self.assertIsNotNone(
        try_job_service._GetTryJobData(failure_type.FLAKY_TEST, try_job_id))

  def testGetTryJobDataWaterfall(self):
    try_job_id = 'try_job_id'
    try_job = WfTryJob.Create('m', 'b', 123)
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = try_job.key
    try_job_data.put()

    self.assertIsNotNone(
        try_job_service._GetTryJobData(failure_type.COMPILE, try_job_id))

  def testOnTryJobStateChangedWhenScheduled(self):
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()
    try_job_data = WfTryJobData.Create('job-id')
    try_job_data.try_job_key = ndb.Key(urlsafe=try_job.key.urlsafe())
    try_job_data.try_job_type = failure_type.GetDescriptionForFailureType(
        failure_type.COMPILE)
    try_job_data.put()
    build_json = {
        'id': 'job-id',
        'url': None,
        'status': 'SCHEDULED',
        'created_ts': '1454367570000000',
    }
    result, state = try_job_service.OnTryJobStateChanged(
        'job-id', failure_type.COMPILE, build_json)
    try_job_data = WfTryJobData.Get('job-id')
    self.assertIsInstance(try_job_data.request_time, datetime)
    self.assertIsNone(result)
    self.assertEqual(analysis_status.PENDING, state)

  def testOnTryJobStateChangedWhenStarted(self):
    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()
    try_job_data = WfTryJobData.Create('job-id')
    try_job_data.try_job_key = ndb.Key(urlsafe=try_job.key.urlsafe())
    try_job_data.try_job_type = failure_type.GetDescriptionForFailureType(
        failure_type.COMPILE)
    try_job_data.put()
    build_json = {
        'id': 'job-id',
        'url': 'https://build.url',
        'status': 'STARTED',
        'created_ts': '1454367570000000',
        'started_ts': '1454367571000000',
    }
    result, state = try_job_service.OnTryJobStateChanged(
        'job-id', failure_type.COMPILE, build_json)
    self.assertIsNone(result)
    self.assertEqual(analysis_status.RUNNING, state)
    try_job_data = WfTryJobData.Get('job-id')
    self.assertIsInstance(try_job_data.start_time, datetime)
    try_job = WfTryJob.Get('m', 'b', 1)
    self.assertEqual(analysis_status.RUNNING, try_job.status)
    self.assertEqual('https://build.url', try_job.compile_results[-1]['url'])

  @mock.patch.object(try_job_service, 'OnTryJobCompleted')
  def testOnTryJobStateChangedWhenCompleted(self, mocked_OnTryJobCompleted):
    mocked_job_result = {
        'url': 'https://build.url',
        'try_job_id': 'job-id',
        'culprit': {
            'a': 'b',
        },
        'report': {
            'culprit': 'x',
            'result': {
                'r': 'v',
            },
            'last_checked_out_revision': 'r1',
            'previously_checked_out_revision': 'r2',
            'previously_cached_revision': 'r3',
            'metadata': {
                'm': 'v',
            },
        },
    }
    mocked_OnTryJobCompleted.return_value = mocked_job_result

    try_job = WfTryJob.Create('m', 'b', 1)
    try_job.put()

    try_job_data = WfTryJobData.Create('job-id')
    try_job_data.try_job_key = ndb.Key(urlsafe=try_job.key.urlsafe())
    try_job_data.try_job_type = failure_type.GetDescriptionForFailureType(
        failure_type.COMPILE)
    try_job_data.put()

    build_json = {
        'id': 'job-id',
        'url': 'https://build.url',
        'status': 'COMPLETED',
        'created_ts': '1454367570000000',
        'started_ts': '1454367571000000',
        'completed_ts': '1454367572000000',
    }
    returned_result = try_job_service.OnTryJobStateChanged(
        'job-id', failure_type.COMPILE, build_json)
    self.assertDictEqual(mocked_job_result, returned_result)

  @mock.patch.object(
      try_job_service,
      '_GetError',
      return_value=({
          'message': 'Try job monitoring was abandoned.',
          'reason': 'Timeout after 5 hours'
      }, 20))
  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  def testOnTryJobTimeout(self, mocked_UpdateTryJobMetadata, mock_error):
    try_job_data = WfTryJobData.Create('job-id')
    urlsafe_try_job_key = WfTryJob.Create('m', 'b', 1).key.urlsafe()
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)
    try_job_data.try_job_type = failure_type.GetDescriptionForFailureType(
        failure_type.COMPILE)
    try_job_data.put()
    try_job_service.OnTryJobTimeout('job-id', failure_type.COMPILE)
    error_dict = {
        'message': 'Try job monitoring was abandoned.',
        'reason': 'Timeout after 5 hours'
    }
    error_code = 20
    mock_error.assert_called_once_with(timed_out=True)
    mocked_UpdateTryJobMetadata.assert_called_once_with(
        try_job_data,
        failure_type.COMPILE,
        error_dict=error_dict,
        error_code=error_code)

  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  @mock.patch.object(try_job_service, '_UpdateTryJobEntity')
  def testOnTryJobRunning(self, *_):
    try_job_id = '1'
    params = {
        'try_job_type': failure_type.COMPILE,
        'try_job_id': try_job_id,
        'default_pipeline_wait_seconds': 5,
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    build_data = {
        'id': try_job_id,
        'url': 'url',
        'status': 'STARTED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367571000000'
    }
    build = buildbucket_client.BuildbucketBuild(build_data)
    result, state = try_job_service.OnTryJobRunning(params, None, build, None)
    self.assertIsNone(result)
    self.assertEqual(analysis_status.RUNNING, state)

  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  @mock.patch.object(
      try_job_service, '_UpdateTryJobEntity', return_value=['result'])
  @mock.patch.object(step_util, 'GetStepLogForLuciBuild')
  def testOnTryJobCompletedBuildbot(self, mock_report, *_):
    try_job_id = '1'
    params = {
        'try_job_type': failure_type.COMPILE,
        'try_job_id': try_job_id,
        'default_pipeline_wait_seconds': 5,
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    urlsafe_try_job_key = WfTryJob.Create('m', 'b', 1).key.urlsafe()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)
    try_job_data.put()

    build_data = {
        'id': try_job_id,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367571000000'
    }
    build = buildbucket_client.BuildbucketBuild(build_data)

    report = {
        'result': {
            'rev1': 'passed',
            'rev2': 'failed'
        },
        'metadata': {
            'regression_range_size': 2
        }
    }
    mock_report.return_value = report
    self.assertEqual(('result', analysis_status.COMPLETED),
                     try_job_service.OnTryJobCompleted(params, try_job_data,
                                                       build, None))

  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  @mock.patch.object(
      try_job_service, '_UpdateTryJobEntity', return_value=['result'])
  @mock.patch.object(step_util, 'GetStepLogForLuciBuild', side_effect=TypeError)
  @mock.patch.object(logging, 'exception')
  def testOnTryJobCompletedBuildbotNoReport(self, mock_log, *_):
    try_job_id = '1'
    params = {
        'try_job_type': failure_type.COMPILE,
        'try_job_id': try_job_id,
        'default_pipeline_wait_seconds': 5,
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    urlsafe_try_job_key = WfTryJob.Create('m', 'b', 1).key.urlsafe()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)
    try_job_data.put()

    build_data = {
        'id': try_job_id,
        'url': 'https://build.chromium.org/p/m/builders/b/builds/1234',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367571000000'
    }
    build = buildbucket_client.BuildbucketBuild(build_data)

    self.assertEqual(('result', analysis_status.ERROR),
                     try_job_service.OnTryJobCompleted(params, try_job_data,
                                                       build, None))
    mock_log.assert_called_once_with(
        'Failed to load result report for tryjob/%s due to exception %s.' %
        (try_job_id, TypeError().message))

  @mock.patch.object(try_job_service, '_RecordCacheStats')
  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  @mock.patch.object(
      try_job_service, '_UpdateTryJobEntity', return_value=['result'])
  @mock.patch.object(step_util, 'GetStepLogForLuciBuild')
  def testOnTryJobCompletedSwarmingbot(self, mock_report, *_):
    try_job_id = '1'
    params = {
        'try_job_type': failure_type.COMPILE,
        'try_job_id': try_job_id,
        'default_pipeline_wait_seconds': 5,
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    urlsafe_try_job_key = WfTryJob.Create('m', 'b', 1).key.urlsafe()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)
    try_job_data.put()

    build_data = {
        'id': try_job_id,
        'url': 'https://ci.chromium.org/p/chromium/builders/'
               'luci.chromium.findit/findit_variable/102',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367571000000'
    }
    build = buildbucket_client.BuildbucketBuild(build_data)

    report = {
        'result': {
            'rev1': 'passed',
            'rev2': 'failed'
        },
        'metadata': {
            'regression_range_size': 2
        }
    }
    mock_report.return_value = report
    self.assertEqual(('result', analysis_status.COMPLETED),
                     try_job_service.OnTryJobCompleted(params, try_job_data,
                                                       build, None))

  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  @mock.patch.object(
      try_job_service, '_UpdateTryJobEntity', return_value=['result'])
  @mock.patch.object(step_util, 'GetStepLogForLuciBuild', return_value=None)
  @mock.patch.object(try_job_service, '_RecordCacheStats')
  def testOnTryJobCompletedSwarmingbotNoReport(self, mock_fn, *_):
    try_job_id = '1'
    params = {
        'try_job_type': failure_type.COMPILE,
        'try_job_id': try_job_id,
        'default_pipeline_wait_seconds': 5,
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    urlsafe_try_job_key = WfTryJob.Create('m', 'b', 1).key.urlsafe()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)
    try_job_data.put()

    build_data = {
        'id': try_job_id,
        'url': 'https://ci.chromium.org/p/chromium/builders/'
               'luci.chromium.findit/findit_variable/102',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367571000000'
    }
    build = buildbucket_client.BuildbucketBuild(build_data)

    self.assertEqual(('result', analysis_status.COMPLETED),
                     try_job_service.OnTryJobCompleted(params, try_job_data,
                                                       build, None))
    self.assertFalse(mock_fn.called)

  @mock.patch.object(try_job_service, 'UpdateTryJobMetadata')
  @mock.patch.object(
      try_job_service, '_UpdateTryJobEntity', return_value=['result'])
  @mock.patch.object(step_util, 'GetStepLogForLuciBuild', side_effect=TypeError)
  @mock.patch.object(logging, 'exception')
  def testOnTryJobCompletedSwarmingbotException(self, mock_log, *_):
    try_job_id = '1'
    params = {
        'try_job_type': failure_type.COMPILE,
        'try_job_id': try_job_id,
        'default_pipeline_wait_seconds': 5,
        'urlsafe_try_job_key': 'urlsafe_try_job_key'
    }

    urlsafe_try_job_key = WfTryJob.Create('m', 'b', 1).key.urlsafe()
    try_job_data = WfTryJobData.Create(try_job_id)
    try_job_data.try_job_key = ndb.Key(urlsafe=urlsafe_try_job_key)
    try_job_data.put()

    build_data = {
        'id': try_job_id,
        'url': 'https://ci.chromium.org/p/chromium/builders/'
               'luci.chromium.findit/findit_variable/102',
        'status': 'COMPLETED',
        'completed_ts': '1454367574000000',
        'created_ts': '1454367570000000',
        'updated_ts': '1454367571000000'
    }
    build = buildbucket_client.BuildbucketBuild(build_data)

    self.assertEqual(('result', analysis_status.ERROR),
                     try_job_service.OnTryJobCompleted(params, try_job_data,
                                                       build, None))
    mock_log.assert_called_once_with(
        'Failed to load result report for tryjob/%s due to exception %s.' %
        (try_job_id, TypeError().message))

  def testGetCurrentTryJobID(self):
    try_job = WfTryJob.Create('m', 'b', '54321')
    try_job.try_job_ids = ['1', '2', '3', '4']
    try_job.put()
    try_job_data = WfTryJobData.Create('2')
    try_job_data.try_job_key = try_job.key
    try_job_data.runner_id = 'pipeline_id'
    try_job_data.put()
    try_job_data = WfTryJobData.Create('3')
    try_job_data.try_job_key = try_job.key
    try_job_data.runner_id = 'pipeline_id3'
    try_job_data.put()
    self.assertEqual(
        '2',
        try_job_service.GetCurrentTryJobID(try_job.key.urlsafe(),
                                           'pipeline_id'))

  def testGetCurrentTryJobIDNoTryJob(self):
    self.assertIsNone(try_job_service.GetCurrentTryJobID(None, 'pipeline_id'))

  def testGetCurrentTryJobIDNoTryJobData(self):
    try_job = WfTryJob.Create('m', 'b', '54321')
    try_job.try_job_ids = ['1', '2', '3']
    try_job.put()
    self.assertIsNone(
        try_job_service.GetCurrentTryJobID(try_job.key.urlsafe(),
                                           'pipeline_id'))

  def testGetCulpritsWithoutNoBlameAccountsCLS(self):
    culprit_info_1 = {
        'revision': 'rev1',
        'repo_name': 'chromium',
        'commit_position': 1,
        'url': 'url_1',
        'author': 'author1@abc.com'
    }
    culprit_info_3 = {
        'revision': 'rev3',
        'repo_name': 'chromium',
        'commit_position': 3,
        'url': 'url_3',
        'author': 'author3@abc.com',
    }

    culprits = {
        'rev1': culprit_info_1,
        'rev2': {
            'revision': 'rev2',
            'repo_name': 'chromium',
            'commit_position': 2,
            'url': 'url_2',
            'author': constants.NO_BLAME_ACTION_ACCOUNTS[0],
        },
        'rev3': culprit_info_3
    }

    expected_culprits = {'rev1': culprit_info_1, 'rev3': culprit_info_3}

    self.assertEqual(
        expected_culprits,
        try_job_service.GetCulpritsWithoutNoBlameAccountsCLS(culprits))

  def testGetTrybot(self):
    self.assertEqual(('luci.chromium.findit', 'findit_variable'),
                     try_job_service.GetTrybot())

  @mock.patch.object(swarmbucket, 'GetDimensionsForBuilder')
  def testGetTrybotDimensions(self, mock_dimensions):
    mock_dimensions.return_value = ['os:Mac-10.9', 'cpu:x86-64']
    self.assertEqual(['os:Mac-10.9', 'cpu:x86-64', 'pool:luci.chromium.findit'],
                     try_job_service.GetTrybotDimensions('m', 'b'))
