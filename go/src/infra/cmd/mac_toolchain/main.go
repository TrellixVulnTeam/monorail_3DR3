// Copyright 2017 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"flag"
	"os"
	"strings"

	"golang.org/x/net/context"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/flag/flagenum"
	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/logging/gologger"
)

// DefaultCipdPackagePrefix is a package prefix for all the xcode packages.
const DefaultCipdPackagePrefix = "infra_internal/ios/xcode"

// AcceptedLicensesFile keeps record of the accepted Xcode licenses.
const AcceptedLicensesFile = "/Library/Preferences/com.apple.dt.Xcode.plist"

// PackageInstallerOnBots is a special script for securely installing packages
// on bots.
const PackageInstallerOnBots = "/usr/local/bin/xcode_install_wrapper.py"

// KindType is the type for enum values for the -kind argument.
type KindType string

var _ flag.Value = (*KindType)(nil)

const (
	macKind = KindType("mac")
	iosKind = KindType("ios")
	// DefaultKind is the default value for the -kind flag.
	DefaultKind = macKind
)

// KindTypeEnum is the corresponding Enum type for the -kind argument.
var KindTypeEnum = flagenum.Enum{
	"mac": macKind,
	"ios": iosKind,
}

// String implements flag.Value
func (t *KindType) String() string {
	return KindTypeEnum.FlagString(*t)
}

// Set implements flag.Value
func (t *KindType) Set(v string) error {
	return KindTypeEnum.FlagSet(t, v)
}

type commonFlags struct {
	subcommands.CommandRunBase
	verbose           bool
	cipdPackagePrefix string
}

type installRun struct {
	commonFlags
	xcodeVersion       string
	outputDir          string
	kind               KindType
	serviceAccountJSON string
}

type uploadRun struct {
	commonFlags
	xcodePath          string
	serviceAccountJSON string
}

type packageRun struct {
	commonFlags
	xcodePath string
	outputDir string
}

func normalizeCipdPrefix(prefix string) string {
	// Strip the trailing /.
	for strings.HasSuffix(prefix, "/") {
		prefix = prefix[:len(prefix)-1]
	}
	return prefix
}

func (c *commonFlags) ModifyContext(ctx context.Context) context.Context {
	if c.verbose {
		ctx = logging.SetLevel(ctx, logging.Debug)
	}
	return ctx
}

func (c *installRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if c.xcodeVersion == "" {
		errors.Log(ctx, errors.Reason("no Xcode version specified (-xcode-version)").Err())
		return 1
	}
	if c.outputDir == "" {
		errors.Log(ctx, errors.Reason("no output folder specified (-output-dir)").Err())
		return 1
	}
	logging.Infof(ctx, "About to install Xcode %s in %s for %s", c.xcodeVersion, c.outputDir, c.kind.String())

	c.cipdPackagePrefix = normalizeCipdPrefix(c.cipdPackagePrefix)
	installArgs := InstallArgs{
		xcodeVersion:           c.xcodeVersion,
		xcodeAppPath:           c.outputDir,
		acceptedLicensesFile:   AcceptedLicensesFile,
		cipdPackagePrefix:      c.cipdPackagePrefix,
		kind:                   c.kind,
		serviceAccountJSON:     c.serviceAccountJSON,
		packageInstallerOnBots: PackageInstallerOnBots,
	}
	if err := installXcode(ctx, installArgs); err != nil {
		errors.Log(ctx, err)
		return 1
	}
	return 0
}

func (c *uploadRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if c.xcodePath == "" {
		errors.Log(ctx, errors.Reason("path to Xcode.app is not specified (-xcode-path)").Err())
		return 1
	}
	c.cipdPackagePrefix = normalizeCipdPrefix(c.cipdPackagePrefix)
	if err := packageXcode(ctx, c.xcodePath, c.cipdPackagePrefix, c.serviceAccountJSON, ""); err != nil {
		errors.Log(ctx, err)
		return 1
	}
	return 0
}

