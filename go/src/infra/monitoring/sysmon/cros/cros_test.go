package cros

import (
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"go.chromium.org/luci/common/clock/testclock"
	"go.chromium.org/luci/common/tsmon"
	"golang.org/x/net/context"

	. "github.com/smartystreets/goconvey/convey"
)

func TestUpdate(t *testing.T) {
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)
	c, _ = testclock.UseTime(c, now)
	Convey("In a temporary directory", t, func() {
		tmpPath, err := ioutil.TempDir("", "cros-devicefile-test")
		So(err, ShouldBeNil)
		defer func() {
			So(os.RemoveAll(tmpPath), ShouldBeNil)
		}()
		fileNames := []string{
			strings.Replace(fileGlob, "*", "device1", 1),
			strings.Replace(fileGlob, "*", "device2", 1),
			strings.Replace(fileGlob, "*", "device3", 1),
		}
		Convey("Loads a number of empty files", func() {
			for _, fileName := range fileNames {
				So(ioutil.WriteFile(filepath.Join(tmpPath, fileName), []byte(""), 0644), ShouldBeNil)
			}
			So(update(c, tmpPath), ShouldNotBeNil)
		})
		Convey("Loads a number of broken files", func() {
			for _, fileName := range fileNames {
				So(ioutil.WriteFile(filepath.Join(tmpPath, fileName), []byte(`not json`), 0644), ShouldBeNil)
			}
			So(update(c, tmpPath), ShouldNotBeNil)
		})
	})
}

func TestUpdateMetrics(t *testing.T) {
	now := time.Date(2000, 1, 2, 3, 4, 5, 0, time.UTC)
	c := context.Background()
	c, _ = tsmon.WithDummyInMemory(c)
	c, _ = testclock.UseTime(c, now)
	statusFile := deviceStatusFile{
		ContainerHostname: "b1_b2",
		Timestamp:         946782246,
		Status:            "online",
		OSVersion:         "12317.0.0-rc1",
		Battery: batteryStatus{
			Charge: 50.56,
		},
		Temperature: map[string][]float64{
			"CPU": {29.65, 28.95, 30.01, 29.02},
			"GPU": {32.23},
		},
		Memory: memory{
			Avail: 1221444,
			Total: 1899548,
		},
		Uptime:    9233.61,
		ProcCount: 233,
	}
	Convey("UpdateMetrics Testing", t, func() {
		updateMetrics(c, statusFile)
		So(dutStatus.Get(c, statusFile.ContainerHostname), ShouldEqual,
			"online")
		So(crosVersion.Get(c, statusFile.ContainerHostname), ShouldEqual,
			"12317.0.0-rc1")
		So(battCharge.Get(c, statusFile.ContainerHostname), ShouldEqual,
			50.56)
		So(temperature.Get(c, statusFile.ContainerHostname, "CPU"), ShouldEqual,
			29.4075)
		So(temperature.Get(c, statusFile.ContainerHostname, "GPU"), ShouldEqual,
			32.23)
		So(totalMem.Get(c, statusFile.ContainerHostname), ShouldEqual,
			1899548)
		So(availMem.Get(c, statusFile.ContainerHostname), ShouldEqual,
			1221444)
		So(uptime.Get(c, statusFile.ContainerHostname), ShouldEqual,
			9233.61)
		So(procCount.Get(c, statusFile.ContainerHostname), ShouldEqual,
			233)
	})
}
