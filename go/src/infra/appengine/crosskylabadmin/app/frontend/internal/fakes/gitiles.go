// Copyright 2018 The LUCI Authors.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package fakes

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"context"
	"fmt"
	"infra/appengine/crosskylabadmin/app/config"
	"strings"

	"go.chromium.org/luci/common/errors"
	"go.chromium.org/luci/common/proto/git"
	"go.chromium.org/luci/common/proto/gitiles"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// GitilesClient is a fake implementation of the gitiles.GitilesClient
// interface.
type GitilesClient struct {
	Archived map[string][]byte
}

// NewGitilesClient returns an initialized fake GitilesClient.
func NewGitilesClient() *GitilesClient {
	return &GitilesClient{
		Archived: make(map[string][]byte),
	}
}

// Log implements gitiles.GitilesClient interface.
func (g *GitilesClient) Log(ctx context.Context, req *gitiles.LogRequest, opts ...grpc.CallOption) (*gitiles.LogResponse, error) {
	// Fake a single commit at the given committish iff there is archived data at that commit.
	if _, ok := g.Archived[projectRefKey(req.Project, req.Committish)]; ok {
		return &gitiles.LogResponse{
			Log: []*git.Commit{
				{Id: req.Committish},
			},
		}, nil
	}
	return &gitiles.LogResponse{}, nil
}

// Refs implements gitiles.GitilesClient interface.
func (g *GitilesClient) Refs(context.Context, *gitiles.RefsRequest, ...grpc.CallOption) (*gitiles.RefsResponse, error) {
	return nil, fmt.Errorf("fakeGitilesClient does not support Refs")
}

// Archive implements gitiles.GitilesClient interface.
func (g *GitilesClient) Archive(ctx context.Context, in *gitiles.ArchiveRequest, opts ...grpc.CallOption) (*gitiles.ArchiveResponse, error) {
	k := projectRefKey(in.Project, in.Ref)
	d, ok := g.Archived[k]
	if !ok {
		return nil, fmt.Errorf("Unknown project reference %s", k)
	}
	return &gitiles.ArchiveResponse{
		Filename: fmt.Sprintf("fake_gitiles_archive"),
		Contents: d,
	}, nil
}

// DownloadFile implements gitiles.GitilesClient inteface.
func (g *GitilesClient) DownloadFile(ctx context.Context, in *gitiles.DownloadFileRequest, opts ...grpc.CallOption) (*gitiles.DownloadFileResponse, error) {
	return nil, status.Error(codes.Unimplemented, "not implemented by fake")
}

// InventoryData contains serialized proto files to be returned as part of the
// gitiles archive.
type InventoryData struct {
	Lab            []byte
	Infrastructure []byte
	// The mapping from the path of the file where the DUT's inventory data is stored (relative the git project root) to its content.
	// E.g. chromeos-misc/jetstream-host.textpb => `duts { common {...} }`
	//
	// This will replace lab field when per-file inventory is enabled. See crbug.com/1008442 for details.
	Duts map[string][]byte
}

const fullPerm = 0777

func writeTarFile(tw *tar.Writer, path string, data []byte) error {
	err := tw.WriteHeader(&tar.Header{
		Name: path,
		Mode: fullPerm,
		Size: int64(len(data)),
	})
	if err != nil {
		return err
	}
	if _, err := tw.Write(data); err != nil {
		return err
	}
	return nil
}

// SetSplitInventory sets the serialized inventory data for the split inventory (each host has its own inventory file).
// archive returned from gitiles.
func (g *GitilesClient) SetSplitInventory(ic *config.Inventory, data InventoryData) error {
	var buf bytes.Buffer
	gw := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gw)

	for path, dut := range data.Duts {
		if err := writeTarFile(tw, path, dut); err != nil {
			return err
		}
	}
	if err := writeTarFile(tw, ic.InfrastructureDataPath, data.Infrastructure); err != nil {
		return err
	}
	if err := tw.Close(); err != nil {
		return err
	}
	if err := gw.Close(); err != nil {
		return err
	}
	g.Archived[projectRefKey(ic.Project, ic.Branch)] = buf.Bytes()
	return nil
}

// SetInventory sets the serialized lab and infrastructure data as the inventory
// archive returned from gitiles.
// TODO(xixuan): remove this after per-file inventory is landed and tested.
func (g *GitilesClient) SetInventory(ic *config.Inventory, data InventoryData) error {
	var buf bytes.Buffer
	gw := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gw)

	if err := tw.WriteHeader(&tar.Header{
		Name: ic.LabDataPath,
		Mode: fullPerm,
		Size: int64(len(data.Lab)),
	}); err != nil {
		return err
	}
	if _, err := tw.Write(data.Lab); err != nil {
		return err
	}
	if err := tw.WriteHeader(&tar.Header{
		Name: ic.InfrastructureDataPath,
		Mode: fullPerm,
		Size: int64(len(data.Infrastructure)),
	}); err != nil {
		return err
	}
	if _, err := tw.Write(data.Infrastructure); err != nil {
		return err
	}
	if err := tw.Close(); err != nil {
		return err
	}
	if err := gw.Close(); err != nil {
		return err
	}
	g.Archived[projectRefKey(ic.Project, ic.Branch)] = buf.Bytes()
	return nil
}

// SetDeviceConfigs sets the serialized device configs as returned from gitiles.
func (g *GitilesClient) SetDeviceConfigs(ic *config.Inventory, configs []byte) error {
	var buf bytes.Buffer
	gw := gzip.NewWriter(&buf)
	tw := tar.NewWriter(gw)
	defer tw.Close()
	defer gw.Close()

	if err := tw.WriteHeader(&tar.Header{
		Name: ic.DeviceConfigPath,
		Mode: fullPerm,
		Size: int64(len(configs)),
	}); err != nil {
		return errors.Annotate(err, "set device config").Err()
	}
	if _, err := tw.Write(configs); err != nil {
		return err
	}
	if err := tw.Close(); err != nil {
		return err
	}
	if err := gw.Close(); err != nil {
		return err
	}
	g.Archived[projectRefKey(ic.DeviceConfigProject, ic.DeviceConfigBranch)] = buf.Bytes()
	return nil
}

func projectRefKey(project, ref string) string {
	// gitiles inconsistently expects the "refs/heads/" prefix. Always strip the
	// prefix before storing refs.
	return fmt.Sprintf("%s::%s", project, strings.TrimPrefix(ref, "refs/heads/"))
}