func (c *packageRun) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	ctx := cli.GetContext(a, c, env)
	if c.xcodePath == "" {
		errors.Log(ctx, errors.Reason("path to Xcode.app is not specified (-xcode-path)").Err())
		return 1
	}
	if c.outputDir == "" {
		errors.Log(ctx, errors.Reason("output directory is not specified (-output-dir)").Err())
		return 1
	}
	c.cipdPackagePrefix = normalizeCipdPrefix(c.cipdPackagePrefix)
	if err := packageXcode(ctx, c.xcodePath, c.cipdPackagePrefix, "", c.outputDir); err != nil {
		errors.Log(ctx, err)
		return 1
	}
	return 0
}

func commonFlagVars(c *commonFlags) {
	c.Flags.BoolVar(&c.verbose, "verbose", false, "Log more.")
	c.Flags.StringVar(&c.cipdPackagePrefix, "cipd-package-prefix", DefaultCipdPackagePrefix, "CIPD package prefix.")
}

func installFlagVars(c *installRun) {
	commonFlagVars(&c.commonFlags)
	c.Flags.StringVar(&c.xcodeVersion, "xcode-version", "", "Xcode version code. (required)")
	c.Flags.StringVar(&c.outputDir, "output-dir", "", "Path where to install contents of Xcode.app (required).")
	c.Flags.StringVar(&c.serviceAccountJSON, "service-account-json", "", "Service account to use for authentication.")
	c.Flags.Var(&c.kind, "kind", "Installation kind: "+KindTypeEnum.Choices()+". (default: \""+string(DefaultKind)+"\")")
	c.kind = DefaultKind
}

func uploadFlagVars(c *uploadRun) {
	commonFlagVars(&c.commonFlags)
	c.Flags.StringVar(&c.serviceAccountJSON, "service-account-json", "", "Service account to use for authentication.")
	c.Flags.StringVar(&c.xcodePath, "xcode-path", "", "Path to Xcode.app to be uploaded. (required)")
}

func packageFlagVars(c *packageRun) {
	commonFlagVars(&c.commonFlags)
	c.Flags.StringVar(&c.xcodePath, "xcode-path", "", "Path to Xcode.app to be uploaded. (required)")
	c.Flags.StringVar(&c.outputDir, "output-dir", "", "Path to drop created CIPD packages. (required)")
}

var (
	cmdInstall = &subcommands.Command{
		UsageLine: "install <options>",
		ShortDesc: "Installs Xcode.",
		LongDesc: `Installs the requested parts of Xcode toolchain.

Note: the "Xcode.app" part of the path is not created.
Instead, "Contents" folder is placed directly in the folder specified
by the -output-dir. If you want an actual app that Finder can launch, specify
-output-dir "<path>/Xcode.app".`,
		CommandRun: func() subcommands.CommandRun {
			c := &installRun{}
			installFlagVars(c)
			return c
		},
	}

	cmdUpload = &subcommands.Command{
		UsageLine: "upload <options>",
		ShortDesc: "Uploads Xcode CIPD packages.",
		LongDesc:  "Creates and uploads Xcode toolchain CIPD packages.",
		CommandRun: func() subcommands.CommandRun {
			c := &uploadRun{}
			uploadFlagVars(c)
			return c
		},
	}

	cmdPackage = &subcommands.Command{
		UsageLine: "package <options>",
		ShortDesc: "Create CIPD packages locally.",
		LongDesc:  "Package Xcode into CIPD packages locally (will not upload).",
		CommandRun: func() subcommands.CommandRun {
			c := &packageRun{}
			packageFlagVars(c)
			return c
		},
	}
)

func main() {
	application := &cli.Application{
		Name:  "mac_toolchain",
		Title: "Mac OS / iOS toolchain management",
		Context: func(ctx context.Context) context.Context {
			goLoggerCfg := gologger.LoggerConfig{Out: os.Stderr}
			goLoggerCfg.Format = "[%{level:.1s} %{time:2006-01-02 15:04:05}] %{message}"
			ctx = goLoggerCfg.Use(ctx)

			ctx = logging.SetLevel(ctx, logging.Warning)
			ctx = useRealExec(ctx)
			return ctx
		},
		Commands: []*subcommands.Command{
			subcommands.CmdHelp,
			cmdInstall,
			cmdUpload,
			cmdPackage,
		},
	}
	os.Exit(subcommands.Run(application, nil))
}
