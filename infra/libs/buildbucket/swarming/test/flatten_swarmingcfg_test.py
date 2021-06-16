# Copyright 2018 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import unittest

from google.protobuf import text_format

from infra import init_python_pb2  # pylint: disable=unused-import
from go.chromium.org.luci.buildbucket.proto import project_config_pb2

from infra.libs.buildbucket.swarming import flatten_swarmingcfg


class ProjectCfgTest(unittest.TestCase):

  def test_parse_dimensions(self):
    dims = ['pool:default', 'cpu:x86-64', '60:cpu:x86']
    actual = flatten_swarmingcfg.parse_dimensions(dims)
    expected = {
        'pool': {('default', 0)},
        'cpu': {('x86-64', 0), ('x86', 60)},
    }
    self.assertEqual(expected, actual)

  def test_format_dimensions(self):
    dims = {
        'pool': {('default', 0)},
        'cpu': {('x86-64', 0), ('x86', 60)},
    }
    actual = flatten_swarmingcfg.format_dimensions(dims)
    self.assertEqual(['60:cpu:x86', 'cpu:x86-64', 'pool:default'], actual)

  def test_flatten_builder(self):

    def test(cfg_text, expected_builder_text):
      cfg = project_config_pb2.BuildbucketCfg()
      text_format.Merge(cfg_text, cfg)
      builder = cfg.buckets[0].swarming.builders[0]
      flatten_swarmingcfg.flatten_builder(
          builder,
          cfg.buckets[0].swarming.builder_defaults,
          {m.name: m for m in cfg.builder_mixins},
      )

      expected = project_config_pb2.Builder()
      text_format.Merge(expected_builder_text, expected)
      self.assertEqual(builder, expected)

    test(
        '''
        buckets {
          name: "bucket"
          swarming {
            hostname: "chromium-swarm.appspot.com"
            url_format: "https://example.com/{swarming_hostname}/{task_id}"
            builder_defaults {
              swarming_tags: "commontag:yes"
              dimensions: "cores:8"
              dimensions: "pool:default"
              dimensions: "cpu:x86-86"
              properties: "{\\\"a\\\":\\\"b\\\"}"
              recipe {
                name: "recipe"
                cipd_package: "infra/recipe_bundle"
                cipd_version: "refs/heads/master"
              }
              caches {
                name: "git_chromium"
                path: "git_cache"
              }
              caches {
                name: "build_chromium"
                path: "out"
              }
            }
            builders {
              name: "builder"
              swarming_tags: "buildertag:yes"
              dimensions: "os:Linux"
              dimensions: "pool:Chrome"
              dimensions: "cpu:"
              priority: 108
              properties: "{\\\"c\\\":\\\"d\\\"}"
              recipe {
                properties: "predefined-property:x"
                properties_j: "predefined-property-bool:true"
              }
              caches {
                name: "a"
                path: "a"
              }
            }
          }
        }
        ''',
        '''
        name: "builder"
        swarming_tags: "buildertag:yes"
        swarming_tags: "commontag:yes"
        dimensions: "cores:8"
        dimensions: "cpu:"
        dimensions: "os:Linux"
        dimensions: "pool:Chrome"
        priority: 108
        properties: "{\\\"a\\\":\\\"b\\\",\\\"c\\\":\\\"d\\\"}"
        recipe {
          name: "recipe"
          cipd_package: "infra/recipe_bundle"
          cipd_version: "refs/heads/master"
          properties_j: "predefined-property:\\\"x\\\""
          properties_j: "predefined-property-bool:true"
        }
        caches {
          name: "a"
          path: "a"
        }
        caches {
          name: "build_chromium"
          path: "out"
        }
        caches {
          name: "git_chromium"
          path: "git_cache"
        }
      ''',
    )

    # Diamond merge.
    test(
        '''
          builder_mixins {
            name: "base"
            dimensions: "d1:base"
            dimensions: "d2:base"
            dimensions: "d3:base"
            dimensions: "60:d4:base"
            swarming_tags: "t1:base"
            swarming_tags: "t2:base"
            swarming_tags: "t3:base"
            caches {
              name: "c1"
              path: "base"
            }
            caches {
              name: "c2"
              path: "base"
            }
            caches {
              name: "c3"
              path: "base"
            }
            recipe {
              name: "base"
              properties: "p1:base"
              properties: "p2:base"
              properties: "p3:base"
              properties_j: "pj1:\\\"base\\\""
              properties_j: "pj2:\\\"base\\\""
              properties_j: "pj3:\\\"base\\\""
            }
          }
          builder_mixins {
            name: "first"
            mixins: "base"
            dimensions: "d2:first"
            dimensions: "d3:first"
            dimensions: "120:d4:first"
            swarming_tags: "t2:first"
            swarming_tags: "t3:first"
            caches {
              name: "c2"
              path: "first"
            }
            caches {
              name: "c3"
              path: "first"
            }
            recipe {
              name: "first"
              cipd_package: "infra/recipe_bundle"
              cipd_version: "refs/heads/master"
              properties: "p2:first"
              properties_j: "pj2:\\\"first\\\""
            }
          }
          builder_mixins {
            name: "second"
            mixins: "base"
            dimensions: "d2:"
            dimensions: "d3:second"
            swarming_tags: "t3:second"
            caches {
              name: "c3"
              path: "second"
            }
            recipe {
              name: "second"
              properties: "p3:second"
              # Unset p2 and p2j
              properties_j: "p2:null"
              properties_j: "pj2:null"
              properties_j: "pj3:\\\"second\\\""
            }
          }
          buckets {
            name: "bucket"
            swarming {
              hostname: "chromium-swarm.appspot.com"
              builders {
                name: "builder"
                mixins: "first"
                mixins: "second"
              }
            }
          }
        ''',
        '''
          name: "builder"
          dimensions: "60:d4:base"
          dimensions: "d1:base"
          dimensions: "d2:"
          dimensions: "d3:second"
          swarming_tags: "t1:base"
          swarming_tags: "t2:base"
          swarming_tags: "t2:first"
          swarming_tags: "t3:base"
          swarming_tags: "t3:first"
          swarming_tags: "t3:second"
          caches {
            name: "c1"
            path: "base"
          }
          caches {
            name: "c2"
            path: "base"
          }
          caches {
            name: "c3"
            path: "second"
          }
          recipe {
            name: "second"
            cipd_package: "infra/recipe_bundle"
            cipd_version: "refs/heads/master"
            properties_j: "p1:\\\"base\\\""
            properties_j: "p2:\\\"first\\\""
            properties_j: "p3:\\\"second\\\""
            properties_j: "pj1:\\\"base\\\""
            properties_j: "pj2:\\\"first\\\""
            properties_j: "pj3:\\\"second\\\""
          }
        ''',
    )

    # builder_defaults, a builder_defaults mixin and a builder mixin.
    test(
        '''
          builder_mixins {
            name: "default"
            dimensions: "pool:builder_default_mixin"
          }
          builder_mixins {
            name: "builder"
            dimensions: "pool:builder_mixin"
          }
          buckets {
            name: "bucket"
            swarming {
              hostname: "chromium-swarm.appspot.com"
              builder_defaults {
                mixins: "default"
                dimensions: "pool:builder_defaults"
                recipe {
                  name: "foo"
                  cipd_package: "infra/recipe_bundle"
                  cipd_version: "refs/heads/master"
                }
              }
              builders {
                name: "release"
                mixins: "builder"
              }
            }
          }
        ''',
        '''
          name: "release"
          dimensions: "pool:builder_mixin"
          recipe {
            name: "foo"
            cipd_package: "infra/recipe_bundle"
            cipd_version: "refs/heads/master"
          }
        ''',
    )
    # with auto_builder_dimension and mixins and defaults.
    test(
        '''
          builder_mixins {
            name: "mixme"
            dimensions: "pool:mixed"
          }
          buckets {
            name: "bucket"
            swarming {
              builder_defaults {
                auto_builder_dimension: YES
                dimensions: "pool:dedicated"
              }
              builders {
                name: "ng-1000"
                mixins: "mixme"
                properties: "{\\\"a\\\":\\\"b\\\"}"
              }
            }
          }
        ''',
        '''
          name: "ng-1000"
          dimensions: "pool:mixed"
          auto_builder_dimension: YES
          properties: "{\\\"a\\\":\\\"b\\\"}"
      ''',
    )

    # repeated dimension keys
    test(
        '''
          builder_mixins {
            name: "mixme"
            dimensions: "cores:8"
          }
          buckets {
            name: "bucket"
            swarming {
              builders {
                name: "ng-1000"
                mixins: "mixme"

                dimensions: "60:cores:64"
                dimensions: "cores:16"
              }
            }
          }
        ''',
        '''
          name: "ng-1000"
          dimensions: "60:cores:64"
          dimensions: "cores:16"
      ''',
    )

    # exe.cmd
    test(
        '''
          buckets {
            name: "bucket"
            swarming {
              builder_defaults {
                exe {
                  cmd: "luciexe"
                }
              }
              builders {
                name: "default"
              }
            }
          }
        ''',
        '''
          name: "default"
          exe { cmd: "luciexe" }
      ''',
    )

    # exe.cmd
    test(
        '''
          buckets {
            name: "bucket"
            swarming {
              builder_defaults {
                exe {
                  cmd: "luciexe"
                }
              }
              builders {
                name: "override"
                exe {
                  cmd: "recipes"
                }
              }
            }
          }
        ''',
        '''
          name: "override"
          exe { cmd: "recipes" }
      ''',
    )

    # properties
    test(
        '''
          buckets {
            name: "bucket"
            swarming {
              builder_defaults {
                properties: "{\\"recipe\\":\\"world\\"}"
              }
              builders {
                name: "default"
                properties: "{\\"fleem\\":\\"baz\\"}"
              }
            }
          }
        ''',
        '''
          name: "default"
          properties: "{\\"fleem\\":\\"baz\\",\\"recipe\\":\\"world\\"}"
      ''',
    )

    # properties override
    test(
        '''
          buckets {
            name: "bucket"
            swarming {
              builder_defaults {
                properties: "{\\"recipe\\":\\"world\\"}"
              }
              builders {
                name: "default"
                properties: "{\\"fleem\\":\\"baz\\",\\"recipe\\":\\"nope\\"}"
              }
            }
          }
        ''',
        '''
          name: "default"
          properties: "{\\"fleem\\":\\"baz\\",\\"recipe\\":\\"nope\\"}"
      ''',
    )



  def test_merge_toggle(self):
    unset = project_config_pb2.Builder()
    yes = project_config_pb2.Builder(experimental=project_config_pb2.YES)
    no = project_config_pb2.Builder(experimental=project_config_pb2.NO)

    b = project_config_pb2.Builder()
    flatten_swarmingcfg.merge_builder(b, unset)
    flatten_swarmingcfg.merge_builder(b, yes)
    self.assertEqual(b.experimental, project_config_pb2.YES)

    flatten_swarmingcfg.merge_builder(b, unset)
    self.assertEqual(b.experimental, project_config_pb2.YES)

    flatten_swarmingcfg.merge_builder(b, no)
    self.assertEqual(b.experimental, project_config_pb2.NO)

  def test_merge_luci_migration_host(self):
    unset = project_config_pb2.Builder()
    yes = project_config_pb2.Builder(luci_migration_host='example.com')
    no = project_config_pb2.Builder(luci_migration_host='-')

    b = project_config_pb2.Builder()
    flatten_swarmingcfg.merge_builder(b, unset)
    flatten_swarmingcfg.merge_builder(b, yes)
    self.assertEqual(b.luci_migration_host, 'example.com')

    flatten_swarmingcfg.merge_builder(b, unset)
    self.assertEqual(b.luci_migration_host, 'example.com')

    flatten_swarmingcfg.merge_builder(b, no)
    self.assertEqual(b.luci_migration_host, '-')

if __name__ == '__main__':
  unittest.main()
