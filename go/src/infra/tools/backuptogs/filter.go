package main

import (
	"context"

	"infra/tools/backuptogs/filetree"

	"go.chromium.org/luci/common/logging"
	"go.chromium.org/luci/common/tsmon/metric"
	"go.chromium.org/luci/common/tsmon/types"
)

var (
	filesSeen = metric.NewCounter("backups/files_seen",
		"Number of files seen in scope for backup",
		&types.MetricMetadata{})
)

// filterFiles determines whether a file needs to be backed up by comparing to
// a previous backup state.
//
// It also populates a new backup state with each file that it sees on
// filesChan, regardless of whether it actually needs to be backed up.
//
// Similarly, each file from filesChan is deleted from prevState. This
// mechanism is used to detect files that have been deleted on the local
// filesystem since the previous backup run.
func filterFiles(
	ctx context.Context,
	filesChan <-chan fileInfo,
	prevState *filetree.Dir,
	newState *filetree.Dir,
) <-chan string {

	backupsChan := make(chan string, 10)

	go func() {
		defer func() {
			logging.Debugf(ctx, "Closing backupsChan")
			close(backupsChan)
		}()

		for info := range filesChan {

			select {
			case _ = <-ctx.Done():
				continue
			default:
			}

			filesSeen.Add(ctx, 1)
			if prevState == nil || !prevState.MatchOsInfo(info.path, info.osInfo) {
				backupsChan <- info.path
			}

			if prevState != nil {
				prevState.Del(info.path)
			}

			newState.Put(info.path, &filetree.FileInfo{
				Size:    info.osInfo.Size(),
				ModTime: info.osInfo.ModTime(),
				Mode:    info.osInfo.Mode(),
			})
		}

		logging.Debugf(ctx, "filesChan closed")
	}()

	return backupsChan
}
