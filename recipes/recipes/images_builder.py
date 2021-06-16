# Copyright 2019 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from collections import namedtuple
from recipe_engine import recipe_api

from PB.recipes.infra import images_builder as images_builder_pb

DEPS = [
    'recipe_engine/buildbucket',
    'recipe_engine/commit_position',
    'recipe_engine/futures',
    'recipe_engine/json',
    'recipe_engine/path',
    'recipe_engine/properties',
    'recipe_engine/step',
    'recipe_engine/time',

    'depot_tools/gerrit',

    'cloudbuildhelper',
    'infra_checkout',
]


PROPERTIES = images_builder_pb.Inputs


# Metadata is returned by _checkout_* and applied to built images.
Metadata = namedtuple('Metadata', [
    'canonical_tag',  # str or None
    'labels',         # {str: str}
    'tags',           # [str]
])


def RunSteps(api, properties):
  try:
    _validate_props(properties)
  except ValueError as exc:
    raise recipe_api.InfraFailure('Bad input properties: %s' % exc)

  # Checkout either the committed code or a pending CL, depending on the mode.
  # This also calculates metadata (labels, tags) to apply to images built from
  # this code.
  if properties.mode in (PROPERTIES.MODE_CI, PROPERTIES.MODE_TS):
    co, meta = _checkout_committed(api, properties.mode, properties.project)
  elif properties.mode == PROPERTIES.MODE_CL:
    co, meta = _checkout_pending(api, properties.project)
  else:  # pragma: no cover
    raise recipe_api.InfraFailure(
        'Unknown mode %s' % PROPERTIES.Mode.Name(properties.mode))
  co.gclient_runhooks()

  # Discover what *.yaml manifests (full paths to them) we need to build.
  manifests = api.cloudbuildhelper.discover_manifests(
      co.path, properties.manifests)
  if not manifests:  # pragma: no cover
    raise recipe_api.InfraFailure('Found no manifests to build')

  with co.go_env():
    # Use 'cloudbuildhelper' that comes with the infra checkout (it's in PATH),
    # to make sure builders use same version as developers.
    api.cloudbuildhelper.command = 'cloudbuildhelper'

    # Report the exact version we picked up from the infra checkout.
    api.cloudbuildhelper.report_version()

    # Build, tag and upload corresponding images (in parallel).
    futures = {}
    for m in manifests:
      fut = api.futures.spawn(
          api.cloudbuildhelper.build,
          manifest=m,
          canonical_tag=meta.canonical_tag,
          build_id=api.buildbucket.build_url(),
          infra=properties.infra,
          labels=meta.labels,
          tags=meta.tags)
      futures[fut] = m

  # Wait until all builds complete.
  built = []
  fails = []
  for fut in api.futures.iwait(futures.keys()):
    try:
      img = fut.result()
      if img != api.cloudbuildhelper.NotUploadedImage:
        built.append(img)
    except api.step.StepFailure:
      fails.append(api.path.basename(futures[fut]))

  # Try to roll even if something failed. One broken image should not block the
  # rest of them.
  if built and properties.HasField('roll_into'):
    with api.step.nest('upload roll CL') as roll:
      num, url = _roll_built_images(api, properties.roll_into, built, meta)
      if num is not None:
        roll.presentation.links['Issue %s' % num] = url

  if fails:
    raise recipe_api.StepFailure('Failed to build: %s' % ', '.join(fails))


def _validate_props(p):  # pragma: no cover
  if p.mode == PROPERTIES.MODE_UNDEFINED:
    raise ValueError('"mode" is required')
  if p.project == PROPERTIES.PROJECT_UNDEFINED:
    raise ValueError('"project" is required')
  if not p.infra:
    raise ValueError('"infra" is required')
  if not p.manifests:
    raise ValueError('"manifests" is required')
  # There's no CI/TS for luci-go. Its CI happens when it gets rolled in into
  # infra.git. But we still can run tryjobs for luci-go by applying CLs on top
  # of infra.git checkout.
  if p.project == PROPERTIES.PROJECT_LUCI_GO and p.mode != PROPERTIES.MODE_CL:
    raise ValueError('PROJECT_LUCI_GO can be used only together with MODE_CL')
  if p.HasField('roll_into') and p.mode == PROPERTIES.MODE_CL:
    raise ValueError('"roll_into" can\'t be used in MODE_CL')


