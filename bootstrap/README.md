# Bootstrapping infra.git

[TOC]

The [infra.git](/) repo uses python [wheel files][wheel files],
[virtualenv][virtualenv] and [pip][pip] to manage dependencies. The process for
bootstrapping these is contained entirely within [bootstrap/ directory](.).

See [dockerbuild](/infra/tools/dockerbuild/README.md) for a tool that tries to
make a lot of this easier. If you use dockerbuild to build a wheel for
bootstrap, you will need to upload it manually to the
[wheelhouse](https://pantheon.corp.google.com/storage/browser/chrome-python-wheelhouse/wheels).
(TODO: We should enable Dockerbuild to upload to wheelhouse too.) Check the
`.dockerbuild/wheels` directory for the local wheel.

## TL;DR - Workflows

### Setting up the env with already-built-deps

Just run:

    gclient sync
    # OR
    gclient runhooks

### Adding a new dep

Say we want to add a stock my\_pkg python package at version 1.2.3:

#### Tarball

If it comes from a tarball:

    $ ./bootstrap/ingest_source.py <tarball>
    ...
    deadbeefdeadbeefdeadbeefdeadbeef.tar.gz

#### Another repo

If it comes from a repo, file a ticket to have it mirrored (no matter what VCS!)
to `chromium.googlesource.com/external/<repo_url>`

Grab the git commit hash of the commit to build:
badc0ffeebadc0ffeebadc0ffeebadc0

Then add the actual dep:

    $ edit bootstrap/deps.pyl  # add a new entry (see the 'deps.pyl' section)
    ...
      'my_pkg' : {
        'version': '1.2.3',
        'build': 0,  # This is the first build
        'gs':  'deadbeefdeadbeefdeadbeefdeadbeef.tar.gz',  # if tarball
        'rev': 'badc0ffeebadc0ffeebadc0ffeebadc0',         # if repo
      }
    ...

Then build it:

    $ ./bootstrap/build_deps.py --upload
    # builds and uploads my_pkg-1.2.3-0_deadbeef...-....whl to google storage

*** note
If your dep is not pure-python, you will have to run `build_deps.py`
for each platform.
***

*** note
If you're running an unsupported platform (the main symptom being that `gclient
sync` fails with `__main__.NoWheelException: No matching wheel found for`. See
http://crbug.com/520285 for more details), then you have to run `build_deps.py`
to rebuild the missing packages. See also 'rolling deps' below. If you don't
have permission to upload the generated packages to Cloud Storage (e.g. if
you're not a Googler), then drop the `--upload` option and all packages will be
stored locally only.
***

### If your dep needs special treatment

Do everything in the [Adding a new dep](#Adding-a-new-dep) section, but before
running `build_deps.py`, add a file
`custom_builds/{wheel package name}.py`. This file is expected to
implement:

    def Build(source_path, wheelhouse_path)

See [custom builds](#Custom-builds) below for more detail.

## bootstrap.py (a.k.a. "I just want a working infra repo!")

Run `gclient runhooks`. Under the hood, this runs:

    ./bootstrap/bootstrap.py --deps_file bootstrap/deps.pyl ENV

This creates a virtualenv called `{repo_root}/ENV` with all the deps
contained in `bootstrap/deps.pyl`. You must be online, or must already
have the wheels for your system in cache.

If you already have an `ENV` directory, [bootstrap.py](bootstrap.py) will check
the manifest in `ENV` to see if it matches [deps.pyl](#deps_pyl) (i.e. the diff
is zero). If it's not, then `ENV` directory will be re-created *from scratch*.

[run.py](../run.py) will automatically use the environment `ENV`. It is
an error to use `run.py` without first setting up `ENV`.

## [deps.pyl](deps.pyl)

This file is a python dictionary containing the exact versions of all
Python module dependencies. These versions are the standard upstream
package versions (e.g. '0.8.0'), plus the commit hash or sha1.{ext} of
an [ingested source bundle](injest_source.py).

The format of this file is `{'package_name': <values>}`. This file is a
Python
[ast literal](https://docs.python.org/2/library/ast.html#ast.literal_eval),
so comments are allowed and encouraged.

Note that the `package_name` key is the pip-reported name (the one set
in `setup.py`). It may be different from the name used for import, and
for the wheel.

Values are:

* version: The pip version of the module
* build: An integer representing which build of this version/hash. If you
  modify the _way_ that a requirement is built, but not the source
  hash, you can bump the build number to get a new pinned dependency.

And either:

* `rev`: The revision or sha1 of the source for this module. The repo
  is
  `git+https://chromium.googlesource.com/infra/third_party/{package_name}`
* `gs`: `{sha1}.{ext}` indicates file
  `gs://chrome-python-wheelhouse/sources/{sha1}.{ext}`. The sha1 will
  be checked against the content of the file.

And optionally:

* `implicit`: A boolean indicating that this dep should only be
  installed as a dependency of some other dep. For example, you want
  package A, which depends on package Z, but you don't really care
  about Z. You should mark Z as `implicit` to allow it to be pinned
  correctly, but not to deliberately install it.

## [ingest_source.py](ingest_source.py)

Some python modules don't have functional python repos (i.e. ones that
pip can natively clone+build), and thus ship their source in tarballs.
To ingest such a tarball into the infra google storage bucket, use
`ingest_source.py /path/to/archive`. This will print the value for the
'gs' key for a deps.pyl entry.

