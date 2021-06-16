# Copyright 2008 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""URL mappings for the codereview package."""

from django.conf.urls.defaults import patterns
from django.conf.urls.defaults import url
import django.views.defaults
from django.views.generic.base import RedirectView

urlpatterns = patterns(
    'codereview.views',

    # TODO(ojan): Remove the scrape urls once there are JSON APIs for them.
    (r'^scrape/?$', 'index'),
    (r'^$', 'index'),

    (r'^scrape/(\d+)/?$', 'show', {}, 'show_bare_issue_number'),
    (r'^(\d+)/?$', 'show', {}, 'show_bare_issue_number'),

    # TODO(jrobbins): scrape/settings can be removed after the next deployment.
    (r'^scrape/settings$', 'settings'),
    (r'^settings$', 'settings'),
    (r'^api/settings$', 'api_settings'),

    # TODO(ojan): Use the api and remove the scrape URL.
    (r'^scrape/user/([^/]+)$', 'show_user'),
    (r'^user/([^/]+)$', 'show_user'),
    (r'^api/user_inbox/([^/]+)$', 'api_user_inbox'),

    # TODO(ojan): all/mine/starred/show are not useful. Remove them once
    # we remove the deprecated UI.
    (r'^all$', 'view_all'),
    (r'^mine$', 'mine'),
    (r'^starred$', 'starred'),
    (r'^(\d+)/(?:show)?$', 'show'),

    (r'^download/issue(\d+)_(\d+)\.diff', 'download'),
    (r'^download/issue(\d+)_(\d+)_(\d+)\.diff', 'download_patch'),
    (r'^(\d+)/patch/(\d+)/(\d+)$', 'patch'),
    (r'^(\d+)/image/(\d+)/(\d+)/(\d+)$', 'image'),
    (r'^(\d+)/diff/(\d+)/(.+)$', 'diff'),
    (r'^(\d+)/diff2/(\d+):(\d+)/(.+)$', 'diff2'),
    # The last path element is optional till the polymer UI supports it.
    (r'^(\d+)/diff_skipped_lines/(\d+)/(\d+)/(\d+)/(\d+)/([tba])/(\d+)$',
     'diff_skipped_lines'),
    (r'^(\d+)/diff_skipped_lines/(\d+)/(\d+)/(\d+)/(\d+)/([tba])/(\d+)/(\d+)$',
     'diff_skipped_lines'),
    (r'^(\d+)/diff_skipped_lines/(\d+)/(\d+)/$',
     django.views.defaults.page_not_found, {}, 'diff_skipped_lines_prefix'),
    # The last path element is optional till the polymer UI supports it.
    (r'^(\d+)/diff2_skipped_lines/(\d+):(\d+)/(\d+)/(\d+)/(\d+)/([tba])/(\d+)$',
     'diff2_skipped_lines'),
    (r'^(\d+)/diff2_skipped_lines/(\d+):(\d+)/(\d+)/(\d+)/(\d+)/([tba])'
     '/(\d+)/(\d+)$', 'diff2_skipped_lines'),
    (r'^(\d+)/diff2_skipped_lines/(\d+):(\d+)/(\d+)/$',
     django.views.defaults.page_not_found, {}, 'diff2_skipped_lines_prefix'),
    (r'^(\d+)/description$', 'description'),
    (r'^(\d+)/fields', 'fields'),
    (r'^api/(\d+)/?$', 'api_issue'),
    (r'^api/(\d+)/(\d+)/?$', 'api_patchset'),
    (r'^tarball/(\d+)/(\d+)$', 'tarball'),
    (r'^account_delete$', 'account_delete'),
    (r'^user_popup/(.+)$', 'user_popup'),
    (r'^(\d+)/patchset/(\d+)$', 'patchset'),
    (r'^(\d+)/patchset/(\d+)/get_depends_on_patchset$',
     'get_depends_on_patchset'),
    (r'^account$', 'account'),
    (r'^xsrf_token$', 'xsrf_token'),
    (r'^search$', 'search'),
    (r'^get-access-token$', 'get_access_token'),
    (r'^oauth2callback$', 'oauth2callback'),
    # Restricted access.
    (r'^restricted/set-client-id-and-secret$', 'set_client_id_and_secret'),
    (r'^restricted/user/([^/]+)/block$', 'block_user'),
    )


# Chromium urls
urlpatterns += patterns(
    'codereview.views_chromium',
    (r'^(\d+)/binary/(\d+)/(\d+)/(\d+)$', 'download_binary'),
    )