def _checkout_committed(api, mode, project):
  """Checks out some committed revision (based on Buildbucket properties).

  Args:
    api: recipes API.
    mode: PROPERTIES.Mode enum (either MODE_CI or MODE_TS).
    project: PROPERTIES.Project enum.

  Returns:
    (infra_checkout.Checkout, Metadata).
  """
  conf, internal, repo_url = {
    PROPERTIES.PROJECT_INFRA: (
        'infra',
        False,
        'https://chromium.googlesource.com/infra/infra',
    ),
    PROPERTIES.PROJECT_INFRA_INTERNAL: (
        'infra_internal',
        True,
        'https://chrome-internal.googlesource.com/infra/infra_internal',
    ),
  }[project]

  co = api.infra_checkout.checkout(gclient_config_name=conf, internal=internal)
  rev = co.bot_update_step.presentation.properties['got_revision']
  cp = co.bot_update_step.presentation.properties['got_revision_cp']

  cp_ref, cp_num = api.commit_position.parse(cp)
  if cp_ref != 'refs/heads/master':  # pragma: no cover
    raise recipe_api.InfraFailure(
        'Only refs/heads/master commits are supported for now, got %r' % cp_ref)

  canonical_tag = None
  if mode == PROPERTIES.MODE_CI:
    canonical_tag = 'ci-%s-%d-%s' % (_date(api), cp_num, rev[:7])
  elif mode == PROPERTIES.MODE_TS:
    canonical_tag = 'ts-%s-%d' % (_date(api), api.buildbucket.build.number)
  else:
    raise AssertionError('Impossible')  # pragma: no cover

  return co, Metadata(
      canonical_tag=canonical_tag,
      labels={
          'org.opencontainers.image.source': repo_url,
          'org.opencontainers.image.revision': rev,
      },
      tags=['latest'])


def _checkout_pending(api, project):
  """Checks out some pending CL (based on Buildbucket properties).

  Args:
    api: recipes API.
    project: PROPERTIES.Project enum.

  Returns:
    (infra_checkout.Checkout, Metadata).
  """
  conf, patch_root, internal = {
    PROPERTIES.PROJECT_INFRA: (
        'infra',
        'infra',
        False,
    ),
    PROPERTIES.PROJECT_INFRA_INTERNAL: (
        'infra_internal',
        'infra_internal',
        True,
    ),
    PROPERTIES.PROJECT_LUCI_GO: (
        'infra',
        'infra/go/src/go.chromium.org/luci',
        False,
    ),
  }[project]

  co = api.infra_checkout.checkout(
      gclient_config_name=conf,
      patch_root=patch_root,
      internal=internal)
  co.commit_change()

  # Grab information about this CL (in particular who wrote it).
  cl = api.buildbucket.build.input.gerrit_changes[0]
  repo_url = 'https://%s/%s' % (cl.host, cl.project)
  rev_info = api.gerrit.get_revision_info(repo_url, cl.change, cl.patchset)
  author = rev_info['commit']['author']['email']

  return co, Metadata(
      # ':inputs-hash' essentially tells cloudbuildhelper to skip the build if
      # there's already an image built from the exact same inputs.
      canonical_tag=':inputs-hash',
      labels={'org.chromium.build.cl.repo': repo_url},
      tags=[
          # An "immutable" tag that identifies how the image was built.
          'cl-%s-%d-%d-%s' % (
              _date(api),
              cl.change,
              cl.patchset,
              author.split('@')[0],
          ),
          # A movable tag for "a latest image produced from this CL". It is
          # intentionally simple, so that developers can "guess" it just knowing
          # the CL number.
          'cl-%d' % cl.change,
      ])


def _date(api):
  """Returns UTC YYYY.MM.DD to use in tags."""
  return api.time.utcnow().strftime('%Y.%m.%d')


def _roll_built_images(api, spec, images, meta):
  """Uploads a CL with info about built images into a repo with pinned images.

  See comments in images_builder.proto for more details.

  Args:
    api: recipes API.
    spec: instance of images_builder.Inputs.RollInto proto with the config.
    images: a list of CloudBuildHelperApi.Image with info about built images.
    meta: Metadata struct, as returned by _checkout_committed.

  Returns:
    (None, None) if didn't create a CL (because nothing has changed).
    (Issue number, Issue URL) if created a CL.
  """
  return api.cloudbuildhelper.do_roll(
      repo_url=spec.repo_url,
      root=api.path['cache'].join('builder', 'roll'),
      callback=lambda root: _mutate_pins_repo(api, root, spec, images, meta))