## build_deps.py / rolling deps

Any time a new dependency/version is introduced into `deps.pyl`, you
must run `build_deps.py --upload`. If the dependency is a pure-Python
dependency (i.e. no compiled extensions), you only need to run it once on
CPython 2.7. You can tell that it's a pure python module by looking at the name
of the wheel file. For example:

    requests-2.3.0-py2.py3-none-any.whl

Is compatible with Python 2 and Python 3 (py2.py3) any python ABI
(none), and any OS platform (any).

Running [build_deps.py](build_deps.py) will only attempt to build dependencies
which are missing for the current platform.

If the module does contain compiled extensions, you must run
[build_deps.py](build_deps.py) on the following systems (all with CPython 2.7):

* OS X 10.9 - `x86_64`
* Windows 7 - `x86_64`
* Linux - `x86_64`

TODO(iannucci): Add job to build wheels on all appropriate systems.

Once a wheel is sucessfully built, it is uploaded to
`gs://chrome-python-wheelhouse/wheels` if it is not there already.

Only Googlers have access to that bucket. Make sure to run the following
command to authenticate first:

    depot_tools/third_party/gsutil/gsutil config

[build_deps.py](build_deps.py) assumes that it can find `gsutil` on `PATH`, so
go ahead and install it appropriately for whichever platform you're on.

## Custom builds

Sometimes building a wheel is a bit trickier than
`pip wheel {repo}@{hash}`. In order to support this, add a script named
`custom_builds/{name}.py`. This module should have a function defined
like:

```python
def Build(source_path, wheelhouse_path)
```

Where `source_path` is a string path to the checked-out / unpacked
source code, and `wheelhouse_path` is a string path where
`build_deps.py` expects to find a `.whl` file after Build completes.

Note that your Build function will actually need to invoke pip manually.
Currently you can get the path for pip by doing:
`os.path.join(sys.prefix, 'bin', 'pip')`, and you can invoke it with
subprocess
([example](https://code.google.com/p/chromium/codesearch#chromium/infra/bootstrap/custom)).

## Rolling the version of wheel

Since wheel is a package needed to build the wheels, it has a slightly
different treatment. To roll a wheel, bump the version in deps.pyl, and
then run `bootstrap_wheel_wheel.sh` to build and upload the wheel for
`wheel` pinned at the version in `deps.pyl`.

Once you do that, `build_deps.py` will continue working as expected.

## Building deps on Windows

TODO(iannucci): actually implement this

Windows builds require a slightly more care when building, due to the
complexities of getting a compile environment. To this effect,
`build_deps.py` relies on the `depot_tools/win_toolchain` functionality
to get a hermetic windows compiler toolchain. This should not be an
issue for chromium devs working on windows, since they should already
have this installed by compiling chromium, but it's something to be
aware of.

## Modified (non-upstream) deps

If it is necessary to roll a patched version of a library, we should
branch it in the infra googlesource mirror. This branch should be named
`{version}-cr`, and will build packages whose version is
`{version}.{cr_version}` (e.g. modify `setup.py` on this branch to add
an additional component to the version field).

For example, given the package `jane` at version `2.1.3`, we would
create a branch `2.1.3-cr`. On this branch we would commit any changes
necessary to `2.1.3`, and would adjust the version number in the builds
to be e.g. `2.1.3.0`.

[wheel files]: https://www.python.org/dev/peps/pep-0427/
[virtualenv]: https://github.com/pypa/virtualenv
[pip]: https://github.com/pypa/pip

## Platform Problems

### NoWheelExecption

A builder is failing with NoWheelException, but you feel strongly that the
entry in [deps.pyl](deps.pyl) matches what is in the
[wheelhouse](https://pantheon.corp.google.com/storage/browser/chrome-python-wheelhouse/wheels).

One thing that might be happening is that pip doesn't think that wheel, based on
its filename, is supported for that platform. You might log on to that bot and
start a python interpreter:

```
>>> import pip
>>> pip.pep425tags.supported_tags
```

will list all of the [supported tags](https://www.python.org/dev/peps/pep-0425/)
for that platform. What to do next depends on your particular situation, but
hopefully this information is helpful for giving you ideas.
