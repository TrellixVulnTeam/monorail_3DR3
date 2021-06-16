// Copyright 2018 The LUCI Authors. All rights reserved.
// Use of this source code is governed under the Apache License, Version 2.0
// that can be found in the LICENSE file.

package main

import (
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"

	"github.com/maruel/subcommands"
	"golang.org/x/net/context"

	cipd_common "go.chromium.org/luci/cipd/common"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/stringmapflag"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/sync/parallel"
)

func bundleCmd() *subcommands.Command {
	return &subcommands.Command{
		UsageLine: "bundle [options]",
		ShortDesc: "Bundles recipe repos",
		LongDesc: `This will create CIPD package bundles for each repo.

The CIPD package name will be '<package-name-prefix>/<repo>'. For example
a package name might be:

  infra/recipe_bundles/chromium.googlesource.com/chromium/tools/build

The package will be tagged with 'git_revision:<repo_revision_pin>'. If the tool
was instructed to package the latest version (i.e. 'FETCH_HEAD'), it will also
set the CIPD ref to match both the stated ref (i.e. 'HEAD'), as well as the ref
that it resolves to ('HEAD' usually resolves to 'refs/heads/master', but this
depends on the repo). So, if you go with the default of:

  '{ref=HEAD, revision=FETCH_HEAD}'

And the repo has HEAD -> refs/heads/master, the tool will update the 'HEAD' and
'refs/heads/master' CIPD refs. If you ask this tool to fetch 'refs/foo/bar', this
tool would update 'refs/foo/bar'.
`,

		CommandRun: func() subcommands.CommandRun {
			ret := &cmdBundle{}
			ret.logCfg.Level = logging.Info
			ret.logCfg.AddFlags(&ret.Flags)

			ret.Flags.Var(&ret.reposInput, "r",
				`(repeatable) A `+"`"+`repospec`+"`"+` to bundle (e.g. 'host.name/to/repo').

A git revision may be provided with an =, e.g. 'host.name/to/repo=deadbeef'.
The revision must be either a full hexadecimal commit id, or it may be the
literal 'FETCH_HEAD' to indicate that the latest version should be used.

If this revision lies on a ref other than 'HEAD', you may provide the
ref to fetch after the revision by separating it with a comma, e.g.
'host.name/to/repo=deadbeef,refs/other/thing'. Note that most repos configure
'HEAD' to symlink to 'refs/heads/master'. See e.g.
https://stackoverflow.com/a/8841024

You may also provide one of more comma-separated glob refs, which will create
bundles for all matching refs, e.g.:
  'host.name/to/repo=FETCH_HEAD,refs/other/*,refs/example/1*'.
would create bundles for refs like:
  refs/other/thing1, refs/other/thing2, refs/example/1234, etc.
Note that this only makes sense with a revision of 'FETCH_HEAD', which will
bundle the latest commit on each matched branch.`)

			ret.Flags.StringVar(&ret.localDest, "local", "",
				`Set to a non-empty path, and this tool will produce CIPD packages in that local directory.
	Otherwise it will upload them to CIPD.`)

			ret.Flags.StringVar(&ret.workdir, "workdir", "./recipe_bundler",
				`Set where this tool should store its repo checkouts`)

			ret.Flags.StringVar(&ret.packageNamePrefix, "package-name-prefix", "",
				`Set the CIPD package name prefix.`)

			ret.Flags.StringVar(&ret.packageNameInternalPrefix, "package-name-internal-prefix", "",
				`Set the CIPD package name prefix for repos containing the word "internal".`)

			ret.Flags.StringVar(&ret.cipd.serviceURL, "service-url", "",
				`Set to override the default CIPD service URL.`)

			return ret
		},
	}
}

type fetchSpec struct {
	revision string
	ref      string
}

type packageInfo struct {
	name    string
	version string
	refs    []string
}

func (f fetchSpec) isPinned() bool {
	return f.revision != "FETCH_HEAD"
}

type cmdBundle struct {
	subcommands.CommandRunBase

	logCfg logging.Config

	reposInput                stringmapflag.Value
	localDest                 string
	workdir                   string
	packageNamePrefix         string
	packageNameInternalPrefix string
	cipd                      cipdClient

	env subcommands.Env

	repos map[string]fetchSpec
}

