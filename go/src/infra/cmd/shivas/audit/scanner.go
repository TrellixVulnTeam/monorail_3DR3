// Copyright 2020 The Chromium Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package audit

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"strings"

	"github.com/maruel/subcommands"
	"go.chromium.org/luci/auth/client/authcli"
	"go.chromium.org/luci/common/cli"
	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/gcloud/gs"
	"go.chromium.org/luci/grpc/prpc"

	fleetAPI "infra/appengine/cros/lab_inventory/api/v1"
	"infra/cmd/shivas/site"
	"infra/cmd/shivas/utils"
	"infra/cmdsupport/cmdlib"
	invUtils "infra/libs/cros/lab_inventory/utils"
	fleet "infra/libs/fleet/protos"
	ufs "infra/libs/fleet/protos/go"
)

// ScannerCmd runs with the scanner to scan lab assets.
var ScannerCmd = &subcommands.Command{
	UsageLine: "scan -l lab",
	ShortDesc: "Audit using a barcode scanner",
	LongDesc: `Connect the scanner and run the tool with defaults for location;

	The scan order is: location => asset tag(s) => next location => asset tag(s)
	Once the next location is scanned, the last location and its related asset
	tags will be recorded to registration system.

	Every scan will be recorded in local log file: <home>/.shivas/timestamp-log
	Every interaction with registration system will be recorded in local res file:
		<home>/.shivas/timestamp-res
	`,
	CommandRun: func() subcommands.CommandRun {
		c := &bcScanner{}
		c.authFlags.Register(&c.Flags, site.DefaultAuthOptions)
		c.envFlags.Register(&c.Flags)
		c.Flags.StringVar(&c.lab, "l", "", "Default lab")
		c.Flags.StringVar(&c.aisle, "a", "", "Default aisle")
		c.Flags.StringVar(&c.row, "ro", "", "Default row")
		c.Flags.StringVar(&c.rack, "ra", "", "Default rack")
		c.Flags.StringVar(&c.shelf, "s", "", "Default Shelf")
		c.Flags.StringVar(&c.position, "p", "", "Default position")
		c.Flags.StringVar(&c.zone, "z", "", "Default Zone")
		c.Flags.StringVar(&c.logDir, "log-dir", getLogDir(), `Dir to store logs. Two types of logs
		are stored here. Logs with <timestamp>-log filename store the asset-location inputs in order.
		Logs with <timestamp>-res filename store the results of datastore transactions.`)
		return c
	},
}

func getLogDir() string {
	// Attempt to use home dir for logs, failing which use /tmp
	home, err := os.UserHomeDir()
	if err != nil {
		return "/tmp/.shivas"
	}
	return filepath.Join(home, ".shivas")
}

func createLogDir(logDir string) error {
	_, err := os.Stat(logDir)
	if os.IsNotExist(err) {
		if err := os.Mkdir(logDir, 0777); err != nil {
			return err
		}
	} else {
		return err
	}
	return nil
}

type bcScanner struct {
	subcommands.CommandRunBase
	authFlags authcli.Flags
	envFlags  site.EnvFlags
	logDir    string
	lab       string
	aisle     string
	row       string
	rack      string
	shelf     string
	position  string
	zone      string
	state     string
	updater   *utils.Updater
}

func (c *bcScanner) Run(a subcommands.Application, args []string, env subcommands.Env) int {
	if err := c.exec(a, args, env); err != nil {
		cmdlib.PrintError(a, err)
		return 1
	}
	return 0
}

