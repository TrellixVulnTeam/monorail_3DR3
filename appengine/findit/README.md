# Assumptions

The Current Working Directory is $SRC_ROOT/infra/appengine/findit, i.e. the
directory that contains this file. Please `cd` into it for the commands below to
work.

Note:
1. For Mac, if GoogleAppEngineLauncher is used to run Findit locally, you
    may have to set the field "Extra Flags" under "Launch Settings" with value
   "$SRC_ROOT/infra/appengine/findit/waterfall-backend.yaml
    $SRC_ROOT/infra/appengine/findit/waterfall-frontend.yaml".
2. For Windows, you may have to read the contents of the makefile to learn how
   to run all of the commands manually.

# How to run Findit locally?

From command line, run:
  `make run`

Then open http://localhost:8080 for the home page.

# How to run unit tests for Findit?

From command line, run:
 * `make test` to run all tests;
 * `make test TEST_GLOB=<path to a sub dir>` to run tests in a sub directory;
 * `make test TEST_GLOB=<path to a sub dir>:*<test name>*` to run a given test.


If a code path branch is not tested and no line number is shown in the command
line output, you could check the code coverage report shown in the output.

# How to automatically format python code?

YAPF is used to format the code in chromium style, and it is expected to format
the code before uploading a CL for review. To install YAPF, please refer to
https://github.com/google/yapf.

From command line, run:
  `make format`

# How to deploy to appengine?

## Staging
Deploy to the staging instance (and make it default):
  `make deploy-findit-staging`

## Production
Deploy to analysis.chromium.org (production):
  `make deploy-findit-prod`

Please use [pantheon] to make the new version default.

# Code Structure
* Findit v1
  * [services/](services/) contains service-layer code for the core analysis logic
  for compile failures, reliable test failures, and flaky tests.
  * [pipelines/](pipelines/) contains code for the pipeline flows that connect the
  different analysis units from the service layer.
* Findit v2
  * [findit_v2/](findit_v2/) contains code of Findit v2. To add support to a Luci
  project, please make changes in this directory.

# BQ Event Tables

To get bqchemaupdater installed run
```shell
  cd infra/go
  eval `./env.py`
  ./deps.py update
  ./deps.py install
```
This should install it in your path.

In the event that you need to create a table, run a command like this:
```shell
bqschemaupdater -message-dir <absolute findit dir>/model/proto/
                -table "findit-for-me.events.test"
                -message findit.TestAnalysisCompletionEvent
                -dry-run
```
From findit/ this command may be out of date. Refer to bqschemaupdater --help.

WARNING: Consult with chrome-findit@ before running any commands that may
affect production data. Once you're confident that the command does what you
want, remove the -dry-run argument.

[pantheon]: https://pantheon.corp.google.com/appengine/versions?project=findit-for-me&src=ac&versionId=alpha&moduleId=default&pli=1&serviceId=default&versionssize=50