func parseRepoInput(input stringmapflag.Value) (ret map[string]fetchSpec, err error) {
	ret = make(map[string]fetchSpec, len(input))
	for repo, fetchInfo := range input {
		if repo == "" {
			err = errors.New("repo URL is blank")
			return
		}
		var u *url.URL
		if u, err = url.Parse("https://" + repo); err != nil {
			err = errors.Annotate(err, "parsing repo %q", repo).Err()
			return
		}
		if strings.Contains(u.Host, ":") {
			err = errors.Reason("parsing repo %q: must not include scheme", repo).Err()
			return
		}
		if strings.HasSuffix(u.Path, ".git") {
			err = errors.Reason("parsing repo %q: must not end with .git", repo).Err()
			return
		}
		if strings.HasSuffix(u.Path, "/") {
			err = errors.Reason("parsing repo %q: must not end with slash", repo).Err()
			return
		}

		spec := fetchSpec{"FETCH_HEAD", "HEAD"}
		if fetchInfo != "" {
			switch toks := strings.SplitN(fetchInfo, ",", 2); {
			case len(toks) == 1:
				spec.revision = toks[0]
			case len(toks) == 2:
				spec.revision, spec.ref = toks[0], toks[1]
				if spec.ref != "HEAD" && !strings.HasPrefix(spec.ref, "refs/") {
					err = errors.Reason("parsing repo %q: ref must start with 'refs/', got %q", repo, spec.ref).Err()
					return
				}
			}
			if spec.revision != "FETCH_HEAD" {
				var decoded []byte
				if decoded, err = hex.DecodeString(spec.revision); err != nil {
					err = errors.Annotate(err, "parsing repo %q: bad revision", repo).Err()
					return
				}
				if len(decoded) != sha1.Size {
					err = errors.Reason("parsing repo %q: bad revision: wrong length", repo).Err()
					return
				}
			}
		}
		ret[repo] = spec
	}

	return
}

func (c *cmdBundle) parseFlags() (err error) {
	if len(c.reposInput) == 0 {
		return errors.New("no repos specified")
	}

	c.repos, err = parseRepoInput(c.reposInput)
	if err != nil {
		return errors.Annotate(err, "parsing repos").Err()
	}

	if c.localDest != "" {
		c.localDest, err = filepath.Abs(c.localDest)
		if err != nil {
			return errors.Annotate(err, "getting abspath of -local").Err()
		}
		if err = os.MkdirAll(c.localDest, 0777); err != nil {
			return errors.Annotate(err, "ensuring -local directory").Err()
		}
	}

	if c.packageNamePrefix == "" {
		return errors.New("-package-name-prefix is required")
	}
	if err = cipd_common.ValidatePackageName(c.packageNamePrefix); err != nil {
		return errors.Annotate(err, "validating -package-name-prefix").Err()
	}

	if c.packageNameInternalPrefix == "" {
		return errors.New("-package-name-internal-prefix is required")
	}
	if err = cipd_common.ValidatePackageName(c.packageNameInternalPrefix); err != nil {
		return errors.Annotate(err, "validating -package-name-internal-prefix").Err()
	}

	if c.workdir, err = filepath.Abs(c.workdir); err != nil {
		return errors.Annotate(err, "resolving workdir").Err()
	}

	return nil
}

func (c *cmdBundle) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := c.logCfg.Set(cli.GetContext(a, c, env))
	c.env = env

	if err := c.parseFlags(); err != nil {
		logging.WithError(err).Errorf(ctx, "parsing flags")
		return 1
	}

	if err := c.run(ctx); err != nil {
		logging.WithError(err).Errorf(ctx, "failed")
		return 1
	}
	return 0
}

var pathSquisher = strings.NewReplacer(
	"/", "_",
	"\\", "_",
)

func (c *cmdBundle) mkRepoDirs(repoName string) (repo, bundleDir string, err error) {
	base := filepath.Join(c.workdir, pathSquisher.Replace(repoName))
	repo = filepath.Join(base, "repo")
	bundleDir = filepath.Join(base, "bndl")

	if err = os.MkdirAll(repo, 0777); err != nil {
		return
	}

	// Make the directory clean
	if err = os.RemoveAll(bundleDir); err == nil {
		err = os.MkdirAll(bundleDir, 0777)
	}
	return
}

func (c *cmdBundle) prepPackage(repoName string, specref string, resolvedSpec fetchSpec) (pkg packageInfo, err error) {
	pkg.name = ""
	if strings.Contains(repoName, "internal") {
		pkg.name = fmt.Sprintf("%s/%s", c.packageNameInternalPrefix, repoName)
	} else {
		pkg.name = fmt.Sprintf("%s/%s", c.packageNamePrefix, repoName)
	}
	if err = cipd_common.ValidatePackageName(pkg.name); err != nil {
		err = errors.Reason("bug: %q doesn't result in a valid CIPD package", repoName).Err()
		return
	}

	pkg.version = "git_revision:" + resolvedSpec.revision
	pkg.refs = make([]string, 0, 2)
	if err = cipd_common.ValidatePackageRef(specref); err == nil {
		pkg.refs = append(pkg.refs, specref)
	}
	if resolvedSpec.ref != specref {
		if err = cipd_common.ValidatePackageRef(resolvedSpec.ref); err == nil {
			pkg.refs = append(pkg.refs, resolvedSpec.ref)
		}
	}
	if len(pkg.refs) == 0 {
		err = errors.Reason("bug: %s doesn't resolve to a valid CIPD ref name", specref).Err()
		return
	}

	return
}

