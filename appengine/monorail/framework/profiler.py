# Copyright 2016 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style
# license that can be found in the LICENSE file or at
# https://developers.google.com/open-source/licenses/bsd

"""A simple profiler object to track how time is spent on a request.

The profiler is called from application code at the begining and
end of each major phase and subphase of processing.  The profiler
object keeps track of how much time was spent on each phase or subphase.

This class is useful when developers need to understand where
server-side time is being spent.  It includes durations in
milliseconds, and a simple bar chart on the HTML page.

On-page debugging and performance info is useful because it makes it easier
to explore performance interactively.
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import datetime
import logging
import random
import re
import threading
import time

from infra_libs import ts_mon

from contextlib import contextmanager

from google.appengine.api import app_identity

PHASE_TIME = ts_mon.CumulativeDistributionMetric(
    'monorail/servlet/phase_time',
    'Time spent in profiler phases, in ms',
    [ts_mon.StringField('phase')])

# trace_service requires names less than 128 bytes
# https://cloud.google.com/trace/docs/reference/v1/rest/v1/projects.traces#Trace
MAX_PHASE_NAME_LENGTH = 128


class Profiler(object):
  """Object to record and help display request processing profiling info.

  The Profiler class holds a list of phase objects, which can hold additional
  phase objects (which are subphases).  Each phase or subphase represents some
  meaningful part of this application's HTTP request processing.
  """

  _COLORS = ['900', '090', '009', '360', '306', '036',
             '630', '630', '063', '333']

  def __init__(self, opt_trace_context=None, opt_trace_service=None):
    """Each request processing profile begins with an empty list of phases."""
    self.top_phase = _Phase('overall profile', -1, None)
    self.current_phase = self.top_phase
    self.next_color = 0
    self.original_thread_id = threading.current_thread().ident
    self.trace_context = opt_trace_context
    self.trace_service = opt_trace_service
    self.project_id = app_identity.get_application_id()

  def StartPhase(self, name='unspecified phase'):
    """Begin a (sub)phase by pushing a new phase onto a stack."""
    if self.original_thread_id != threading.current_thread().ident:
      return  # We only profile the main thread.
    color = self._COLORS[self.next_color % len(self._COLORS)]
    self.next_color += 1
    self.current_phase = _Phase(name, color, self.current_phase)

  def EndPhase(self):
    """End a (sub)phase by poping the phase stack."""
    if self.original_thread_id != threading.current_thread().ident:
      return  # We only profile the main thread.
    self.current_phase = self.current_phase.End()

  @contextmanager
  def Phase(self, name='unspecified phase'):
    """Context manager to automatically begin and end (sub)phases."""
    self.StartPhase(name)
    try:
      yield
    finally:
      self.EndPhase()

  def LogStats(self):
    """Log sufficiently-long phases and subphases, for debugging purposes."""
    self.top_phase.End()
    lines = ['Stats:']
    self.top_phase.AccumulateStatLines(self.top_phase.elapsed_seconds, lines)
    logging.info('\n'.join(lines))

  def ReportTrace(self):
    """Send a profile trace to Google Cloud Tracing."""
    self.top_phase.End()
    spans = self.top_phase.SpanJson()
    if not self.trace_service or not self.trace_context:
      logging.info('would have sent trace: %s', spans)
      return

    # Format of trace_context: 'TRACE_ID/SPAN_ID;o=TRACE_TRUE'
    # (from https://cloud.google.com/trace/docs/troubleshooting#force-trace)
    # TODO(crbug/monorail:7086): Respect the o=TRACE_TRUE part.
    # Note: on Appngine it seems ';o=1' is omitted rather than set to 0.
    trace_id, root_span_id = self.trace_context.split(';')[0].split('/')
    for s in spans:
      # TODO(crbug/monorail:7087): Consider setting `parentSpanId` to
      # `root_span_id` for the children of `top_phase`.
      if not 'parentSpanId' in s:
        s['parentSpanId'] = root_span_id
    traces_body = {
      'projectId': self.project_id,
      'traceId': trace_id,
      'spans': spans,
    }
    body = {
      'traces': [traces_body]
    }
    # TODO(crbug/monorail:7088): Do this async so it doesn't delay the response.
    request = self.trace_service.projects().patchTraces(
        projectId=self.project_id, body=body)
    _res = request.execute()


class _Phase(object):
  """A _Phase instance represents a period of time during request processing."""

  def __init__(self, name, color, parent):
    """Initialize a (sub)phase with the given name and current system clock."""
    self.start = time.time()
    self.name = name[:MAX_PHASE_NAME_LENGTH]
    self.color = color
    self.subphases = []
    self.elapsed_seconds = None
    self.ms = 'in_progress'  # shown if the phase never records a finish.
    self.uncategorized_ms = None
    self.parent = parent
    if self.parent is not None:
      self.parent._RegisterSubphase(self)

    self.id = str(random.getrandbits(64))


  def _RegisterSubphase(self, subphase):
    """Add a subphase to this phase."""
    self.subphases.append(subphase)

  def End(self):
    """Record the time between the start and end of this (sub)phase."""
    self.elapsed_seconds = time.time() - self.start
    self.ms = int(self.elapsed_seconds * 1000)
    for sub in self.subphases:
      if sub.elapsed_seconds is None:
        logging.warn('issue3182: subphase is %r', sub and sub.name)
    categorized = sum(sub.elapsed_seconds or 0.0 for sub in self.subphases)
    self.uncategorized_ms = int((self.elapsed_seconds - categorized) * 1000)
    return self.parent

  def AccumulateStatLines(self, total_seconds, lines, indent=''):
    # Only phases that took longer than 30ms are interesting.
    if self.ms <= 30:
      return

    percent = self.elapsed_seconds // total_seconds * 100
    lines.append('%s%5d ms (%2d%%): %s' % (indent, self.ms, percent, self.name))

    # Remove IDs etc to reduce the phase name cardinality for ts_mon.
    normalized_phase = re.sub('[0-9]+', '', self.name)
    PHASE_TIME.add(self.ms, {'phase': normalized_phase})

    for subphase in self.subphases:
      subphase.AccumulateStatLines(total_seconds, lines, indent=indent + '   ')

  def SpanJson(self):
    """Return a json representation of this phase as a GCP Cloud Trace object.
    """
    endTime = self.start + self.elapsed_seconds

    span = {
      'kind': 'RPC_SERVER',
      'name': self.name,
      'spanId': self.id,
      'startTime':
          datetime.datetime.fromtimestamp(self.start).isoformat() + 'Z',
      'endTime': datetime.datetime.fromtimestamp(endTime).isoformat() + 'Z',
    }

    if self.parent is not None and self.parent.id is not None:
      span['parentSpanId'] = self.parent.id

    spans = [span]
    for s in self.subphases:
      spans.extend(s.SpanJson())

    return spans
