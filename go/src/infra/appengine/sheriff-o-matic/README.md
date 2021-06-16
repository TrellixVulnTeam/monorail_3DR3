# sheriff-o-matic

aka SoM

**NOTE: All of the instructions below assume you are working in a single shell
window. All shell commands should be run from the sheriff-o-matic directory
(where this README lives).**

## Prerequisites

You will need a chrome infra checkout as
[described here](https://chromium.googlesource.com/infra/infra/). That will
create a local checkout of the entire infra repo, but that will include this
application and many of its dependencies.

Warning: If you are starting from scratch, there may be a lot more setup involved
than you expected. Please bear with us.

You'll also need some extras that aren't in the default infra checkout.

```sh
# sudo where appropriate for your setup.

npm install -g bower
```

If you don't have npm or node installed yet, make sure you do so using
`gclient runhooks` to pick up infra's CIPD packages for nodejs and
npm (avoid using other installation methods, as they won't match what
the builders and other infra devs have installed). *Then* make sure you've
run

```sh
eval `../../../../env.py`
```
in that shell window.

## Setting up credentials for local development and testing

You will need access to either staging or prod
sheriff-o-matic before you can do this, so contact cit-sheriffing@google.com
to request access ("Please add me to the relevant AMI roles...") if you don't already have it.

```
# in case you already have this pointed at a jwt file downloaded from gcp console:
unset GOOGLE_APPLICATION_CREDENTIALS

# Use your user identity instead of a service account, will require web flow auth:
gcloud auth application-default login
```

Note that some services (notably, Monorail) will not honor your credentials when
authenticated this way. You'll see `401 Unauthorized` responses in the console logs.
For these, you may need to get service account credentials.
We no longer recommend developers download service account credentials to their machines
because they are more sensitive (and GCP limits how many we can have out in the wild).

## Getting up and running locally

After initial checkout, make sure you have all of the bower dependencies
installed. Also run this whenever bower.json is updated:

```sh
make build
```

(Note that you should always be able to `rm -rf frontend/bower_components`
and re-run `bower install` at any time. Occasionally there are changes that,
when applied over an existing `frontend/bower_components`, will b0rk your
checkout.)

To run locally from an infra.git checkout:
```sh
make devserver
```

To run tests:
```sh
# Default (go and JS):
make test

# For go:
go test infra/appengine/sheriff-o-matic/som/...

# For interactive go, automatically re-runs tests on save:
cd som && goconvey

# For JS:
cd frontend
make wct

# For debugging JS, with a persistent browser instance you can reload:
cd frontend
make wct_debug
```

To view test coverage report after running tests:
```sh
google-chrome ./coverage/lcov-report/index.html
```
## Access to AppEngine instances

If you would like to test your changes on our staging server (this is often
necessary in order to test and debug integrations, and some issues will
only reliably reproduce in the actual GAE runtime rather than local devserver),
please contact cit-sheriffing@google.com to request access. We're happy to
grant staging access to contributors!

## Deploying a new release

First create a new CL for the RELNOTES.md update. Then run:
```sh
make relnotes
```

Note that you may need to authenticate for deployment as
described below in order to have `make relnotes` work properly this way.

Copy and paste the output into the top of `RELNOTES.md` and make any manual
edits if necessary.

You can also use the optional flags `-since-date YYYY-MM-DD` or
`-since-hash=<git short hash>` if you need to manually specify the range
of commits to include, using the command
```
go run ../../tools/relnotes/relnotes.go -since-hash <commit_hash> -app sheriff-o-matic -extra-paths .,../../monitoring/analyzer,../../monitoring/client,../../monitoring/messages
```

Tips: You can find the commit hash of a version by looking at the version name in appengine (Go to pantheon page for your app, and click at Versions section). For example, if your version name is 12345-20d8b52, then the commit hash is 20d8b52.

Then:

- Send the RELNOTES.md update CL for review by OWNERS.
- Land CL.
- run `make deploy_prod`
- Double-check that the version is not named with a `-tainted` suffix, as deploying
such a version will cause alerts to fire (plus, you shouldn't deploy uncommitted code :).
- Go to the Versions section of the
[App Engine Console](https://appengine.google.com/) and update the default
version of the app services. **Important**: *Remember to update both the "default" and "analyzer"
services* by clicking the "Migrate traffic" button. Having the default and analyzer services running different versions
may cause errors and/or monitoring alerts to fire.
- Wait for a while, making sure that the graphs looks fine and there is no abnormality in https://viceroy.corp.google.com/chrome_infra/Appengine/sheriff_o_matic_prod?duration=1h
- Send a PSA email to cit-sheriffing@ about the new release.

### Deploying to staging

Sheriff-o-Matic also has a staging server with the AppEngine ID
sheriff-o-matic-staging. To deploy to staging:

- run `make deploy_staging`
- Optional: Go to the Versions section of the
[App Engine Console](https://appengine.google.com/) and update both the default
and backend versions of the app.
- Check https://viceroy.corp.google.com/chrome_infra/Appengine/sheriff_o_matic_staging?duration=1h, make sure everything is ok

### Authenticating for deployment

In order to deploy to App Engine, you will need to be a member of the
project (either sheriff-o-matic or sheriff-o-matic-staging). Before your first
deployment, you will have to run `./gae.py login` to authenticate yourself.

### Modifying BigQuery views

If you modify the SQL files for bigquery views (sheriffable_failures.sql, failing_steps.sql, step_status_transitions.sql), the steps to deploy your changes are as follows:
- `cd ./bigquery`
- Run `./create_views.sh` to deploy your change to staging
- Verify that everything works as expected
- Create a CL with your changes and get it reviewed
- Land your change
- Modify the file create_views.sh to point to prod by setting `APP_ID=sheriff-o-matic`
- Run `./create_views.sh` again to deploy your change to prod
- Verify that everything works as expected in prod
- Revert the change in create_views.sh by setting `APP_ID=sheriff-o-matic-staging`

If you want to revert your deployment, simply checkout master and run `./create_view.sh` again for staging and prod


## Configuring and populating devserver SoM with alerts

Once you have a server running locally, you'll want to add at least one
tree configuration to the datastore. Make sure you are logged in locally
as an admin user (admin checkbox on fake devserver login page).

Navigate to [localhost:8080/admin/portal](http://localhost:8080/admin/portal)
and fill out the tree(s) you wish to test with locally. For consistency, you
may just want to copy the [settings from prod](http://sheriff-o-matic.appspot.com/admin/portal).

If you don't have access to prod or staging, you can manually enter this for
"Trees in SOM" to get started with a reasonable default:

```
android:Android,chromeos:Chrome OS,chromium:Chromium,chromium.perf:Chromium Perf,gardener:ChromeOS Gardener,ios:iOS,trooper:Trooper
```

After you have at least one tree configured, you'll want to populate your
local SoM using either local cron tasks or alerts-dispatcher.

### Populating alerts from local cron tasks (any tree besides Chrome OS):
You can use local cron anaylzers and skip all of this by navigating to e.g.
[http://localhost:8081/_cron/analyze/chromium](http://localhost:8081/_cron/analyze/chromium).
You can replace `chromium` in `_cron/analyze/chromium` with the name of whichever tree you
wish to analyze. Note that the cron analyzers run on a different port than the
UI (8081 vs 8080). This is because the cron tasks run in a separate GAE service
(aka "module" in some docs). These requests may also take quite a while to
complete, depending on the current state of your builders.

## Contributors

We don't currently run the `WCT` tests on CQ. So *please* be sure to run them
yourself before submitting. Also keep an eye on test coverage as you make
changes. It should not decrease with new commits.