func (c *bcScanner) exec(a subcommands.Application, args []string, env subcommands.Env) (err error) {
	if c.lab == "" {
		return cmdlib.NewUsageError(c.Flags, "Lab is required")
	}

	ctx := cli.GetContext(a, c, env)
	hc, err := cmdlib.NewHTTPClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}

	username, err := getUsername(ctx, &c.authFlags, a.GetOut())
	if err != nil {
		return err
	}

	e := c.envFlags.Env()
	fmt.Printf("Using inventory service %s\n", e)

	ic := fleetAPI.NewInventoryPRPCClient(&prpc.Client{
		C:       hc,
		Host:    e.InventoryService,
		Options: site.DefaultPRPCOptions,
	})

	if err := createLogDir(c.logDir); err != nil {
		return err
	}

	gsc, err := getGSClient(ctx, &c.authFlags)
	if err != nil {
		return err
	}

	u, err := utils.NewUpdater(ctx, ic, gsc, c.logDir, username)
	if err != nil {
		return err
	}
	c.updater = u
	go c.signalCatcher()
	c.parseLoop()
	return err
}

func getUsername(ctx context.Context, f *authcli.Flags, w io.Writer) (string, error) {
	at, err := cmdlib.NewAuthenticator(ctx, f)
	if err != nil {
		return "", err
	}
	username, err := at.GetEmail()
	if err != nil {
		return "", errors.New("Please login with your @google.com account")
	}
	fmt.Printf("Username: %s\n", username)
	return strings.Split(username, "@")[0], nil
}

func getGSClient(ctx context.Context, f *authcli.Flags) (gs.Client, error) {
	t, err := cmdlib.NewAuthenticatedTransport(ctx, f)
	if err != nil {
		return nil, err
	}
	return gs.NewProdClient(ctx, t)
}

var currLoc *ufs.Location

//List to collect assets into
var assetList []*fleet.ChopsAsset

// parseLoop handles the data from the scanner
func (c *bcScanner) parseLoop() {
	u := c.updater
	scanner := bufio.NewScanner(os.Stdin)
	currLoc = c.defaultLocation()
	prompt()
	for scanner.Scan() {
		iput := scanner.Text()
		/* The four types of input that can be expected in this loop
		*  and the: actions taken are as follows
		*  1. Location input
		*      -> Send all the assets in assetList to updater
		*      -> Update the current location
		*      -> Reset the assetList
		*  2. Close
		*      -> Send all the assets in assetList to updater
		*      -> Close the updater
		*  3. Back
		*      -> Remove the last entry in assetList
		*  4. Asset Tag
		*      -> Any input that doesn't fit the other three options is
		*         considered as Asset tag and assetList updated
		 */
		if utils.IsLocation(iput) {
			currLoc = invUtils.GetLocation(iput)
			u.AddAsset(assetList)
			assetList = []*fleet.ChopsAsset{}
		} else if isClose(iput) {
			if len(assetList) != 0 {
				u.AddAsset(assetList)
			}
			u.Close()
			return
		} else if isBack(iput) {
			if len(assetList) > 0 {
				prompt()
				last := assetList[len(assetList)-1]
				fmt.Println("- " + last.GetId())
				assetList = assetList[:len(assetList)-1]
			}
		} else if iput != "" {
			dev := &fleet.ChopsAsset{
				Id:       iput,
				Location: currLoc,
			}
			assetList = append(assetList, dev)
		}
		prompt()
	}
}

func prompt() {
	fmt.Print("[" + currLoc.String() + "] ")
}

// Determines if the input string describes close action
// Not supported the barcode for scanning yet.
func isClose(iput string) bool {
	return iput == "%close"
}

// Determines if the input string describes back action
// Not supported the barcode for scanning yet.
func isBack(iput string) bool {
	return iput == "%back"
}

func (c *bcScanner) defaultLocation() *ufs.Location {
	return &ufs.Location{
		Lab:      c.lab,
		Aisle:    c.aisle,
		Row:      c.row,
		Rack:     c.rack,
		Shelf:    c.shelf,
		Position: c.position,
	}
}

func (c *bcScanner) signalCatcher() {
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt)
	s := <-sigChan
	fmt.Println("Caught signal: ", s)
	if len(assetList) != 0 {
		c.updater.AddAsset(assetList)
	}
	c.updater.Close()
	os.Exit(0)
}
