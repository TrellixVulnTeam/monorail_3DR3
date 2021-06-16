This is forked from : https://chromium.googlesource.com/infra/infra/+/master/appengine/monorail. Please refer https://github.com/epiFi/monorail/pull/1 for our changes.

# Monorail Issue Tracker

Monorail is the Issue Tracker used by the Chromium project and other related
projects. It is hosted at [bugs.chromium.org](https://bugs.chromium.org).

If you wish to file a bug against Monorail itself, please do so in our
[self-hosting tracker](https://bugs.chromium.org/p/monorail/issues/entry).
We also discuss development of Monorail at `infra-dev@chromium.org`.

# Getting started with Monorail development

Here's how to run Monorail locally for development on MacOS and Debian stretch/buster or its derivatives.

1.  You need to [get the Chrome Infra depot_tools commands](https://commondatastorage.googleapis.com/chrome-infra-docs/flat/depot_tools/docs/html/depot_tools_tutorial.html#_setting_up) to check out the source code and all its related dependencies and to be able to send changes for review.
1.  Check out the Monorail source code
    1.  `cd /path/to/empty/workdir`
    1.  `fetch infra`
    1.  `cd infra/appengine/monorail`
1.  Make sure you have the AppEngine SDK:
    1.  It should be fetched for you by step 1 above (during runhooks)
    1.  Otherwise, you can download it from https://developers.google.com/appengine/downloads#Google_App_Engine_SDK_for_Python
1.  Install MySQL v5.6.
    1. On a Debian derivative, download and unpack [this bundle](https://dev.mysql.com/get/Downloads/MySQL-5.6/mysql-server_5.6.40-1ubuntu14.04_amd64.deb-bundle.tar):
        1.  `tar -xf mysql-server_5.6.40-1ubuntu14.04_amd64.deb-bundle.tar`
    1. Install the packages in the order of `mysql-common`,`mysql-community-client`, `mysql-client`, then `mysql-community-server`.
    1. As of March 2020, MacOS MySQL setup will look something like this:
        ```
        1. Install docker
        2. Run MySQL@5.6 in docker
        3. Install MySQL locally (only needed for MySQL-python)
        4. Set MySQL user passwords
        5. Install MySQL-python
        6. Initialize database with tables
        7. Run the app locally
        ```
        1.  Install [docker for mac](https://docs.docker.com/docker-for-mac/install/).
        1.  Start your docker container named mysql for MySQL v5.6.
            1.  `docker run --name mysql -e MYSQL_ROOT_PASSWORD=my-secret-pw -p 3306:3306 -d mysql:5.6`
        1. Use [homebrew](https://brew.sh/) to install MySQL v5.6 on your system for its configs to install MySQLdb later. We will be using the docker container's MySQL instance.
            1.  `brew install mysql@5.6`
    1. Otherwise, download from the [official page](http://dev.mysql.com/downloads/mysql/5.6.html#downloads).
        1.  **Do not download v5.7 (as of April 2016)**
1.  Get the database backend configured and running:
    1. On Debian
        1.  Allow passwordless authentication from non-root users:
            1.  `sudo mysql -uroot mysql -e "UPDATE user SET host='%', plugin='' WHERE user='root'; FLUSH PRIVILEGES;"`
        1.  Disable `STRICT_TRANS_TABLES`
            1.  `echo -e "[mysqld]\nsql_mode = ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION" | sudo tee /etc/mysql/conf.d/99-sql-mode.cnf`
        1.  `sudo /etc/init.d/mysql restart`
    1. On MacOS
        1.  Enter the docker container and update its authentication.
            1.  `docker exec -it mysql bash`
            1.  `mysqladmin -u root -p'my-secret-pw' password ''`
            1.  `mysql -uroot mysql -e "UPDATE user SET host='172.17.0.1', plugin='' WHERE user='root'; FLUSH PRIVILEGES; exit;"`
                1.  We set the host to 172.17.0.1 to match the docker container. Your docker container may be at a different IP, you use `docker network inspect bridge` from another terminal to verify your container's IP.
        1. Exit the docker container
            1.  `exit`
1.  Install Python MySQLdb.
    1.  On Debian, use apt-get:
        1. `sudo apt-get install python-mysqldb`
    1.  On MacOS, use pip
        1. `export LIBRARY_PATH=$LIBRARY_PATH:/usr/local/opt/openssl/lib/`
        1.  Check if you have pip, if you don't, install it first
            1.  `sudo easy_install pip`
        1. `pip install MYSQL-python`
    1.  Otherwise, download from http://sourceforge.net/projects/mysql-python/
        1.  Follow instructions to install.
        1.  If needed, add these lines to your ~/.profile file and restart on MacOS 10.8:
            1.  setenv DYLD_LIBRARY_PATH /usr/local/mysql/lib/
            1.  setenv VERSIONER_PYTHON_PREFER_64_BIT no
            1.  setenv VERSIONER_PYTHON_PREFER_32_BIT yes
        1.  In Mac OSX 10.11.1, if you see errors about failing to import MySQLdb or that _mysql.so references an untrusted relative path, then run:
  `sudo install_name_tool -change libmysqlclient.18.dylib \
  /usr/local/mysql/lib/libmysqlclient.18.dylib \
  /Library/Python/2.7/site-packages/_mysql.so`
1.  Set up one master SQL database. (You can keep the same sharding options in settings.py that you have configured for production.).
    1. On Debian
        1.  `mysql --user=root -e 'CREATE DATABASE monorail;'`
        1.  `mysql --user=root monorail < schema/framework.sql`
        1.  `mysql --user=root monorail < schema/project.sql`
        1.  `mysql --user=root monorail < schema/tracker.sql`
    1. On MacOS
        1. Install your schema into the docker container
            1.  `docker cp schema/. mysql:/schema`
            1.  `docker exec -it mysql bash`
            1.  `mysql --user=root monorail < schema/framework.sql`
            1.  `mysql --user=root monorail < schema/project.sql`
            1.  `mysql --user=root monorail < schema/tracker.sql`
1.  Configure the site defaults in settings.py.  You can leave it as-is for now.
1.  Set up the front-end development environment:
    1. On Debian
        1.  ``eval `../../go/env.py` `` -- you'll need to run this in any shell you
            wish to use for developing Monorail. It will add some key directories to
            your `$PATH`.
        1.  `npm install`
        1.  Install build requirements:
            1.  `sudo apt-get install build-essential automake`
    1. On MacOS
        1.  Install npm
            1.  `brew install nvm`
            1.   See the brew instructions on updating your shell's configuration
            1.  `nvm install 12.13.0`
            1.  `npm install`
1.  Run the app:
    1.  `make serve`
1.  Browse the app at localhost:8080 your browser.
1.  Optional: Create/modify your Monorail User row in the database and make that user a site admin. You will need to be a site admin to gain access to create projects through the UI.
    1.  `mysql --user=root monorail -e "UPDATE User SET is_site_admin = TRUE WHERE email = 'test@example.com';"`
    1.  If the admin change isn't immediately apparent, you may need to restart your local dev appserver.

Instructions for deploying Monorail to an existing instance or setting up a new instance are [here](doc/deployment.md).

Here's how to run unit tests from the command-line:

## Testing

To run all Python unit tests, in the `appengine/monorail` directory run:

```
make test
```

For quick debugging, if you need to run just one test you can do the following. For instance for the test
`IssueServiceTest.testUpdateIssues_Normal` in `services/test/issue_svc_test.py`:

```
../../test.py test appengine/monorail:services.test.issue_svc_test.IssueServiceTest.testUpdateIssues_Normal --no-coverage
```

### Frontend testing

To run the frontend tests for Monorail, you first need to set up your Go environment. From the Monorail directory, run:

```
eval `../../go/env.py`
```

Then, to run the frontend tests, run:

```
make karma
```

To run only one test or a subset of tests, you can add `.only` to the test
function you want to isolate:

```javascript
// Run one test.
it.only(() => {
  ...
});

// Run a subset of tests.
describe.only(() => {
  ...
});
```

Just remember to remove them before you upload your CL.

## Troubleshooting

*   `TypeError: connect() got an unexpected keyword argument 'charset'`

This error occurs when `dev_appserver` cannot find the MySQLdb library.  Try installing it via <code>sudo apt-get install python-mysqldb</code>.

*   `TypeError: connect() argument 6 must be string, not None`

This occurs when your mysql server is not running.  Check if it is running with `ps aux | grep mysqld`.  Start it up with <code>/etc/init.d/mysqld start </code>on linux, or just <code>mysqld</code>.

*   dev_appserver says `OSError: [Errno 24] Too many open files` and then lists out all source files

dev_appserver wants to reload source files that you have changed in the editor, however that feature does not seem to work well with multiple GAE modules and instances running in different processes.  The workaround is to control-C or `kill` the dev_appserver processes and restart them.

*   `IntegrityError: (1364, "Field 'comment_id' doesn't have a default value")` happens when trying to file or update an issue

In some versions of SQL, the `STRICT_TRANS_TABLES` option is set by default. You'll have to disable this option to stop this error.

*   `ImportError: No module named six.moves`

You may not have six.moves in your virtual environment and you may need to install it.

1.  Determine that python and pip versions are possibly in vpython-root
    1.  `which python`
    1.  `which pip`
1.  If your python and pip are in vpython-root
    1.  ```sudo `which python` `which pip` install six```

# Development resources

## Supported browsers

Monorail supports all browsers defined in the [Chrome Ops guidelines](https://chromium.googlesource.com/infra/infra/+/master/doc/front_end.md).

File a browser compatability bug
[here](https://bugs.chromium.org/p/monorail/issues/entry?labels=Type-Defect,Priority-Medium,BrowserCompat).

## Frontend code practices

See: [Monorail Frontend Code Practices](doc/code-practices/frontend.md)

## Monorail's design

* [Monorail Data Storage](doc/design/data-storage.md)
* [Monorail Email Design](doc/design/emails.md)
* [How Search Works in Monorail](doc/design/how-search-works.md)
* [Monorail Source Code Organization](doc/design/source-code-organization.md)
* [Monorail Testing Strategy](doc/design/testing-strategy.md)

## Triage process

See: [Monorail Triage Guide](doc/triage.md)

## Release process

See: [Monorail Deployment](doc/deployment.md)

# User guide

For information on how to user Monorail, see the [Monorail User Guide](doc/userguide/README.md).