def _mutate_pins_repo(api, root, spec, images, meta):
  """Modifies the checked out repo with image pins.

  Args:
    api: recipes API.
    root: the directory where the repo is checked out.
    spec: instance of images_builder.Inputs.RollInto proto with the config.
    images: a list of CloudBuildHelperApi.Image with info about built images.
    meta: Metadata struct, as returned by _checkout_committed.

  Returns:
    cloudbuildhelper.RollCL to proceed with the roll or None to skip it.
  """
  # RFC3389 timstamp in UTC zone.
  date = api.time.utcnow().isoformat('T') + 'Z'

  # Prepare tag JSON specs for all images.
  # See //scripts/roll_images.py in infradata/k8s repo.
  tags = []
  for img in images:
    tags.append({
        'image': img.image,
        'tag': {
            'tag': img.tag,
            'digest': img.digest,
            'metadata': {
                'date': date,
                'source': {
                    'repo': meta.labels['org.opencontainers.image.source'],
                    'revision':
                        meta.labels['org.opencontainers.image.revision'],
                },
                'links': {
                    'buildbucket': api.buildbucket.build_url(),
                    'cloudbuild': img.view_build_url,
                    'gcr': img.view_image_url,
                },
            },
        },
    })

  # Add all new tags (if any).
  res = api.step(
      name='roll_images.py',
      cmd=[root.join('scripts', 'roll_images.py')],
      stdin=api.json.input({'tags': tags}),
      stdout=api.json.output(),
      step_test_data=lambda: api.json.test_api.output_stream(
          _roll_images_test_data(tags)))
  rolled = res.stdout['tags']
  deployments = res.stdout.get('deployments') or []

  # If added new pins, delete old unused ones (if any). Note that if we are
  # building a rollback CL, we often do not add new pins (since we actually
  # rebuild a previously built image). We still need to land a CL to do the
  # rollback. If it turns out nothing has changed, api.cloudbuildhelper.do_roll
  # will just skip uploading the change.
  if rolled:
    api.step(
        name='prune_images.py',
        cmd=[root.join('scripts', 'prune_images.py'), '--verbose'])

  # Generate the commit message.
  message = str('\n'.join([
      '[images] Rolling in images.',
      '',
      'Produced by %s' % api.buildbucket.build_url(),
      '',
      'Updated staging deployments:',
  ] + [
      '  * %s: %s -> %s' % (d['image'], d['from'], d['to'])
      for d in deployments
  ] + ['']))

  # List of people to CC based on what staging deployments were updated.
  extra_cc = set()
  for dep in deployments:
    extra_cc.update(dep.get('cc') or [])

  return api.cloudbuildhelper.RollCL(
      message=message,
      cc=extra_cc,
      tbr=spec.tbr,
      commit=spec.commit)


def _roll_images_test_data(tags):
  return {
      'tags': tags,
      'deployments': [
          {
              'cc': ['n1@example.com', 'n2@example.com'],
              'channel': 'staging',
              'from': 'prev-version',
              'spec': 'projects/something/channels.json',
              'image': t['image'],
              'to': t['tag']['tag'],
          }
          for t in tags
      ],
  }


def GenTests(api):
  def try_props(project, cl, patch_set):
    return (
        api.buildbucket.try_build(
            project=project,
            change_number=cl,
            patch_set=patch_set) +
        api.override_step_data(
            'gerrit changes',
            api.json.output([{
                'project': project,
                '_number': cl,
                'revisions': {
                    '184ebe53805e102605d11f6b143486d15c23a09c': {
                        '_number': patch_set,
                        'commit': {
                            'message': 'Commit message',
                            'author': {'email': 'author@example.com'},
                        },
                        'ref': 'refs/changes/../../..',
                    },
                },
            }]),
        )
    )


  yield (
      api.test('try-infra') +
      api.properties(
          mode=PROPERTIES.MODE_CL,
          project=PROPERTIES.PROJECT_INFRA,
          infra='dev',
          manifests=['infra/build/images/deterministic'],
      ) +
      try_props('infra/infra', 123456, 7)
  )

  yield (
      api.test('try-luci-go') +
      api.properties(
          mode=PROPERTIES.MODE_CL,
          project=PROPERTIES.PROJECT_LUCI_GO,
          infra='dev',
          manifests=['infra/build/images/deterministic'],
      ) +
      try_props('infra/luci/luci-go', 123456, 7)
  )

  yield (
      api.test('try-infra-internal') +
      api.properties(
          mode=PROPERTIES.MODE_CL,
          project=PROPERTIES.PROJECT_INFRA_INTERNAL,
          infra='dev',
          manifests=['infra_internal/build/images/deterministic'],
      ) +
      try_props('infra/infra_internal', 123456, 7)
  )

  yield (
      api.test('ci-infra') +
      api.properties(
          mode=PROPERTIES.MODE_CI,
          project=PROPERTIES.PROJECT_INFRA,
          infra='prod',
          manifests=['infra/build/images/deterministic'],
      )
  )

  yield (
      api.test('ci-infra-internal') +
      api.properties(
          mode=PROPERTIES.MODE_CI,
          project=PROPERTIES.PROJECT_INFRA_INTERNAL,
          infra='prod',
          manifests=['infra_internal/build/images/deterministic'],
      )
  )

  yield (
      api.test('ts-infra') +
      api.properties(
          mode=PROPERTIES.MODE_TS,
          project=PROPERTIES.PROJECT_INFRA,
          infra='prod',
          manifests=['infra/build/images/daily'],
      )
  )

  yield (
      api.test('ci-infra-with-roll') +
      api.properties(
          mode=PROPERTIES.MODE_CI,
          project=PROPERTIES.PROJECT_INFRA,
          infra='prod',
          manifests=['infra/build/images/deterministic'],
          roll_into={
              'repo_url': 'https://images.repo.example.com',
              'tbr': ['someone@example.com'],
              'commit': True,
          },
      ) +
      api.step_data('upload roll CL.git diff', retcode=1)
  )

  yield (
      api.test('build-failure') +
      api.properties(
          mode=PROPERTIES.MODE_CI,
          project=PROPERTIES.PROJECT_INFRA,
          infra='prod',
          manifests=['infra/build/images/deterministic'],
      ) +
      api.step_data(
          'cloudbuildhelper build target',
          api.cloudbuildhelper.build_error_output('Boom'),
          retcode=1)
  )

  yield (
      api.test('bad-props') +
      api.properties(mode=0)
  )
