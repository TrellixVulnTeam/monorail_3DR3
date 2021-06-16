# This is an application designed to collect and analyze build/compile stats.

[go/cbs-doc](http://go/cbs-doc)

Deign Doc: [Chromium build time profiler](https://docs.google.com/a/chromium.org/document/d/16TdPTIIZbtAarXZIMJdiT9CePG5WYCrdxm5u9UuHXNY/edit#heading=h.xgjl2srtytjt)

How to:

See [infra/go/README.md](../../../../README.md) for preparation.

 to re-generate trace-viewer contents in app dir.
```shell
  $ (cd app; \
      <CHROMIUM_SRC>/third_party/catapult/tracing/bin/trace2html /dev/null \
         --output=tmpl/trace-viewer.html)
```
Note: to update trial origin tokens,
re-generate trial origin tokens on
https://developers.chrome.com/origintrials/#/trials/active
for WebComponents V0 for https://chromium-build-stats.appspot.com
and https://chromium-build-stats-staging.appspot.com,
and update
[catapult/common/py_vulcanize/py_vulcanize/generate.py](https://chromium.googlesource.com/catapult.git/+/c757d41a83a706565d4a17118e15a70475d77358/common/py_vulcanize/py_vulcanize/generate.py#55).


 to compile

```shell
  $ make build
```

 to run locally with dev_appserver
 (note: no service account available, so you couldn't
  fetch file from gs://chrome-goma-log)

```shell
   $ (cd app; dev_appserver.py app.yaml)
```


 to deploy to production
```shell
  $ make deploy-prod
```

 and need to [migrate traffic](https://cloud.google.com/appengine/docs/standard/go/migrating-traffic).

 NOTE: Check ninja trace data after deploy. If it's not accessible,
 you must forget to generate trace-viewer contents (See the first item of
 this how-to). Re-generate it and deploy again.

 to run test

```shell
  $ make test
```

 to read go documentation

```shell
  $ godoc <package>
  $ godoc <package> <symbol>
```

 (or

```shell
  $ godoc -http :6060
```
 and go to http://localhost:6060
 )

## Operation for BigQuery Table

Setup

1. Make Dataset

```shell
$ bq --project_id=$PROJECT mk ninjalog
```

2. Make table

```shell
# Set 2 year expiration.
# This is for log table from buildbot.
$ bq --project_id=$PROJECT mk --time_partitioning_type=DAY \
    --time_partitioning_expiration=$((3600 * 24 * 365 * 2)) ninjalog.ninjalog

# This is for log table from chromium developer.
# Set ***540 days*** expiration.
$ bq --project_id=$PROJECT mk --time_partitioning_type=DAY \
    --time_partitioning_expiration=$((3600 * 24 * 30 * 18)) ninjalog.user
```

3. Update schema

```shell
$ make update-prod # or `make update-staging`
```

## ninja log upload from user

Ninja log is uploaded from user too.
Upload script is located in [depot_tools](https://chromium.googlesource.com/chromium/tools/depot_tools.git/+/master/ninjalog_uploader.py).

### example query

[link to query editor](https://console.cloud.google.com/bigquery?project=chromium-build-stats)

1. Find time consuming build tasks in a day per target_os, build os and outputs

```
SELECT
  (
  SELECT
    value
  FROM
    UNNEST(build_configs)
  WHERE
    key = "target_os") target_os,
  os,
  SUBSTR(ARRAY_TO_STRING(log_entry.outputs, ", "), 0, 128) outputs,
  TRUNC(AVG(log_entry.end_duration_sec - log_entry.start_duration_sec), 2) task_duration_avg,
  TRUNC(SUM(log_entry.end_duration_sec - log_entry.start_duration_sec), 2) task_duration_sum,
  TRUNC(SUM(weighted_duration_sec), 2) weighted_duration_sum,
  COUNT(1) cnt
FROM
  `chromium-build-stats.ninjalog.user`
WHERE
  (_PARTITIONTIME >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
    -- This is for streaming buffer.
    OR _PARTITIONTIME IS NULL)
GROUP BY
  target_os,
  os,
  outputs
ORDER BY
  weighted_duration_sum DESC
```