func (c *cmdBundle) resolvePackage(ctx context.Context, pkg packageInfo, spec fetchSpec) (exists bool, err error) {
	exists = false

	if c.localDest == "" && c.cipd.serverQuiet(ctx, "resolve", pkg.name, "-version", pkg.version) == nil {
		exists = true
		logging.Infof(ctx, "CIPD already has `%s %s`", pkg.name, pkg.version)

		if spec.isPinned() {
			// if the user requested a pinned revision, don't presume that we
			// need to move a ref for them.
			err = nil
			return
		}

		// We just got the "freshest" value for these refs, so set them in CIPD.
		pkgRefArgs := make([]string, 0, len(pkg.refs))
		for _, ref := range pkg.refs {
			pkgRefArgs = append(pkgRefArgs, "-ref", ref)
		}
		cmd := append([]string{
			"set-ref",
			pkg.name,
			"-version", pkg.version,
		}, pkgRefArgs...)
		err = c.cipd.server(ctx, cmd...)
		return
	}

	return
}

func (c *cmdBundle) createBundle(ctx context.Context, pkg packageInfo, spec, resolvedSpec fetchSpec, repo gitRepo, bundleDir string) (err error) {
	// Get initial repo checkout
	logging.Infof(ctx, "fetching: %v", resolvedSpec)
	if err = repo.git(ctx, "init"); err == nil {
		if err = repo.ensureFetched(ctx, resolvedSpec); err == nil {
			err = repo.git(ctx, "checkout", resolvedSpec.revision)
		}
	}
	if err != nil {
		return err
	}

	logging.Infof(ctx, "recipes fetch + bundle")
	var r recipes
	// The destination dir must be empty or 'bundle' will fail.
	if err = os.RemoveAll(bundleDir); err == nil {
		err = os.MkdirAll(bundleDir, 0777)
	}
	if r, err = newRecipes(repo.localPath); err == nil {
		if err = r.run(ctx, "fetch"); err == nil {
			err = r.run(ctx, "bundle", "--destination", bundleDir)
		}
	}
	if err != nil {
		return err
	}
	logging.Infof(ctx, "finished bundling")

	// package or package+upload
	commonArgs := []string{
		"-name", pkg.name,
		"-in", bundleDir,
	}

	if c.localDest != "" {
		pkgFile := fmt.Sprintf("%s_%s.zip", pathSquisher.Replace(pkg.name), resolvedSpec.revision)
		cmd := []string{
			"pkg-build",
			"-install-mode", "copy",
			"-out", filepath.Join(c.localDest, pkgFile),
		}
		cmd = append(cmd, commonArgs...)
		if err = c.cipd.local(ctx, cmd...); err != nil {
			return err
		}
		logging.Infof(ctx, "finished cipd pkg-build: %q", pkgFile)
	} else {
		cmd := []string{
			"create",
			"-install-mode", "copy",
			"-tag", pkg.version,
		}
		cmd = append(cmd, commonArgs...)
		if !spec.isPinned() {
			pkgRefArgs := make([]string, 0, len(pkg.refs))
			for _, ref := range pkg.refs {
				pkgRefArgs = append(pkgRefArgs, "-ref", ref)
			}
			cmd = append(cmd, pkgRefArgs...)
		}
		if err = c.cipd.server(ctx, cmd...); err != nil {
			return err
		}
		logging.Infof(ctx, "finished cipd create: `%s %s`", pkg.name, pkg.version)
	}

	return nil
}

func (c *cmdBundle) run(ctx context.Context) error {
	return parallel.FanOutIn(func(ch chan<- func() error) {
		for repoName, spec := range c.repos {
			repoName, spec := repoName, spec
			ch <- func() error {
				repoDir, bundleDir, err := c.mkRepoDirs(repoName)
				if err != nil {
					return errors.Annotate(err, "making repo dirs").Err()
				}

				repo := gitRepo{repoDir, repoName}
				repoMu := sync.Mutex{}
				ctx := logging.SetField(ctx, "repo", repoName)

				return parallel.FanOutIn(func(chSpec chan<- func() error) {
					for _, specref := range strings.Split(spec.ref, ",") {
						resolvedSpecs, err := repo.resolveSpec(ctx, fetchSpec{spec.revision, specref})
						for _, resolvedSpec := range resolvedSpecs {
							specref, resolvedSpec := specref, resolvedSpec
							chSpec <- func() error {
								ctx := logging.SetField(ctx, "resolved", resolvedSpec)
								var pkg packageInfo
								if pkg, err = c.prepPackage(repoName, specref, resolvedSpec); err != nil {
									return err
								}
								if exists, err := c.resolvePackage(ctx, pkg, spec); exists {
									return err
								}
								// TODO(iannucci): once we have transparent git caching,
								// consider making a local directory for each resolved ref.
								repoMu.Lock()
								defer repoMu.Unlock()
								return c.createBundle(ctx, pkg, spec, resolvedSpec, repo, bundleDir)
							}
						}
					}
				})
			}
		}
	})
}
