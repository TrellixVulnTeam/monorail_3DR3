# Overview

Our event pipeline collects, stores, and aggregates event data from ChOps
services. Event data can be any piece of information we want to collect for
analysis or tracking. It is distinct from timeseries data, for which we use
[tsmon](https://chrome-internal.googlesource.com/infra/infra_internal/+/master/doc/ts_mon.md).

For Googlers, see the [internal docs](https://chrome-internal.googlesource.com/infra/infra_internal/+/master/doc/event_pipeline.md).

[TOC]

# Exploring Tables

Lists of tables and their descriptions are available by project (e.g. infra or
infra_internal) at doc/bigquery_tables.md. Table owners are responsible for
updating those lists.

[infra tables](../bigquery_tables.md)

# Step 1: Create a BigQuery table

## Table Organization

Tables are commonly identified by `<project-id>.<dataset_id>.<table_id>`.

BigQuery tables belong to datasets. Dataset IDs and table IDs should be
underscore delimited, e.g. `test_results`.

For services which already have corresponding Google Cloud Projects, tables
should be created in their own project, under the dataset "events." For other
services, create a new GCP project.

Datasets can be created in the easy-to-use [console](bigquery.cloud.google.com).

Rationale for per-project tables:

* Each project may ACL its tables as it sees fit, and apply its own quota
constraints to stay within budget.
* Different GCP instances of the same application code (say, staging vs
production for a given AppEngine app) may keep separate ACLs and retention
policies for their logs so they don’t write over each other.

## Creating and updating tables

Tables are defined by schemas. Schemas are stored in .proto form. Therefore we
have version control and can use the protoc tool to create language-specific
instances. Use
[bqschemaupdater](https://chromium.googlesource.com/infra/luci/luci-go/+/master/tools/cmd/bqschemaupdater/README.md)
to create new tables or modify existing tables in BigQuery. As of right now,
this tool must be run manually. Run the go environment setup script from
infra.git:

    eval `go/env.py`

and this should install bqschemaupdater in your path. See the
[docs](https://chromium.googlesource.com/infra/luci/luci-go/+/master/tools/cmd/bqschemaupdater/README.md)
or run `bqschemaupdater --help` for more information.

# Step 2: Send events to BigQuery

Once you have a table, you can send events to it!

## Credentials

The following applies to non-GCP projects. Events sent from GCP projects to
tables owned by the same project should just work.

You need to ensure the machines that will be running the code which sends events
have proper credentials. At this point, you may need to enlist the help of a
Chrome Operations Googler, as many of the following resources and repos are
internal.

1. Choose a [service
   account](https://cloud.google.com/docs/authentication/#service_accounts).
   This account may be a service account that is already associated with the
   service, or it may be a new one that you create.
1. Give that service account the "BigQuery Data Editor" IAM role using the
   [cloud console](https://console.cloud.google.com) under "IAM & Admin" >>
   "IAM" in the `chrome-infra-events` project. You'll need the proper privileges
   to do this. If you don't have them, ask a Chrome Infrastructure team member
   for help.
1. If you have created a new private key for an account, you'll need to add it
   to puppet. [More
   info.](https://chrome-internal.googlesource.com/infra/puppet/+/master/README.md)
1. Make sure that file is available to your service. For CQ, this takes the form
   of passing the name of the credentials file to the service on start. [See
   CL.](https://chrome-internal-review.googlesource.com/c/405268/)

## How to Choose a Library

### TLDR

Go: use
[go.chromium.org/luci/common/bq](https://godoc.org/go.chromium.org/luci/common/bq),
[example CL](https://chromium-review.googlesource.com/c/infra/infra/+/719962).

Python: use
[infra.libs.bqh](https://cs.chromium.org/chromium/infra/infra/libs/bqh.py),
[example CL](https://chrome-internal-review.googlesource.com/c/infra/infra_internal/+/445955),
[docs](https://chromium.googlesource.com/infra/infra/+/master/infra/libs/README.md).


### Options

How you instrument your code to add event logging depends on your needs, and
there are a couple of options.

If you don’t need transactional integrity, and prefer a simpler configuration,
use [bq.Uploader](https://godoc.org/go.chromium.org/luci/common/bq#Uploader)
This should be your default choice if you’re just starting out.

If you need ~8ms latency on inserts, or transactional integrity with datastore
operations, use
[bqlog](https://godoc.org/go.chromium.org/luci/tokenserver/appengine/impl/utils/bqlog)
[TODO: update this link if/when bqlog moves out of tokenserver into a shared
location].

Design trade-offs for using bq instead of bqlog: lower
accuracy and precision. Some events may be duplicated in logs (say, if an
operation that logs events has to be retried due to datastore contention).
Intermittent failures in other supporting infrastructure may also cause events
to be lost.

Design trade-offs for using bqlog instead of bq: You will have to
enable task queues in your app if you haven’t already, and add a new cron task
to your configuration. You will also not be able to use the bqschemaupdater
(described below) tool to manage your logging schema code generation.

### From Go: bq package

Package [bq](https://godoc.org/go.chromium.org/luci/common/bq)
takes care of some boilerplate and makes it easy to add monitoring for uploads.
It also takes care of adding insert IDs, which BigQuery uses to deduplicate
rows. If you are not using
[bq.Uploader](https://godoc.org/go.chromium.org/luci/common/bq#Uploader),
check out
[bq.InsertIDGenerator](https://godoc.org/go.chromium.org/luci/common/bq#InsertIDGenerator).

With `bq`, you can construct a synchronous `Uploader` or asynchronous
`BatchUploader` depending on your needs.

[kitchen](../../go/src/infra/tools/kitchen/monitoring.go) is an example of a
tool that uses bq.

### From Python: infra/libs/bqh

You will need the
[google-cloud-bigquery](https://pypi.python.org/pypi/google-cloud-bigquery)
library in your environment. infra.git/ENV has this dependency already, so you
only need to add it if you are working outside that environment.

Check out the (../../infra/libs/bqh.py)[bigquery helper module]. Under the hood,
it uses the [BigQuery Python
client](https://cloud.google.com/bigquery/docs/reference/libraries#client-libraries-usage-python).
It is recommended that you use it over using the client directly, as it houses
common logic around handling edge cases, formatting errors, and handling
protobufs. You'll still have to provide an authenticated instance of
google.cloud.bigquery.client.Client.

See
[this change](https://chrome-internal-review.googlesource.com/c/407748/)
for a simple example. (TODO: replace with a non-internal example that uses
BigQueryHelper.) The [API
docs](https://googlecloudplatform.github.io/google-cloud-python/stable/bigquery-usage.html)
can also be helpful.

### From Python GAE:

1. Use [message_to_dict](https://chromium.googlesource.com/infra/infra/+/fe875b1417d5d6a73999462b1001a2852ef6efb9/packages/infra_libs/infra_libs/bqh.py#24)
   function to convert a protobuf message to a dict.
2. Use [BigQuery REST API](https://cloud.google.com/bigquery/docs/reference/rest/v2/tabledata/insertAll)
   to insert rows.
3. Don't forget to include insert ids in the request!

# Step 3: Analyze/Track/Graph Events

Generally you will use the [bigquery console](https://bigquery.cloud.google.com)
for this. You can also use [google data studio](https://datastudio.google.com),
which allows you to create dashboards and graphs from bigquery data.

## Querying plx tables from bigquery

Googlers can query existing plx tables from bigquery. Here's an example query:

    SELECT issue, patchset, attempt_start_msec FROM
    chrome_infra.cq_attempts
    LIMIT 10;

To make this work on big query, you need to change the table. That example query
would look like this on bigquery:

    SELECT issue, patchset, attempt_start_msec FROM
    `plx.google:chrome_infra.cq_attempts.all`
    LIMIT 10;

Note the `all` suffix on the table. This is only for tables which don't have
existing suffixes like `lastNdays`, `today`.

ACLs for these tables depend on the user's gaia ID. If a service account needs
access to a plx table, you need to add them as a READER to the table, which can
be done either in PLX or in the materialization script. Request a googler to do
this for you.

Note that it appears that enums lose their string values when you query them
through bigquery. This means that you need to change

    SELECT *
    FROM chrome_infra.cq_attempts
    WHERE fail_type = 'NOT_LGTM'

into

    SELECT *
    FROM `plx.google:chrome_infra.cq_attempts.all`
    WHERE fail_type = 4

## Joining tables from other projects

To execute a query which joins a table from a different cloud project, ensure
the querying project's service account has BigQuery read permissions in the
other project.

## Other tools

[Datastudio](http://datastudio.google.com): for graphs, reports, and dashboards

# Limits

BigQuery and Dataflow limits are documented for tools when they are relevant.
Because many components of the pipeline make API requests to BigQuery, that is
documented here.

API Request limits are per user. In our case, the use is most often a service
account. Check the [BigQuery
docs](https://cloud.google.com/bigquery/quotas#apirequests) for the most up to
date limits. At the time of writing, there are limits on requests per second and
concurrent api requests. The client is responsible for ensuring it does not
exceed these limits.
